"""Semantic cue clock advanced by played PCM, not model generation time."""
from collections import deque
import re
import math


def valid_time(value):
    if not isinstance(value,(int,float)) or isinstance(value,bool):
        return False
    try:
        return math.isfinite(value) and value>=0
    except OverflowError:
        return False

class PresentationClock:
    MAX_PENDING=256
    def __init__(self):
        self.reset()

    def reset(self):
        self.elapsed = 0.0
        self.next_cue = 0.0
        self.pending = deque()
        self.dropped = 0
        self.active = False
        self.cancelled = False

    def enqueue(self,text, at=None, duration=None):
        if not isinstance(text,str):return
        at=at if valid_time(at) else None
        duration=duration if valid_time(duration) else None
        if text.strip():
            parts=[part.strip() for part in re.split(r'(?=\b(?:primeir[ao]|segund[ao]|terceir[ao]|quart[ao]|quint[ao]|sext[ao]|s[eé]tim[ao]|oitav[ao]|non[ao]|d[eé]cim[ao])\s+(?:not[ií]cia|manchete|tarefa|mensagem|conversa|e-mail|email|compromisso|reuni[aã]o|item|assunto)\b)',text,flags=re.I) if part.strip()]
            offset=at
            total_words=max(1,sum(len(part.split()) for part in parts))
            for index,part in enumerate(parts):
                anchored = offset is not None and (index == 0 or duration is not None and duration > 0)
                if len(self.pending)<self.MAX_PENDING:
                    self.pending.append((part[:1200],offset,anchored))
                else:
                    self.dropped+=1
                if offset is not None:
                    offset+=(duration*len(part.split())/total_words if duration is not None and duration>0
                             else max(.35,len(part.split())*.42))

    def advance(self,seconds):
        if self.cancelled or not valid_time(seconds) or seconds==0:
            return {"elapsed":self.elapsed,"cues":[]}
        self.active = True
        self.elapsed += max(0,min(.5,seconds))
        fired=[]
        while self.pending:
            due=self.pending[0][1]
            anchored=self.pending[0][2]
            target=due if anchored else max(self.next_cue,due if due is not None else 0)
            if self.elapsed < target:break
            text,at,_=self.pending.popleft()
            fired.append(text)
            duration=max(.35,len(re.findall(r"\S+",text))*.42)
            self.next_cue=self.elapsed+duration
        return {"elapsed":self.elapsed,"cues":fired,'degraded':bool(self.dropped)}

    def cancel(self):
        self.pending.clear()
        self.active=False
        self.cancelled=True

    def replace_scene(self):
        if self.cancelled:
            self.reset()
        else:
            self.pending.clear()
            self.next_cue = self.elapsed

    def resume(self):
        if self.cancelled:
            self.elapsed=0
            self.next_cue=0
        self.cancelled=False
