"""Entrada portatil: elevacao obrigatoria, ambiente isolado e bootstrap existente."""
import os
import subprocess
import sys
import venv
from pathlib import Path

ROOT=Path(__file__).resolve().parent


def prepare(root=ROOT):
    root=Path(root)
    executable=root/'.venv'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    if not executable.exists():venv.EnvBuilder(with_pip=True).create(root/'.venv')
    if not executable.exists():raise RuntimeError('Não foi possível preparar o ambiente Python do Jarvis.')
    return executable


def main():
    if sys.version_info<(3,11):raise RuntimeError('Instale Python 3.11 ou mais recente; Python 3.12 é recomendado.')
    os.chdir(ROOT)
    from core.app_identity import register_windows_identity
    register_windows_identity()
    from core.elevation import require_admin
    if not require_admin():return
    executable=prepare()
    windowless=executable.with_name('pythonw.exe')
    if os.name=='nt' and windowless.exists():executable=windowless
    subprocess.Popen([str(executable),str(ROOT/'main.py')],cwd=str(ROOT),
        creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))


if __name__=='__main__':
    try:main()
    except Exception as error:
        if os.name=='nt':
            import ctypes
            ctypes.windll.user32.MessageBoxW(None,str(error),'DIEF JARVIS · Inicialização',0x10)
        else:raise
