"""Bounded tail replay filtering across server turn boundaries, before synthesis."""
import re


class TranscriptReplay:
    LIMIT=12800
    MIN_MATCH=12

    def __init__(self):self.reset()

    @staticmethod
    def normalized(text):return re.sub(r'\s+',' ',text).strip()

    def reset(self):
        self.previous='';self.current='';self.pending='';self.matching=False

    def feed(self,text):
        if not self.matching:
            self.current=(self.current+text)[-self.LIMIT:]
            return text
        self.pending+=text
        candidate=self.normalized(self.pending)
        if len(self.pending)<=self.LIMIT and candidate:
            starts=[match.start() for match in re.finditer(r'(?<!\S)'+re.escape(candidate[:1]),self.previous)]
            matches=[self.previous[start:] for start in starts if self.previous.startswith(candidate,start)]
            if matches:
                terminal=not (candidate[-1].isalnum() or candidate[-1]=='_') or self.pending[-1:].isspace()
                if len(candidate)>=self.MIN_MATCH and candidate in matches and terminal:
                    self.pending='';self.matching=False
                return ''
            completed=[self.previous[start:] for start in starts
                       if len(self.previous)-start>=self.MIN_MATCH and candidate.startswith(self.previous[start:])
                       and (not (self.previous[-1].isalnum() or self.previous[-1]=='_')
                            or not (candidate[len(self.previous)-start].isalnum() or candidate[len(self.previous)-start]=='_'))]
            if completed:
                prefix=max(completed,key=len)
                match=re.match(r'\s*'+r'\s+'.join(re.escape(word) for word in prefix.split()),self.pending)
                if match:
                    text=self.pending[match.end():];self.pending='';self.matching=False
                    self.current=(self.current+text)[-self.LIMIT:]
                    return text
        elif not candidate and len(self.pending)<=self.LIMIT:
            return ''
        text=self.pending;self.pending='';self.matching=False
        self.current=(self.current+text)[-self.LIMIT:]
        return text

    def flush(self):
        text=self.pending;self.pending=''
        candidate=self.normalized(text)
        if len(candidate)>=self.MIN_MATCH and candidate in self.previous:return ''
        self.current=(self.current+text)[-self.LIMIT:]
        return text

    def finish(self):
        current=self.normalized(self.current)
        if current:self.previous=current
        self.current='';self.pending=''
        self.matching=len(self.previous)>=self.MIN_MATCH
