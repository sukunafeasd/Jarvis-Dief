"""Local cached glass material for native floating previews and workspace panels."""
from PyQt6.QtCore import Qt, QEvent, QPropertyAnimation, pyqtProperty
from PyQt6.QtGui import QColor, QFontDatabase, QLinearGradient, QPainter, QPen, QRegion
from PyQt6.QtWidgets import QFrame
from pathlib import Path
import os
import math
from core.fui_paint import glass_plate


def paint_hud_light(painter, width, height, phase, header=7):
    """Moving light is confined to frame conductors, never placed over labels."""
    painter.save()
    x = 24 + max(0, width-48)*phase
    beam = QLinearGradient(x-35, header, x+35, header)
    beam.setColorAt(0, QColor(40,220,255,0)); beam.setColorAt(.5,QColor(160,250,255,210)); beam.setColorAt(1,QColor(40,220,255,0))
    for stroke in (7,3,1):
        painter.setOpacity(.18 if stroke==7 else .4 if stroke==3 else 1)
        painter.setPen(QPen(beam,stroke))
        painter.drawLine(max(18,round(x-35)),header,min(width-18,round(x+35)),header)
    y = 24 + max(0,height-48)*((phase+.37)%1)
    beam = QLinearGradient(width-7,y-28,width-7,y+28)
    beam.setColorAt(0,QColor(255,65,85,0));beam.setColorAt(.5,QColor(255,105,125,180));beam.setColorAt(1,QColor(255,65,85,0))
    painter.setOpacity(.6);painter.setPen(QPen(beam,3))
    painter.drawLine(width-7,max(18,round(y-28)),width-7,min(height-18,round(y+28)))
    painter.setOpacity(1)
    painter.setPen(QPen(QColor(255,88,108,round(105+70*math.sin(phase*math.tau)**2)),1.5))
    painter.drawLine(6,17,17,6)
    painter.drawLine(width-17,height-6,width-6,height-17)
    x=width-24-max(0,width-48)*phase
    beam=QLinearGradient(x-42,height-6,x+42,height-6)
    beam.setColorAt(0,QColor(93,112,255,0));beam.setColorAt(.5,QColor(170,185,255,220));beam.setColorAt(1,QColor(93,112,255,0))
    painter.setPen(QPen(beam,2));painter.drawLine(max(16,round(x-42)),height-6,min(width-16,round(x+42)),height-6)
    y=height-24-max(0,height-48)*phase
    beam=QLinearGradient(6,y-26,6,y+26)
    beam.setColorAt(0,QColor(44,237,255,0));beam.setColorAt(.5,QColor(140,248,255,200));beam.setColorAt(1,QColor(44,237,255,0))
    painter.setPen(QPen(beam,2));painter.drawLine(6,max(16,round(y-26)),6,min(height-16,round(y+26)))
    painter.restore()


class HudGlassFrame(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setProperty('independentTheme',True)
        if 'Segoe UI' not in QFontDatabase.families():
            fonts = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts'
            for name in ('segoeui.ttf', 'seguisb.ttf'):
                if (fonts / name).exists():
                    QFontDatabase.addApplicationFont(str(fonts / name))
        self._plate = None
        self._plate_key = None
        self._accent='#53daef'
        self._motion_reduced = False
        self._light_phase = 0.0
        self._motion_window = None
        self._light = QPropertyAnimation(self,b'lightPhase',self)
        self._light.setDuration(5600);self._light.setStartValue(0.0);self._light.setEndValue(1.0);self._light.setLoopCount(-1)

    @pyqtProperty(float)
    def lightPhase(self):
        return self._light_phase

    @lightPhase.setter
    def lightPhase(self, value):
        self._light_phase = value
        if not self._can_animate():
            self.suspend_motion()
            return
        self.update(QRegion(self.rect()).subtracted(QRegion(self.rect().adjusted(16,16,-16,-16))))

    def set_motion_reduced(self, reduced):
        self._motion_reduced = bool(reduced)
        if reduced:
            self.suspend_motion(); self._light_phase=0.0; self.update()
        else:
            self.resume_motion()

    def set_accent(self,color):
        if QColor(color).isValid():self._accent=color;self._plate_key=None;self.update()

    def resume_motion(self):
        proxy=self.graphicsProxyWidget()
        views=proxy.scene().views() if proxy and proxy.scene() else []
        window=views[0].window() if views else self.window()
        if self._motion_window is not window:
            if self._motion_window is not None: self._motion_window.removeEventFilter(self)
            self._motion_window=window;window.installEventFilter(self)
        if not self._motion_reduced and self._can_animate():
            if self._light.state()!=QPropertyAnimation.State.Running:
                self._light.start()

    def _can_animate(self):
        proxy=self.graphicsProxyWidget()
        if proxy and proxy.scene():
            return self.isVisible() and any(view.isVisible() and not view.window().isMinimized() for view in proxy.scene().views())
        return self.isVisible() and not self.window().isMinimized()

    def suspend_motion(self):
        self._light.stop()

    def showEvent(self, event):
        super().showEvent(event)
        self.resume_motion()

    def hideEvent(self, event):
        self.suspend_motion(); super().hideEvent(event)

    def eventFilter(self, watched, event):
        if watched is self._motion_window and event.type()==QEvent.Type.WindowStateChange:
            if watched.isMinimized(): self.suspend_motion()
            else: self.resume_motion()
        return super().eventFilter(watched,event)

    def paintEvent(self, event):
        super().paintEvent(event)
        key = (self.width(), self.height(), min(self.devicePixelRatioF(), 1.5),self._accent)
        if key != self._plate_key:
            self._plate_key = key
            w, h, scale,accent = key
            self._plate=glass_plate(w,h,scale,accent)
        painter = QPainter(self)
        painter.drawPixmap(0, 0, self._plate)
        if not self._motion_reduced:
            paint_hud_light(painter,self.width(),self.height(),self._light_phase)
        painter.end()


class PinnedPreviewFrame(HudGlassFrame):
    def __init__(self,parent=None):
        super().__init__(parent)
        self._semantic={}

    def set_semantic(self,data):
        from core.observatory_theme import ACCENTS
        self._semantic={'kind':data.get('kind'),'code':data.get('code',-1),'rain':data.get('rain',0),'day':data.get('is_day',1)}
        self.set_accent(ACCENTS.get(data.get('kind'),'#8dcaff'))

    @pyqtProperty(float)
    def lightPhase(self):return self._light_phase

    @lightPhase.setter
    def lightPhase(self,value):
        self._light_phase=value
        if self._can_animate():
            if self._semantic.get('kind')=='weather':self.update()
            else:self.update(QRegion(self.rect()).subtracted(QRegion(self.rect().adjusted(18,18,-18,-18))))
        else:self.suspend_motion()

    def paintEvent(self,event):
        from core.observatory_theme import optical_plate
        QFrame.paintEvent(self,event)
        key=(self.width(),self.height(),min(1.5,self.devicePixelRatioF()),self._accent)
        if key!=self._plate_key:self._plate_key=key;self._plate=optical_plate(*key)
        painter=QPainter(self)
        painter.drawPixmap(0,0,self._plate)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        accent=QColor(self._accent);accent.setAlpha(105);painter.setPen(QPen(accent,1))
        if self._semantic:painter.drawLine(16,38,max(16,self.width()-16),38)
        t=0 if self._motion_reduced else self._light_phase
        x=15+(self.width()-30)*t
        beam=QLinearGradient(x-40,6,x+40,6)
        beam.setColorAt(0,QColor(126,186,255,0));beam.setColorAt(.5,QColor(218,239,255,200));beam.setColorAt(1,QColor(126,186,255,0))
        for width,opacity in ((8,.16),(4,.32),(1.5,1)):
            painter.setOpacity(opacity);painter.setPen(QPen(beam,width));painter.drawLine(max(20,round(x-40)),6,min(self.width()-20,round(x+40)),6)
        painter.setOpacity(1)
        painter.setPen(QPen(beam,2));painter.drawLine(max(20,round(x-40)),self.height()-6,min(self.width()-20,round(x+40)),self.height()-6)
        kind=self._semantic.get('kind')
        if kind=='weather' and isinstance(self._semantic.get('code'),(int,float)) and self._semantic['code']>=51:
            painter.setPen(QPen(QColor(91,175,255,40),1))
            snow=self._semantic['code'] in (71,73,75,77,85,86)
            for i in range(20):
                x=18+(i*37)%max(1,self.width()-36);y=48+(i*19+t*(65 if snow else 180))%max(1,self.height()-60)
                if snow:painter.drawPoint(round(x),round(y))
                else:painter.drawLine(round(x),round(y),round(x-3),round(min(self.height()-12,y+9)))
        elif kind in ('system','tasks','calendar','gmail','whatsapp','memory','news','files','search','data'):
            accent.setAlpha(120);painter.setPen(QPen(accent,2))
            pace={'tasks':1,'calendar':.45,'gmail':.75,'whatsapp':1.3,'system':1.6,'news':.6}.get(kind,.8)
            span=max(1,self.width()-32)
            for i in range(4):
                x=16+span*((t*pace+i/4)%1)
                painter.drawLine(round(x),self.height()-8,min(self.width()-14,round(x+9)),self.height()-8)
        painter.end()
