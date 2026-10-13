"""RECORD das distribuicoes detecta arquivos removidos ou alterados."""
import argparse
import base64
import hashlib
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys


def broken_distributions():
    root=Path(sys.prefix).resolve();broken=[]
    for distribution in importlib.metadata.distributions():
        for entry in distribution.files or []:
            if entry.hash is None:continue
            path=Path(distribution.locate_file(entry)).resolve()
            if not path.is_relative_to(root):continue
            if not path.is_file():broken.append(distribution.metadata['Name']);break
            digest=hashlib.new(entry.hash.mode)
            with path.open('rb') as stream:
                while chunk:=stream.read(1024*1024):digest.update(chunk)
            actual=base64.urlsafe_b64encode(digest.digest()).rstrip(b'=').decode()
            if actual!=entry.hash.value:broken.append(distribution.metadata['Name']);break
    return sorted(set(broken))


def repair(python,application,progress,stop):
    from core.installer_process import spawn,close_tree
    def inspect():
        progress('Dependências','Conferindo integridade dos arquivos instalados','working')
        command=[str(python),'-I',str(application/'core/dependency_integrity.py'),'--inspect']
        process=spawn(command,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,encoding='utf-8')
        import time
        until=time.monotonic()+180
        while process.poll() is None:
            if stop.wait(.1) or time.monotonic()>until:close_tree(process);process.stdout.close();raise InterruptedError('Verificacao de integridade interrompida.')
        close_tree(process);output=process.stdout.read();process.stdout.close()
        if process.returncode:raise RuntimeError('Nao foi possivel conferir a integridade das dependencias.')
        value=json.loads(output)
        if not isinstance(value,list) or not all(isinstance(name,str) for name in value):raise ValueError('Relatorio de integridade invalido.')
        return value
    damaged=inspect()
    if damaged:
        from core.distribution import run
        locked=application/'requirements-win.lock'
        requirements=locked if locked.exists() else application/'requirements.txt'
        progress('Dependências','Reparando arquivos de '+', '.join(damaged[:4]),'working')
        run([str(python),'-I','-m','pip','--isolated','install','--force-reinstall','--no-deps','--no-input',
            '--disable-pip-version-check','--index-url','https://pypi.org/simple',
            *(['--require-hashes'] if locked.exists() else []),'-r',str(requirements)],stop)
        if inspect():raise RuntimeError('Dependencias ainda apresentam arquivos danificados.')
    progress('Dependências','Pacotes e arquivos internos verificados','ok')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--inspect',action='store_true');parser.parse_args()
    print(json.dumps(broken_distributions()))
