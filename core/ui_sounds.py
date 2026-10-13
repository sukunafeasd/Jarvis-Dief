"""Original low-volume UI cues, separate from speech playback."""
import math
import os
import struct
import time
import wave
from pathlib import Path
from PyQt6.QtCore import QObject, QUrl, QStandardPaths, QTimer
try:
    from PyQt6.QtMultimedia import QSoundEffect
except ImportError:
    QSoundEffect=None

TONES = {
    'click': (820, 1040), 'projection': (360, 540), 'pin': (660, 880),
    'startup': (220, 330, 440), 'refresh-start': (440, 550),
    'refresh-complete': (660, 880, 1100), 'warning': (440, 330),
    'rest': (330, 220), 'awake': (440, 660), 'space': (165, 220, 330),
    'toggle': (620, 930), 'navigation': (520, 780), 'listening': (490, 735),
    'thinking': (280, 420), 'music-start': (440, 660, 880), 'music-pause': (660, 440),
    'ambient': (110,),
}


def cue_pcm(name, rate=22050):
    tones=TONES[name];frames=[]
    if name=='ambient':
        count=rate*6
        for i in range(count):
            t=i/rate
            envelope=math.sin(math.pi*i/count)**2
            value=.12*envelope*(math.sin(2*math.pi*110*t)+.35*math.sin(2*math.pi*165*t))
            frames.append(struct.pack('<h',int(value*32767)))
        return b''.join(frames)
    length=.045 if name=='click' else .085 if name in ('toggle','navigation','listening','thinking') else .14
    for frequency in tones:
        count=int(rate*length)
        for i in range(count):
            envelope=math.sin(math.pi*i/count)**2
            phase=2*math.pi*(frequency*i/rate+18*(i/rate)**2)
            value=.36*envelope*(math.sin(phase)+.18*math.sin(2*phase)+.06*math.sin(3*phase))
            frames.append(struct.pack('<h',int(value*32767)))
    return b''.join(frames)


class SoundDirector(QObject):
    def __init__(self,parent):
        super().__init__(parent)
        self.enabled=QSoundEffect is not None and os.environ.get('QT_QPA_PLATFORM')!='offscreen'
        self.effects={};self.last={};self.last_any=0;self.speaking=False
        self.visible=False;self.resting=False;self.music=False;self.music_at=0
        self.active_cue=None;self.active_priority=0
        self.ambient_timer=QTimer(self);self.ambient_timer.timeout.connect(self._ambience)
        self.ambient_timer.start(2000)
        if not self.enabled:return
        root=Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.CacheLocation))/'dief-ui-sounds-v2'
        try:
            root.mkdir(parents=True,exist_ok=True)
            for name in TONES:
                path=root/(name+'.wav')
                if not path.exists():
                    with wave.open(str(path),'wb') as output:
                        output.setnchannels(1);output.setsampwidth(2);output.setframerate(22050)
                        output.writeframes(cue_pcm(name))
                effect=QSoundEffect(self);effect.setSource(QUrl.fromLocalFile(str(path)))
                effect.setVolume(.22);self.effects[name]=effect
                if name=='ambient':effect.setLoopCount(QSoundEffect.Loop.Infinite.value)
        except OSError:
            self.enabled=False

    def play(self,name):
        now=time.monotonic()
        if not self.enabled or name not in self.effects:return False
        if now-self.last.get(name,0)<(.12 if name=='click' else .8) or now-self.last_any<.09:return False
        self.last[name]=now;self.last_any=now
        if name=='ambient':return False
        priority=3 if name in ('warning','refresh-complete') else 1 if name in ('click','toggle','navigation') else 2
        active=self.effects.get(self.active_cue)
        if active and active.isPlaying():
            if self.active_priority>priority:return False
            active.stop()
        self.active_cue=name;self.active_priority=priority
        effect=self.effects[name];effect.setVolume(.055 if self.speaking else .22);effect.play()
        return True

    def voice(self,speaking):
        self.speaking=bool(speaking)
        for name,effect in self.effects.items():
            if name!='ambient':effect.setVolume(.055 if self.speaking else .22)
        self._ambience()

    def scene(self,visible=None,resting=None):
        if visible is not None:self.visible=bool(visible)
        if resting is not None:self.resting=bool(resting)
        self._ambience()

    def media(self,playback):
        playing=isinstance(playback,dict) and playback.get('is_playing') is True
        if playing!=self.music:self.play('music-start' if playing else 'music-pause')
        self.music=playing;self.music_at=time.monotonic()
        self._ambience()

    def _ambience(self):
        effect=self.effects.get('ambient')
        if not effect:return
        # Never add an artificial beat or compete with speech/confirmed music.
        playing=self.music
        if not self.enabled or not self.visible or self.speaking or playing:
            effect.stop();return
        effect.setVolume(.025 if self.resting else .055)
        if not effect.isPlaying():effect.play()

    def stop(self):
        self.visible=False
        for effect in self.effects.values():effect.stop()
