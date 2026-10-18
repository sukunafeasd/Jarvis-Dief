"""Preparacao neutra, sem substituir o nucleo verdadeiro por outro desenho."""
import time
from PyQt6.QtCore import Qt,QRectF,QPropertyAnimation,QEasingCurve,QTimer,pyqtProperty
from PyQt6.QtGui import QPainter,QColor,QFont
from PyQt6.QtWidgets import QWidget


class OpeningVeil(QWidget):
    def __init__(self,parent):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.alpha=1.;self.started=time.monotonic();self.released=False
        self.hub_visible=True
        self.error=None
        self.timer=QTimer(self);self.timer.timeout.connect(self.update);self.timer.start(50)
        self.fade=QPropertyAnimation(self,b'opacity',self);self.fade.setDuration(280)
        self.fade.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.fade.finished.connect(self.hide)

    @pyqtProperty(float)
    def opacity(self):return self.alpha

    @opacity.setter
    def opacity(self,value):self.alpha=value;self.update()

    def release(self):
        if self.released or self.error:return
        self.released=True;self.fade.setStartValue(1.);self.fade.setEndValue(0.);self.fade.start()

    def fail(self):
        self.error='Nao foi possivel preparar a cena 3D. Reabra o Jarvis.'
        self.fade.stop();self.alpha=1.;self.released=False;self.show();self.raise_()
        self.timer.stop();self.update()

    def hideEvent(self,event):self.timer.stop();super().hideEvent(event)

    def showEvent(self,event):
        if not self.released:self.timer.start(50)
        super().showEvent(event)

    def paintEvent(self,event):
        painter=QPainter(self);painter.setOpacity(self.alpha)
        painter.fillRect(self.rect(),QColor('#03060b'))
        painter.setPen(QColor('#bcd9e3'));painter.setFont(QFont('Segoe UI',12))
        painter.drawText(QRectF(0,self.height()/2-30,self.width(),24),Qt.AlignmentFlag.AlignCenter,'DIEF JARVIS')
        painter.setPen(QColor('#77939f'));painter.setFont(QFont('Segoe UI',9))
        painter.drawText(QRectF(12,self.height()/2,self.width()-24,48),Qt.AlignmentFlag.AlignCenter|Qt.TextFlag.TextWordWrap,self.error or 'Preparando o observatorio')
        if self.error:painter.end();return
        width=min(180,self.width()*.4);x=(self.width()-width)/2;y=self.height()/2+38
        painter.fillRect(QRectF(x,y,width,2),QColor('#16313b'))
        phase=((time.monotonic()-self.started)*.55)%1
        painter.fillRect(QRectF(x+phase*width*.65,y,width*.35,2),QColor('#56c9dc'))
        painter.end()
