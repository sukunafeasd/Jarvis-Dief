"""Continuidade visual nativa enquanto os shaders do observatorio aquecem."""
import time
from pathlib import Path
from PyQt6.QtCore import Qt,QPointF,QPropertyAnimation,QEasingCurve,QTimer,pyqtProperty
from PyQt6.QtGui import QPainter,QPixmap
from PyQt6.QtWidgets import QWidget
from core.fui_paint import paint_core


class OpeningVeil(QWidget):
    def __init__(self,parent):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.background=QPixmap(str(Path(__file__).parent/'spatial/assets/deep-space.png'))
        self.cached=QPixmap();self.alpha=1.;self.started=time.monotonic();self.released=False
        self.timer=QTimer(self);self.timer.timeout.connect(self.update);self.timer.start(50)
        self.fade=QPropertyAnimation(self,b'opacity',self);self.fade.setDuration(280)
        self.fade.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.fade.finished.connect(self.hide)

    @pyqtProperty(float)
    def opacity(self):return self.alpha

    @opacity.setter
    def opacity(self,value):self.alpha=value;self.update()

    def release(self):
        if self.released:return
        self.released=True;self.fade.setStartValue(1.);self.fade.setEndValue(0.);self.fade.start()

    def resizeEvent(self,event):
        self.cached=self.background.scaled(self.size(),Qt.AspectRatioMode.KeepAspectRatioByExpanding,Qt.TransformationMode.SmoothTransformation)
        super().resizeEvent(event)

    def hideEvent(self,event):self.timer.stop();super().hideEvent(event)

    def showEvent(self,event):
        if not self.released:self.timer.start(50)
        super().showEvent(event)

    def paintEvent(self,event):
        painter=QPainter(self);painter.setOpacity(self.alpha)
        painter.fillRect(self.rect(),Qt.GlobalColor.black)
        if not self.cached.isNull():painter.drawPixmap((self.width()-self.cached.width())//2,(self.height()-self.cached.height())//2,self.cached)
        # A distant hub is always present, including when WebGL cannot start.
        paint_core(painter,QPointF(self.width()/2,self.height()/2),min(self.width(),self.height())*.065,time.monotonic()-self.started)
        painter.end()
