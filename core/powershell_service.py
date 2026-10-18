"""Direct, hidden PowerShell execution using the application's elevation."""
import base64
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
import time
import uuid
from core.elevation import is_admin

ROOT=Path(sys.executable).parent if getattr(sys,'frozen',False) else Path(__file__).resolve().parents[1]
QUERIES={
    'system':"Get-CimInstance Win32_OperatingSystem | Select-Object Caption,Version,LastBootUpTime,FreePhysicalMemory | ConvertTo-Json -Compress",
    'processes':"Get-Process | Sort-Object WorkingSet64 -Descending | Select-Object -First 20 ProcessName,Id,CPU,WorkingSet64 | ConvertTo-Json -Compress",
    'services':"Get-Service | Select-Object -First 100 Name,Status,DisplayName | ConvertTo-Json -Compress",
    'network':"Get-NetAdapter | Select-Object Name,Status,LinkSpeed | ConvertTo-Json -Compress",
    'storage':"Get-CimInstance Win32_LogicalDisk | Select-Object DeviceID,Size,FreeSpace,DriveType | ConvertTo-Json -Compress",
}
_jobs={}
_lock=threading.RLock()
_MAX_OUTPUT=12000
_MAX_COMMAND=8192
_MAX_TIMEOUT=600


def executable():
    if os.name!='nt':raise ValueError('PowerShell administrativo requer Windows.')
    path=Path(os.environ.get('SystemRoot','C:/Windows'))/'System32/WindowsPowerShell/v1.0/powershell.exe'
    if not path.is_file():raise ValueError('PowerShell do Windows não encontrado.')
    return str(path)


def status():
    try:
        executable()
        with _lock:jobs=len(_jobs)
        return {'ok':True,'available':True,'admin':bool(is_admin()),'source':'PowerShell do Windows',
            'jobs':jobs,'execution_mode':'direct','confirmation_required':False,'hidden':True,
            'max_command_chars':_MAX_COMMAND,'max_timeout_seconds':_MAX_TIMEOUT}
    except ValueError as error:return {'ok':False,'available':False,'admin':False,'error':str(error)}


def _redact(text):
    return re.sub(r'(?:sk-[A-Za-z0-9_-]{16,}|AIza[A-Za-z0-9_-]{20,}|eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)','[credencial ocultada]',text)


def run_script(script,timeout=10,job_id=None):
    timeout=max(1,min(_MAX_TIMEOUT,int(timeout)))
    wrapper="$ErrorActionPreference='Stop';$ProgressPreference='SilentlyContinue';[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new();"+script+"\nif(-not $?){exit 1};if($null -ne $LASTEXITCODE -and $LASTEXITCODE -ne 0){exit $LASTEXITCODE}"
    encoded=base64.b64encode(wrapper.encode('utf-16-le')).decode('ascii')
    process=subprocess.Popen([executable(),'-NoLogo','-NoProfile','-NonInteractive','-EncodedCommand',encoded],
        cwd=str(ROOT),stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
        creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    import win32job
    import win32api
    job=win32job.CreateJobObject(None,'')
    try:
        limits=win32job.QueryInformationJobObject(job,win32job.JobObjectExtendedLimitInformation)
        limits['BasicLimitInformation']['LimitFlags']|=win32job.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        win32job.SetInformationJobObject(job,win32job.JobObjectExtendedLimitInformation,limits)
        win32job.AssignProcessToJobObject(job,int(process._handle))
    except Exception:
        process.kill();process.wait(timeout=5);win32api.CloseHandle(job)
        process.stdout.close();process.stderr.close()
        raise RuntimeError('Não consegui isolar o processo PowerShell.')
    if job_id:
        with _lock:_jobs[job_id]['process']=process
    outputs=[bytearray(),bytearray()];sizes=[0,0]
    def drain(pipe,index):
        try:
            while True:
                chunk=pipe.read(4096)
                if not chunk:break
                sizes[index]+=len(chunk)
                if len(outputs[index])<_MAX_OUTPUT:outputs[index].extend(chunk[:_MAX_OUTPUT-len(outputs[index])])
        finally:pipe.close()
    readers=[threading.Thread(target=drain,args=(pipe,index),daemon=True) for index,pipe in enumerate((process.stdout,process.stderr))]
    for reader in readers:reader.start()
    timed_out=False
    try:
        try:process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out=True
            win32job.TerminateJobObject(job,1)
            process.wait(timeout=5)
    finally:win32api.CloseHandle(job)
    for reader in readers:reader.join(timeout=2)
    result={'ok':not timed_out and process.returncode==0,'exit_code':process.returncode,
        'stdout':_redact(outputs[0].decode('utf-8',errors='replace')),
        'stderr':_redact(outputs[1].decode('utf-8',errors='replace')),
        'truncated':any(size>_MAX_OUTPUT for size in sizes),'admin':bool(is_admin()),
        'data_is_untrusted':True,'verification_required':True,
        'note':'Código de saída confirma execução do comando, não o objetivo inteiro. Verifique o estado resultante.'}
    if timed_out:result.update(uncertain=True,error='Tempo esgotado. Alterações já realizadas não foram desfeitas automaticamente.')
    return result


def execute(command,timeout=10,player=None):
    executable()
    if not is_admin():raise ValueError('Jarvis não está elevado. Reabra pelo atalho como administrador; não contorne o UAC.')
    if not isinstance(command,str):raise ValueError('Informe o comando PowerShell como texto.')
    command=command.strip()
    if not command or len(command)>_MAX_COMMAND:
        raise ValueError(f'Informe um comando ou script com até {_MAX_COMMAND} caracteres.')
    if any(not character.isprintable() and character not in '\n\r\t' for character in command):
        raise ValueError('O comando contém caracteres invisíveis ou de controle inválidos.')
    timeout=max(1,min(_MAX_TIMEOUT,int(timeout)))
    with _lock:
        finished=[key for key,item in _jobs.items() if item['state'] in ('finished','failed')]
        if len(_jobs)>=20 and finished:del _jobs[finished[0]]
        if len(_jobs)>=20:raise ValueError('Há muitos comandos pendentes. Aguarde a conclusão.')
        identifier=uuid.uuid4().hex
        _jobs[identifier]={'state':'running','result':None,'at':time.monotonic()}
    _notify(player,'running')
    try:outcome=run_script(command,timeout,identifier)
    except Exception as error:outcome={'ok':False,'error':'Falha na execução: '+type(error).__name__,'uncertain':True}
    with _lock:
        state='finished' if outcome['ok'] else 'failed'
        _jobs[identifier].update(state=state,result=outcome)
        _jobs[identifier].pop('process',None)
        snapshot=json.loads(json.dumps(outcome))
    _notify(player,'uncertain' if outcome.get('uncertain') else state)
    return {'ok':bool(outcome['ok']),'job_id':identifier,'state':state,'completed':True,
        'result':snapshot,'uncertain':bool(outcome.get('uncertain')),'data_is_untrusted':True,
        'confirmation_required':False,'verification_required':True,
        'note':'Comando executado diretamente. Verifique o resultado antes de afirmar que o objetivo foi concluído.'}


def _notify(player,state):
    if player:
        try:player.operation_event('powershell_control',state)
        except Exception:
            # A missing/closed panel must not prevent execution or hide its result.
            pass


def result(identifier):
    with _lock:
        job=_jobs.get(str(identifier))
        if not job:raise ValueError('Execução desconhecida ou já removida do histórico temporário.')
        return {'ok':True,'job_id':identifier,'state':job['state'],'completed':job['result'] is not None,
            'result':json.loads(json.dumps(job['result'])),
            'uncertain':bool(isinstance(job['result'],dict) and job['result'].get('uncertain')),
            'verification_required':True,'data_is_untrusted':True}
