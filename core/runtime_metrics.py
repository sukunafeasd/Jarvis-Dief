"""Bounded, content-free measurements. Unknown usage/cost is never reported as zero."""
from collections import deque
from threading import RLock
import time

_lock=RLock()
_events=deque(maxlen=256)


def record(component, started, outcome, **values):
    event={'component':component,'seconds':round(max(0,time.monotonic()-started),4),
           'outcome':outcome,'at':time.time()}
    for key in ('model','tier','input_tokens','output_tokens','estimated_cost','first_audio_seconds'):
        if key in values:event[key]=values[key]
    with _lock:_events.append(event)


def snapshot():
    with _lock:return {'events':[dict(event) for event in _events],
                      'scope':'current_process','contains_content':False}
