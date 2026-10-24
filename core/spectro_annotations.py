"""Click-through desktop annotations anchored to observed UIA rectangles."""
import ctypes
import os
import time
from PyQt6.QtCore import Qt,QRect,QPoint,QPointF,QTimer
from PyQt6.QtGui import QPainter,QPen,QColor,QPainterPath,QFont,QFontMetrics,QGuiApplication
from PyQt6.QtWidgets import QWidget


def annotation_color(value):
    if value is None:return None
    aliases={'amarelo':'#ffe45c','vermelho':'#ff526a','verde':'#4bffa2','azul':'#48baff','roxo':'#c48aff','branco':'#ffffff'}
    value=aliases.get(str(value).lower(),str(value))
    import re
    if not re.fullmatch(r'#[0-9a-fA-F]{6}',value):raise ValueError('Use uma cor #RRGGBB ou amarelo/vermelho/verde/azul/roxo/branco.')
    return value


def exclude_capture(window):
    if os.name!='nt' or os.environ.get('QT_QPA_PLATFORM')=='offscreen':return False
    from ctypes import wintypes
    api=ctypes.WinDLL('user32',use_last_error=True)
    api.SetWindowDisplayAffinity.argtypes=[wintypes.HWND,wintypes.DWORD]
    api.SetWindowDisplayAffinity.restype=wintypes.BOOL
    return bool(api.SetWindowDisplayAffinity(int(window.winId()),0x11))


def logical_target(rect):
    from PyQt6.QtCore import QRect
    if os.name!='nt':return QRect(*rect),QGuiApplication.primaryScreen()
    import win32api
    physical=QRect(*rect);center=physical.center()
    monitor=win32api.MonitorFromPoint((center.x(),center.y()),2)
    info=win32api.GetMonitorInfo(monitor)
    screen=next((screen for screen in QGuiApplication.screens() if screen.name().casefold()==info['Device'].casefold()),None)
    left,top,right,bottom=info['Monitor']
    if screen is None:
        candidates=[item for item in QGuiApplication.screens() if
                    abs(item.geometry().width()*item.devicePixelRatio()-(right-left))<=2 and
                    abs(item.geometry().height()*item.devicePixelRatio()-(bottom-top))<=2]
        located=[item for item in candidates if item.geometry().left()==left and item.geometry().top()==top]
        screen=located[0] if len(located)==1 else candidates[0] if len(candidates)==1 else None
    if screen is None:raise ValueError('Nao consegui associar o alvo ao monitor real.')
    scale=screen.devicePixelRatio();origin=screen.geometry().topLeft()
    result=QRect(origin.x()+round((physical.x()-left)/scale),origin.y()+round((physical.y()-top)/scale),
                 round(physical.width()/scale),round(physical.height()/scale))
    if not screen.geometry().contains(result):raise ValueError('O alvo atravessa monitores; consulte uma regiao menor.')
    return result,screen


class AnnotationWindow(QWidget):
    def __init__(self,screen,core):
        super().__init__(None,Qt.WindowType.Tool|Qt.WindowType.FramelessWindowHint|Qt.WindowType.WindowStaysOnTopHint|
                         Qt.WindowType.WindowTransparentForInput|Qt.WindowType.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setGeometry(screen.geometry());self.core=core;self.target=None;self.text='';self.until=0;self.shape='outline'
        self.started=0;self.color=None;self.points=[];self._label_font=QFont('Segoe UI',11)
        self.timer=QTimer(self);self.timer.setInterval(80);self.timer.timeout.connect(self._tick)
        self.capture_excluded=False
    def present(self,rect,text,shape='outline',color=None):
        self.color=annotation_color(color)
        self.target=rect.translated(-self.x(),-self.y()) if rect is not None else None
        self.text=str(text)[:220];self.started=time.monotonic();self.until=self.started+25;self.shape=shape
        self.timer.setInterval(200 if self.core.owner.hud.motion_reduced else 50)
        self.show();self.capture_excluded=exclude_capture(self);self.timer.start();self.update()
    def _tick(self):
        if time.monotonic()>self.until:self.hide();self.timer.stop()
        else:self.update()
    def paintEvent(self,event):
        painter=QPainter(self);painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        reduced=self.core.owner.hud.motion_reduced
        elapsed=time.monotonic()-self.started
        painter.setOpacity(1 if reduced else max(0,min(1,elapsed/.24)))
        color=QColor(self.color or getattr(self.core.owner,'_spectro_color',lambda:'#54dcff')())
        if not color.isValid():color=QColor('#54dcff')
        glow=QColor(color);glow.setAlpha(45)
        painter.setPen(QPen(color,1.5))
        if self.points:
            path=QPainterPath(QPointF(*self.points[0]))
            for point in self.points[1:]:path.lineTo(QPointF(*point))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(glow,10));painter.drawPath(path)
            painter.setPen(QPen(color,3));painter.drawPath(path)
        if self.target is not None:
            target=self.target.adjusted(-4,-4,4,4)
            fill=QColor(color);fill.setAlpha(65 if self.shape=='marker' else 12)
            painter.setBrush(Qt.BrushStyle.NoBrush);painter.setPen(QPen(glow,6))
            if self.shape=='circle':painter.drawEllipse(target)
            else:painter.drawRoundedRect(target,6,6)
            if self.shape=='underline':
                painter.setPen(QPen(color,4));painter.drawLine(target.bottomLeft(),target.bottomRight())
            elif self.shape=='cross':
                painter.setPen(QPen(color,3));painter.drawLine(target.topLeft(),target.bottomRight());painter.drawLine(target.topRight(),target.bottomLeft())
            painter.setPen(QPen(color,1.5));painter.setBrush(fill)
            if self.shape=='circle':painter.drawEllipse(target)
            else:painter.drawRoundedRect(target,6,6)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            source=self.core.geometry().center()-self.pos()
            if not self.rect().contains(source):
                source=QPoint(max(12,min(self.width()-12,source.x())),max(12,min(self.height()-12,source.y())))
            if source!=target.center():
                path=QPainterPath();path.moveTo(source.x(),source.y())
                destination=QPoint(max(target.left(),min(target.right(),source.x())),max(target.top(),min(target.bottom(),source.y())))
                if destination==source:destination=target.center()
                middle=(source.x()+destination.x())/2
                path.cubicTo(middle,source.y(),middle,destination.y(),destination.x(),destination.y())
                painter.setPen(QPen(glow,5));painter.drawPath(path)
                painter.setPen(QPen(color,1.2))
                painter.drawPath(path)
                if self.shape=='arrow':
                    tip=path.pointAtPercent(1);prior=path.pointAtPercent(.97)
                    dx,dy=tip.x()-prior.x(),tip.y()-prior.y();length=max(.01,(dx*dx+dy*dy)**.5);dx/=length;dy/=length
                    painter.drawLine(tip,QPointF(tip.x()-dx*13+dy*6,tip.y()-dy*13-dx*6))
                    painter.drawLine(tip,QPointF(tip.x()-dx*13-dy*6,tip.y()-dy*13+dx*6))
                point=path.pointAtPercent(.55 if reduced else (elapsed*.4)%1)
                amplitude=max(0,min(1,float(self.core.owner.hud._amp_disp)))
                radius=2.5+(amplitude*2 if self.core.owner.hud.speaking else 0)
                painter.setBrush(color.lighter(150));painter.setPen(Qt.PenStyle.NoPen);painter.drawEllipse(point,radius,radius)
                painter.setPen(QPen(color,1.5));painter.setBrush(Qt.BrushStyle.NoBrush)
        text_rect=self.label_rect()
        painter.setFont(self._label_font);painter.setPen(QColor(0,0,0,230))
        painter.drawText(text_rect.translated(1,1),Qt.TextFlag.TextWordWrap,self.text)
        painter.setPen(color.lighter(130));painter.drawText(text_rect,Qt.TextFlag.TextWordWrap,self.text)
        painter.end()
    def label_rect(self):
        width=max(1,min(320,self.width()-24))
        measured=QFontMetrics(self._label_font).boundingRect(QRect(0,0,width,10000),Qt.TextFlag.TextWordWrap,self.text)
        height=max(24,min(measured.height()+4,max(24,self.height()-24)))
        if self.target is not None:
            x=self.target.left();y=self.target.bottom()+14
            if y+height>self.height()-12:y=self.target.top()-height-14
        else:x=self.core.x()-self.x();y=self.core.y()-self.y()-height-14
        return QRect(max(12,min(x,self.width()-width-12)),max(12,min(y,self.height()-height-12)),width,height)
    def closeEvent(self,event):self.timer.stop();super().closeEvent(event)


class Annotations:
    def __init__(self,core):self.core=core;self.layers={}
    def show_target(self,physical,text='',shape='outline',color=None):
        color=annotation_color(color)
        rect,screen=logical_target(physical);self.clear()
        layer=AnnotationWindow(screen,self.core);self.layers[screen.name()]=layer;layer.present(rect,text,shape,color)
    def update_target(self,physical,text='',shape='outline',color=None):
        color=annotation_color(color)
        rect,screen=logical_target(physical)
        layer=self.layers.get(screen.name())
        if layer is None:self.show_target(physical,text,shape,color)
        else:layer.target=rect.translated(-layer.x(),-layer.y());layer.text=text;layer.shape=shape;layer.color=annotation_color(color);layer.update()
    def note(self,text):
        self.clear();screen=self.core.screen();layer=AnnotationWindow(screen,self.core)
        self.layers[screen.name()]=layer;layer.present(None,text)
    def draw(self,points,color=None,text='',screen_name=None):
        import math
        if not isinstance(points,list) or not 2<=len(points)<=32:raise ValueError('Informe de 2 a 32 pontos normalizados.')
        if any(not isinstance(p,(list,tuple)) or len(p)!=2 or any(type(v) not in (int,float) or not math.isfinite(v) or not 0<=v<=1 for v in p) for p in points):raise ValueError('Cada ponto deve conter x,y entre 0 e 1.')
        color=annotation_color(color)
        screen=next((s for s in QGuiApplication.screens() if s.name()==screen_name),None) if screen_name else self.core.screen()
        if screen is None:raise ValueError('Monitor nao encontrado.')
        self.clear();layer=AnnotationWindow(screen,self.core);self.layers[screen.name()]=layer
        layer.points=[(p[0]*(layer.width()-1),p[1]*(layer.height()-1)) for p in points]
        layer.present(None,text,'path',color)
    def clear(self):
        for layer in self.layers.values():layer.close();layer.deleteLater()
        self.layers={}
    def snapshot(self):
        visible=[layer for layer in self.layers.values() if layer.isVisible()]
        return {'count':len(visible),'click_through':True,'items':[
            {'screen':layer.screen().name(),'shape':layer.shape,'color':layer.color,'text':layer.text,'points':layer.points,
             'bounds':[layer.target.x()+layer.x(),layer.target.y()+layer.y(),layer.target.width(),layer.target.height()] if layer.target is not None else None}
            for layer in visible]}
