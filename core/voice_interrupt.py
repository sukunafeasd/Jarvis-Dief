"""Sustained local speech evidence; loudness alone never cancels playback."""
from collections import deque
import numpy as np


class VoiceInterruptGate:
    def __init__(self,vad=None):
        if vad is None:
            try:
                import webrtcvad
                vad=webrtcvad.Vad(2)
            except ImportError:
                vad=None
        self.vad=vad
        self.noise_floor=.012
        self._partial=b''
        self._candidate=deque(maxlen=16)
        self._duration=0.
        self._latched=False

    @property
    def available(self):
        return self.vad is not None

    @property
    def threshold(self):
        return max(.07,min(.20,self.noise_floor*2.6+.025))

    def reset(self):
        self._partial=b'';self._candidate.clear();self._duration=0.;self._latched=False

    def _speech_fraction(self,pcm,sample_rate):
        if self.vad is None or sample_rate!=16000:return 0.
        self._partial+=pcm
        size=640  # 20 ms, PCM16 mono at 16 kHz.
        frames=[]
        while len(self._partial)>=size:
            frame,self._partial=self._partial[:size],self._partial[size:]
            frames.append(bool(self.vad.is_speech(frame,sample_rate)))
        return sum(frames)/len(frames) if frames else 0.

    def observe_ambient(self,samples,level,sample_rate=16000):
        try:
            if self._speech_fraction(np.asarray(samples,dtype=np.int16).tobytes(),sample_rate)<.5:
                self.noise_floor+=.015*(min(.12,max(0.,level))-self.noise_floor)
        except Exception:
            self._partial=b''

    def feed(self,samples,sample_rate,level,distinct_from_echo,required_blocks=5):
        if self._latched:return None
        try:
            pcm=np.asarray(samples,dtype=np.int16).tobytes()
            speech=self._speech_fraction(pcm,sample_rate)
        except Exception:
            self.reset();return None
        if level<self.threshold or not distinct_from_echo or speech<.66:
            self._candidate.clear();self._duration=0.
            return None
        self._candidate.append(pcm)
        self._duration+=len(pcm)/(sample_rate*2)
        required=max(.28,min(.85,max(1,required_blocks)*.064))
        if self._duration<required:return None
        self._latched=True
        return list(self._candidate)
