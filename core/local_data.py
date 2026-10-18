"""Private per-user data, separated from the executable/source directory."""
import json
import os
from pathlib import Path
import tempfile
import threading

_override=os.environ.get('DIEF_JARVIS_DATA_DIR')
_isolated=os.environ.get('QT_QPA_PLATFORM')=='offscreen'
_managed=os.environ.get('DIEF_MANAGED_ROOT')
ROOT=Path(_override) if _override else Path(tempfile.mkdtemp(prefix='dief-isolated-data-')) if _isolated else Path(_managed)/'data' if _managed else Path(os.environ.get('LOCALAPPDATA',Path.home()/'.local/share'))/'DIEF-JARVIS/data'
ALLOW_LEGACY=not (_override or _isolated)
LOCK=threading.RLock()


def atomic_write(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    handle,name=tempfile.mkstemp(prefix=path.name+'.',suffix='.tmp',dir=path.parent)
    try:
        with os.fdopen(handle,'wb') as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())
        os.replace(name,path)
    finally:Path(name).unlink(missing_ok=True)


def migrate(legacy,name):
    target=ROOT/name
    if not ALLOW_LEGACY:return target
    with LOCK:
        if not target.exists() and Path(legacy).is_file():
            data=Path(legacy).read_bytes()
            if name.endswith('.json'):
                try:
                    if not isinstance(json.loads(data),dict):return target
                except (ValueError,UnicodeDecodeError):return target
            atomic_write(target,data)
    return target
