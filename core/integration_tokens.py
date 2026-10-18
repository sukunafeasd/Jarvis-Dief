"""Credenciais de provedores protegidas pelo usuario do Windows."""
import json
import base64
import threading
from pathlib import Path

LEGACY_ROOT=Path(__file__).resolve().parents[1]/'config'
from core.local_data import ROOT as DATA_ROOT,atomic_write,ALLOW_LEGACY
ROOT=DATA_ROOT/'secrets'
DEFAULT_ROOT=ROOT
LOCK=threading.RLock()


def read(name):
    path=ROOT/('token_'+name+'.bin')
    with LOCK:
        if ALLOW_LEGACY and ROOT==DEFAULT_ROOT and not path.exists():path=LEGACY_ROOT/path.name
        if not path.exists():return {}
        import win32crypt
        data=path.read_bytes()
        if data.startswith(b'DPAPI1\n'):data=base64.b64decode(data.split(b'\n',1)[1].strip(),validate=True)
        return json.loads(win32crypt.CryptUnprotectData(data,None,None,None,0)[1])


def write(name,value):
    import win32crypt
    with LOCK:
        path=ROOT/('token_'+name+'.bin')
        atomic_write(path,win32crypt.CryptProtectData(json.dumps(value).encode(),'Dief Jarvis '+name,None,None,None,0))


def remove(name):
    with LOCK:
        # A tombstone prevents an old pending authorization reappearing from the legacy directory.
        write(name,{})
