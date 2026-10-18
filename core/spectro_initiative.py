"""Bounded suggestions from real events; this component never executes actions."""
import time
from collections import deque


class Initiative:
    def __init__(self,clock=time.monotonic):
        self.clock=clock;self.pending=deque(maxlen=6);self.seen={};self.last_spoken=-float('inf');self.quiet=False
    def offer(self,key,text,source):
        now=self.clock()
        self.seen={key:at for key,at in self.seen.items() if now-at<600}
        if key in self.seen:return
        self.seen[key]=now
        while len(self.seen)>64:self.seen.pop(next(iter(self.seen)))
        self.pending.append({'key':key,'text':text[:400],'source':source,'at':now})
    def next(self):
        now=self.clock()
        while self.pending and now-self.pending[0]['at']>120:self.pending.popleft()
        if self.quiet or now-self.last_spoken<120 or not self.pending:return None
        value=self.pending.popleft();self.last_spoken=now;return value
    def clear(self):self.pending.clear()
