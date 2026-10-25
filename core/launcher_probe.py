"""Offline bootstrap smoke check used before accepting a replacement EXE."""
import hashlib
from pathlib import Path
import re
import sys


def run(root, nonce):
    if not re.fullmatch(r'[a-f0-9]{32}',nonce):raise ValueError('Identificador de teste invalido.')
    import tkinter
    from core.fui_bootstrap import BootstrapSurface
    window=tkinter.Tk()
    try:
        window.withdraw()
        BootstrapSurface(window,reduced=True)
        window.update_idletasks()
    finally:
        window.destroy()
    sessions=Path(root)/'sessions'
    sessions.mkdir(parents=True,exist_ok=True)
    (sessions/('launcher-'+nonce+'.ready')).write_text(
        hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest(),encoding='ascii')
    return 0
