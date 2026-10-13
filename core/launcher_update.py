"""Substitui o EXE validado depois que o processo atual libera o arquivo."""
import base64
import hashlib
import os
import re
import subprocess
import sys
from pathlib import Path
from core.distribution import atomic_json


def schedule(installation):
    if os.name!='nt' or not getattr(sys,'frozen',False):return False
    state=installation.state();pending=state.get('pending_launcher')
    if not pending:return False
    if not re.fullmatch(r'launcher-next-[a-f0-9]{32}\.exe',pending['name']):raise ValueError('Inicializador pendente invalido.')
    if not re.fullmatch(r'[a-f0-9]{64}',pending['sha256']):raise ValueError('Hash de inicializador invalido.')
    if hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest()==pending['sha256']:
        state['pending_launcher']=None;atomic_json(installation.state_file,state)
        (installation.root/pending['name']).unlink(missing_ok=True);return False
    source=installation.root/pending['name'];target=installation.root/'DIEF JARVIS.exe'
    if hashlib.sha256(source.read_bytes()).hexdigest()!=pending['sha256']:raise ValueError('Inicializador pendente danificado.')
    values=[str(source),str(target),str(installation.root/'DIEF JARVIS.update-tmp.exe')]
    assignments=';'.join('$p'+str(i)+'=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String("'+base64.b64encode(value.encode()).decode()+'"))' for i,value in enumerate(values))
    # The one-file bootloader parent also holds the executable open.
    script=assignments+f';Wait-Process -Id {os.getpid()},{os.getppid()} -ErrorAction SilentlyContinue;'
    script+=f'if((Get-FileHash -LiteralPath $p0 -Algorithm SHA256).Hash.ToLowerInvariant() -ne "{pending["sha256"]}"){{exit 1}};'
    script+='[IO.File]::Copy($p0,$p2,$true);if([IO.File]::Exists($p1)){[IO.File]::Replace($p2,$p1,$null)}else{[IO.File]::Move($p2,$p1)}'
    subprocess.Popen(['powershell.exe','-NoProfile','-NonInteractive','-EncodedCommand',base64.b64encode(script.encode('utf-16le')).decode()],
        stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
    return True
