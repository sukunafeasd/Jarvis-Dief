"""Native FUI material and hologram shared by entry, setup and settings."""
import math
from PyQt6.QtCore import Qt,QPointF,QRectF
from PyQt6.QtGui import QColor,QPainter,QPen,QRadialGradient
from core.fui_geometry import core_lines,RED,CYAN


def glass_plate(width,height,scale=1,accent='#53daef'):
    from core.observatory_theme import optical_plate
    return optical_plate(width,height,scale,accent)

def paint_core(painter,center,radius,seconds):
    painter.save();painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    cx,cy=center.x(),center.y()
    halo=QRadialGradient(center,radius*1.3)
    halo.setColorAt(0,QColor(255,92,68,100));halo.setColorAt(.68,QColor(255,44,62,22));halo.setColorAt(1,QColor(0,0,0,0))
    painter.setPen(Qt.PenStyle.NoPen);painter.setBrush(halo);painter.drawEllipse(center,radius*1.3,radius*1.3)
    lines,vertices=core_lines(seconds)
    for a,b,kind in sorted(lines,key=lambda line:line[0][2]+line[1][2]):
        depth=(a[2]+b[2])*.5
        color=QColor('#ffb095' if kind=='heart' else RED)
        color.setAlpha(round(155+80*max(0,depth)) if kind=='heart' else round(55+115*(depth+1)/2))
        if kind=='heart':
            glow=QColor('#ff735d');glow.setAlpha(24);painter.setPen(QPen(glow,3))
            painter.drawLine(QPointF(cx+a[0]*radius,cy+a[1]*radius),QPointF(cx+b[0]*radius,cy+b[1]*radius))
        painter.setPen(QPen(color,1 if kind=='heart' else .8))
        painter.drawLine(QPointF(cx+a[0]*radius,cy+a[1]*radius),QPointF(cx+b[0]*radius,cy+b[1]*radius))
    for i,point in enumerate(vertices):
        if i%5:continue
        x,y,z=point;color=QColor('#ff7b6a');color.setAlpha(round(75+130*(z+1)/2))
        painter.setPen(Qt.PenStyle.NoPen);painter.setBrush(color)
        painter.drawEllipse(QPointF(cx+x*radius,cy+y*radius),1.3,1.3)
    heart=QRadialGradient(center,radius*.31)
    heart.setColorAt(0,QColor(255,224,188,190));heart.setColorAt(.20,QColor(255,109,87,105));heart.setColorAt(1,QColor(255,51,62,0))
    painter.setBrush(heart);painter.drawEllipse(center,radius*.31,radius*.31)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    for i in range(3):
        r=radius*(1.04+i*.09)
        painter.setPen(QPen(QColor(255,74,88,190-i*30),1.8))
        painter.drawArc(QRectF(cx-r,cy-r,r*2,r*2),int((seconds*7+i*120)*16),int(65*16))
    painter.setPen(QPen(QColor(CYAN),.7))
    painter.drawEllipse(QRectF(cx-radius*1.22,cy-radius*.28,radius*2.44,radius*.56))
    for i in range(3):
        a=seconds*.16+i*math.tau/3
        node=QPointF(cx+math.cos(a)*radius*1.22,cy+math.sin(a)*radius*.28)
        painter.setBrush(QColor('#ffd7bb'));painter.drawEllipse(node,2.2,2.2)
    painter.setBrush(Qt.BrushStyle.NoBrush);painter.setPen(QPen(QColor(72,209,230,100),.8))
    painter.drawEllipse(QRectF(cx-radius*1.12,cy+radius*1.26,radius*2.24,9))
    painter.restore()


def paint_entry_core(painter,center,radius,seconds):
    from core.fui_geometry import entry_lines
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    for size,alpha in ((1.2,55),(.7,90),(.32,200)):
        glow=QRadialGradient(center,radius*size)
        glow.setColorAt(0,QColor(255,165,120,alpha))
        glow.setColorAt(.35,QColor(255,55,75,alpha//2))
        glow.setColorAt(1,QColor(255,40,65,0))
        painter.setPen(Qt.PenStyle.NoPen);painter.setBrush(glow)
        painter.drawEllipse(center,radius*size,radius*size)
    lines,vertices=entry_lines(seconds)
    for a,b,kind in sorted(lines,key=lambda item:item[0][2]+item[1][2]):
        color=QColor('#b4f0ff' if kind=='orbit' else '#ffe1b8' if kind=='heart' else '#ff5262')
        color.setAlpha(210 if kind=='heart' else max(35,min(240,int(125+(a[2]+b[2])*48))))
        painter.setPen(QPen(color,1.15 if kind=='heart' else .8))
        painter.drawLine(QPointF(center.x()+a[0]*radius,center.y()+a[1]*radius),QPointF(center.x()+b[0]*radius,center.y()+b[1]*radius))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    for i in range(3):
        r=radius*(1.34+i*.08)
        painter.setPen(QPen(QColor('#32667d' if i else '#ff5262'),1.3))
        painter.drawArc(QRectF(center.x()-r,center.y()-r,2*r,2*r),int((seconds*8+i*113)*16),int((90-i*17)*16))
    for i,p in enumerate(vertices):
        if i%7:continue
        painter.setPen(Qt.PenStyle.NoPen);painter.setBrush(QColor('#ffe1b8'))
        painter.drawEllipse(QPointF(center.x()+p[0]*radius,center.y()+p[1]*radius),1.3,1.3)
    painter.setBrush(Qt.BrushStyle.NoBrush);painter.setPen(QPen(QColor('#4c9db3'),.8))
    painter.drawEllipse(QRectF(center.x()-radius*1.2,center.y()+radius*1.38,radius*2.4,12))
    painter.restore()
