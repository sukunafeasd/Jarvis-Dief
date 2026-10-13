"""Diagnosticos locais: pilhas e tipos de erro, nunca mensagens ou variaveis."""
import faulthandler
import os
import sys
import threading
import traceback
from datetime import datetime,timezone
from pathlib import Path

_sink=None
_lock=threading.Lock()


def record_fault(kind,tb):
    if _sink is None:return
    frames=traceback.extract_tb(tb)
    lines=[datetime.now(timezone.utc).isoformat()+' '+kind.__name__]
    lines.extend(f'{Path(frame.filename).name}:{frame.lineno} {frame.name}' for frame in frames)
    try:
        with _lock:
            _sink.write('\n'.join(lines)+'\n');_sink.flush()
    except (OSError,ValueError):pass


def install():
    global _sink
    if _sink is not None:return
    folder=Path(os.environ.get('LOCALAPPDATA',Path.home()/'.local'))/'DIEF JARVIS'/'logs'
    try:
        folder.mkdir(parents=True,exist_ok=True)
        _sink=(folder/'runtime-faults.log').open('a',encoding='utf-8')
        faulthandler.enable(file=_sink,all_threads=True)
    except (OSError,RuntimeError):return
    previous=sys.excepthook
    def python_fault(kind,error,tb):
        record_fault(kind,tb)
        previous(kind,error,tb)
    sys.excepthook=python_fault
    previous_thread=threading.excepthook
    def thread_fault(args):
        record_fault(args.exc_type,args.exc_traceback)
        previous_thread(args)
    threading.excepthook=thread_fault
