"""Original low-volume UI cues, separate from speech playback."""
import json
import os
import time
import wave
import numpy as np
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
        i=np.arange(count,dtype=np.float64);t=i/rate
        envelope=np.sin(np.pi*i/count)**2
        value=.12*envelope*(np.sin(2*np.pi*110*t)+.35*np.sin(2*np.pi*165*t))
        return (value*32767).astype('<i2').tobytes()
    length=.045 if name=='click' else .085 if name in ('toggle','navigation','listening','thinking') else .14
    for frequency in tones:
        count=int(rate*length)
        i=np.arange(count,dtype=np.float64)
        envelope=np.sin(np.pi*i/count)**2
        phase=2*np.pi*(frequency*i/rate+18*(i/rate)**2)
        value=.36*envelope*(np.sin(phase)+.18*np.sin(2*phase)+.06*np.sin(3*phase))
        frames.append((value*32767).astype('<i2').tobytes())
    return b''.join(frames)


class SoundDirector(QObject):
    def __init__(self,parent,config_path=None):
        super().__init__(parent)
        self.enabled=QSoundEffect is not None and os.environ.get('QT_QPA_PLATFORM')!='offscreen'
        if config_path is None:
            from memory.config_manager import CONFIG_FILE
            config_path=CONFIG_FILE
        try:
            cfg=json.loads(Path(config_path).read_text(encoding='utf-8'))
            self.muted=isinstance(cfg,dict) and cfg.get('panel_sounds_muted') is True
        except (OSError,ValueError):
            self.muted=False
        self.effects={};self.last={};self.last_any=0;self.speaking=False
        self.visible=False;self.resting=False;self.music=False;self.music_at=0
        self.suspended=False;self.closed=False
        self.active_cue=None;self.active_priority=0
        self.ambient_timer=QTimer(self);self.ambient_timer.timeout.connect(self._ambience)
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
        if self.enabled:self.ambient_timer.start(2000)

    def play(self,name):
        now=time.monotonic()
        if self.closed or self.suspended or not self.enabled or self.muted or self.speaking or name not in self.effects:return False
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

    def set_muted(self,muted):
        """Mute panel audio without changing capability, scene or other audio."""
        self.muted=bool(muted)
        if self.muted:
            for effect in self.effects.values():effect.stop()
            self.active_cue=None;self.active_priority=0
            self.last.clear();self.last_any=0
        else:
            self._ambience()

    def voice(self,speaking):
        self.speaking=bool(speaking)
        if self.speaking:
            for effect in self.effects.values():effect.stop()
            self.active_cue=None;self.active_priority=0
        for name,effect in self.effects.items():
            if name!='ambient':effect.setVolume(.055 if self.speaking else .22)
        self._ambience()

    def scene(self,visible=None,resting=None):
        if self.closed:return
        if visible is False:
            self.stop()
            return
        if visible is not None:self.visible=bool(visible)
        if visible:
            self.suspended=False
            if self.enabled and not self.ambient_timer.isActive():self.ambient_timer.start(2000)
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
        if self.closed or self.suspended or not self.enabled or self.muted or not self.visible or self.speaking or playing:
            effect.stop();return
        effect.setVolume(.025 if self.resting else .055)
        if not effect.isPlaying():effect.play()

    def stop(self):
        self.visible=False
        self.suspended=True
        self.ambient_timer.stop()
        self.active_cue=None;self.active_priority=0
        for effect in self.effects.values():effect.stop()

    def close(self):
        self.closed=True
        self.stop()
