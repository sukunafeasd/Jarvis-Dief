"""Substitui o EXE validado depois que o processo atual libera o arquivo."""
import base64
import hashlib
import os
import re
import subprocess
import sys
import uuid
from pathlib import Path
from core.distribution import atomic_json


def schedule(installation, restart_version=None):
    if os.name!='nt' or not getattr(sys,'frozen',False):return False
    state=installation.state();pending=state.get('pending_launcher')
    if restart_version is not None and not re.fullmatch(r'\d+\.\d+\.\d+',restart_version):raise ValueError('Versao invalida.')
    if not pending:
        if restart_version:return schedule_restart(installation.root,restart_version)
        return False
    if not re.fullmatch(r'launcher-next-[a-f0-9]{32}\.exe',pending['name']):raise ValueError('Inicializador pendente invalido.')
    if not re.fullmatch(r'[a-f0-9]{64}',pending['sha256']):raise ValueError('Hash de inicializador invalido.')
    target=installation.root/'DIEF JARVIS.exe'
    if target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest()==pending['sha256']:
        state['pending_launcher']=None;atomic_json(installation.state_file,state)
        (installation.root/pending['name']).unlink(missing_ok=True)
        return schedule_restart(installation.root,restart_version) if restart_version else False
    source=installation.root/pending['name'];target=installation.root/'DIEF JARVIS.exe'
    if hashlib.sha256(source.read_bytes()).hexdigest()!=pending['sha256']:raise ValueError('Inicializador pendente danificado.')
    nonce=uuid.uuid4().hex
    values=[str(source),str(target),str(installation.root/'DIEF JARVIS.update-tmp.exe'),
            str(installation.root/'DIEF JARVIS.previous.exe'),
            str(installation.root/'logs/launcher-update.json'),
            str(installation.root/'sessions'/('launcher-'+nonce+'.ready')),str(installation.root)]
    assignments=';'.join('$p'+str(i)+'=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String("'+base64.b64encode(value.encode()).decode()+'"))' for i,value in enumerate(values))
    # The one-file bootloader parent also holds the executable open.
    script=assignments+f';Wait-Process -Id {os.getpid()},{os.getppid()} -ErrorAction SilentlyContinue;'
    script+=replacement_body(pending['sha256'],nonce)
    if restart_version:
        script+=';if($success){'+restart_command(installation.root,restart_version)+'}elseif($restored){'+restart_command(installation.root,None)+'}'
    subprocess.Popen(['powershell.exe','-NoProfile','-NonInteractive','-EncodedCommand',base64.b64encode(script.encode('utf-16le')).decode()],
        stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
    return True


def replacement_body(expected,nonce):
    if not re.fullmatch(r'[a-f0-9]{64}',expected) or not re.fullmatch(r'[a-f0-9]{32}',nonce):
        raise ValueError('Parametros do inicializador invalidos.')
    return r'''
$ErrorActionPreference='Stop';$success=$false;$replaced=$false;$restored=$false;$probe=$null;$stage='source';$failure=''
function FileDigest($path) {
 $hash=[Security.Cryptography.SHA256]::Create();$stream=[IO.File]::OpenRead($path)
 try {return [BitConverter]::ToString($hash.ComputeHash($stream)).Replace('-','').ToLowerInvariant()}
 finally {$stream.Dispose();$hash.Dispose()}
}
try {
 if((FileDigest $p0) -ne '__HASH__'){throw 'source_hash'}
 for($attempt=0;$attempt -lt 10;$attempt++) {
  try {
   $stage='replace'
   [IO.File]::Copy($p0,$p2,$true)
   if((FileDigest $p2) -ne '__HASH__'){throw 'copy_hash'}
   if([IO.File]::Exists($p1)){[IO.File]::Replace($p2,$p1,$p3)}else{[IO.File]::Move($p2,$p1)}
   $replaced=$true;break
  } catch {if($attempt -eq 9){throw};Start-Sleep -Milliseconds 1000}
 }
 if((FileDigest $p1) -ne '__HASH__'){throw 'target_hash'}
 $stage='probe'
 $env:PYINSTALLER_RESET_ENVIRONMENT='1'
 $probeArgs='--root "'+$p6+'" --launcher-probe __NONCE__'
 $probe=Start-Process -FilePath $p1 -ArgumentList $probeArgs -WindowStyle Hidden -PassThru
 if(-not $probe.WaitForExit(45000)){throw 'probe_timeout'}
 if($probe.ExitCode -ne 0 -or -not [IO.File]::Exists($p5)){throw 'probe_failed'}
 if([IO.File]::ReadAllText($p5).Trim() -ne '__HASH__'){throw 'probe_hash'}
 $success=$true
} catch {
 $failure=$_.Exception.GetType().FullName
 try {
  if($null -ne $probe -and -not $probe.HasExited){
   & "$env:SystemRoot\System32\taskkill.exe" /PID $probe.Id /T /F | Out-Null
   $probe.WaitForExit(5000)|Out-Null
  }
 } catch {}
 if($replaced -and [IO.File]::Exists($p3)) {
  for($attempt=0;$attempt -lt 10;$attempt++) {
   try {[IO.File]::Copy($p3,$p2,$true);[IO.File]::Replace($p2,$p1,[NullString]::Value);$restored=$true;break}
   catch {Start-Sleep -Milliseconds 1000}
  }
 }
} finally {
 try {
  [IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($p4))|Out-Null
  @{success=$success;restored=$restored;stage=$stage;error_type=$failure;expected_sha256='__HASH__';time=[DateTime]::UtcNow.ToString('o')}|ConvertTo-Json|Set-Content -LiteralPath $p4 -Encoding UTF8
  if([IO.File]::Exists($p5)){[IO.File]::Delete($p5)}
 } catch {}
}
'''.replace('__HASH__',expected).replace('__NONCE__',nonce)


def schedule_restart(root, version):
    """Wait for both PyInstaller processes to release the singleton mutex."""
    if not re.fullmatch(r'\d+\.\d+\.\d+',version):raise ValueError('Versao invalida.')
    target=Path(root)/'DIEF JARVIS.exe'
    encoded=base64.b64encode(str(target).encode()).decode()
    script=f'$p=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String("{encoded}"));'
    script+=f'Wait-Process -Id {os.getpid()},{os.getppid()} -ErrorAction SilentlyContinue;'
    script+=restart_command(root,version)
    subprocess.Popen(['powershell.exe','-NoProfile','-NonInteractive','-EncodedCommand',base64.b64encode(script.encode('utf-16le')).decode()],
        stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
    return True


def restart_command(root,version):
    if version is not None and not re.fullmatch(r'\d+\.\d+\.\d+',version):raise ValueError('Versao invalida.')
    encoded=base64.b64encode(str(Path(root)).encode()).decode()
    return ('$r=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String("'+encoded+'"));'
            '$env:PYINSTALLER_RESET_ENVIRONMENT="1";'
            '$exe=[IO.Path]::Combine($r,"DIEF JARVIS.exe");'
            '$argsText=\'--root "\'+$r+\'"'+(' --update-version '+version if version else '')+'\';'
            'Start-Process -FilePath $exe -ArgumentList $argsText -WindowStyle Hidden')
