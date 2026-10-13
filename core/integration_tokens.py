"""Credenciais de provedores protegidas pelo usuario do Windows."""
import json
import threading
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]/'config'
LOCK=threading.RLock()


def read(name):
    path=ROOT/('token_'+name+'.bin')
    with LOCK:
        if not path.exists():return {}
        import win32crypt
        return json.loads(win32crypt.CryptUnprotectData(path.read_bytes(),None,None,None,0)[1])


def write(name,value):
    import win32crypt
    with LOCK:
        ROOT.mkdir(parents=True,exist_ok=True)
        path=ROOT/('token_'+name+'.bin');temporary=path.with_suffix('.tmp')
        temporary.write_bytes(win32crypt.CryptProtectData(json.dumps(value).encode(),
            'Dief Jarvis '+name,None,None,None,0))
        temporary.replace(path)


def remove(name):
    with LOCK:(ROOT/('token_'+name+'.bin')).unlink(missing_ok=True)
