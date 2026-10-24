"""Substitui o EXE validado depois que o processo atual libera o arquivo."""
import base64
import hashlib
import os
import re
import subprocess
import sys
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
    if hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest()==pending['sha256']:
        state['pending_launcher']=None;atomic_json(installation.state_file,state)
        (installation.root/pending['name']).unlink(missing_ok=True)
        return schedule_restart(installation.root,restart_version) if restart_version else False
    source=installation.root/pending['name'];target=installation.root/'DIEF JARVIS.exe'
    if hashlib.sha256(source.read_bytes()).hexdigest()!=pending['sha256']:raise ValueError('Inicializador pendente danificado.')
    values=[str(source),str(target),str(installation.root/'DIEF JARVIS.update-tmp.exe')]
    assignments=';'.join('$p'+str(i)+'=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String("'+base64.b64encode(value.encode()).decode()+'"))' for i,value in enumerate(values))
    # The one-file bootloader parent also holds the executable open.
    script=assignments+f';Wait-Process -Id {os.getpid()},{os.getppid()} -ErrorAction SilentlyContinue;'
    script+=f'if((Get-FileHash -LiteralPath $p0 -Algorithm SHA256).Hash.ToLowerInvariant() -ne "{pending["sha256"]}"){{exit 1}};'
    script+='[IO.File]::Copy($p0,$p2,$true);if([IO.File]::Exists($p1)){[IO.File]::Replace($p2,$p1,$null)}else{[IO.File]::Move($p2,$p1)}'
    if restart_version:script+=';'+restart_command(installation.root,restart_version)
    subprocess.Popen(['powershell.exe','-NoProfile','-NonInteractive','-EncodedCommand',base64.b64encode(script.encode('utf-16le')).decode()],
        stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
    return True


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
    if not re.fullmatch(r'\d+\.\d+\.\d+',version):raise ValueError('Versao invalida.')
    encoded=base64.b64encode(str(Path(root)).encode()).decode()
    return ('$r=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String("'+encoded+'"));'
            '$env:PYINSTALLER_RESET_ENVIRONMENT="1";'
            '$exe=[IO.Path]::Combine($r,"DIEF JARVIS.exe");'
            '$argsText=\'--root "\'+$r+\'" --update-version '+version+'\';'
            'Start-Process -FilePath $exe -ArgumentList $argsText -WindowStyle Hidden')
