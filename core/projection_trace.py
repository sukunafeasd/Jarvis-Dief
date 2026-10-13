"""Short, input-transparent projection cue; no permanent animation loop."""
import time
from PyQt6.QtCore import QPointF, Qt, QTimer
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QWidget


class ProjectionTrace(QWidget):
    def __init__(self,parent):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setAccessibleName('')
        self.timer=QTimer(self)
        self.timer.setInterval(24)
        self.timer.timeout.connect(self._tick)
        self.hide()

    def begin(self,source,target,color,compact=False):
        self.source=QPointF(source);self.target=QPointF(target)
        self.color=QColor(color);self.started=time.monotonic()
        self.duration=.42 if compact else .64
        self.setGeometry(self.parentWidget().rect())
        self.show();self.raise_();self.timer.start();self.update()

    def _tick(self):
        if time.monotonic()-self.started>=self.duration:
            self.stop()
        else:
            self.update()

    def stop(self):
        self.timer.stop();self.hide()

    def paintEvent(self,event):
        progress=min(1,(time.monotonic()-self.started)/self.duration)
        painter=QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path=QPainterPath(self.source)
        dx=self.target.x()-self.source.x()
        path.cubicTo(self.source+QPointF(dx*.3,-35),self.target-QPointF(dx*.25,18),self.target)
        color=QColor(self.color);color.setAlphaF(.20*(1-progress))
        painter.setPen(QPen(color,1));painter.drawPath(path)
        for i in range(8):
            phase=max(0,min(1,progress*1.4-i*.065))
            if phase<=0 or phase>=1:
                continue
            point=path.pointAtPercent(phase)
            color=QColor(self.color);color.setAlphaF(.55*(1-progress))
            painter.setPen(Qt.PenStyle.NoPen);painter.setBrush(color)
            painter.drawEllipse(point,1.8,1.8)
        painter.end()
