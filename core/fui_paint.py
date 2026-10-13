"""Native FUI material and hologram shared by entry, setup and settings."""
import math
from PyQt6.QtCore import Qt,QPointF,QRectF
from PyQt6.QtGui import QColor,QPainter,QPen,QRadialGradient,QLinearGradient,QPainterPath,QPixmap
from core.fui_geometry import core_lines,RED,CYAN


def glass_plate(width,height,scale=1,accent='#53daef'):
    scale=min(1.5,scale)
    plate=QPixmap(max(1,round(width*scale)),max(1,round(height*scale)))
    plate.setDevicePixelRatio(scale);plate.fill(Qt.GlobalColor.transparent)
    painter=QPainter(plate);painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    path=QPainterPath();path.addRoundedRect(QRectF(4,4,max(1,width-8),max(1,height-8)),8,8)
    glass=QLinearGradient(0,0,width,height)
    for at,color in ((0,'#283640'),(.18,'#131f2a'),(.55,'#101722'),(1,'#252530')):glass.setColorAt(at,QColor(color))
    painter.fillPath(path,glass)
    painter.save();painter.setClipPath(path)
    painter.setPen(QColor(58,180,210,9))
    for x in range(16,width,48):painter.drawLine(x,0,x,height)
    for y in range(16,height,48):painter.drawLine(0,y,width,y)
    painter.setPen(QColor(125,224,235,10))
    for y in range(10,height,6):painter.drawLine(5,y,width-5,y)
    reflection=QLinearGradient(0,0,width*.65,height*.4)
    reflection.setColorAt(0,QColor(145,231,244,22));reflection.setColorAt(.3,QColor(120,213,230,3));reflection.setColorAt(1,QColor(0,0,0,0))
    painter.fillPath(path,reflection);painter.restore()
    inner=path.translated(0,1)
    painter.setPen(QPen(QColor(183,247,255,65),1));painter.drawPath(inner)
    edge=QColor(accent)
    for thickness,color in ((10,QColor(50,198,233,16)),(5,QColor('#02080b')),(2,edge),(1,QColor('#c1dce7'))):
        painter.setPen(QPen(color,thickness));painter.drawPath(path)
    inset=QPainterPath();inset.addRoundedRect(QRectF(9,9,max(1,width-18),max(1,height-18)),6,6)
    painter.setPen(QPen(QColor(98,194,222,65),1));painter.drawPath(inset)
    painter.setPen(QPen(QColor(225,245,255,30),1))
    painter.drawLine(18,18,max(18,width-18),18)
    painter.setPen(QPen(edge,2));painter.drawLine(18,18,min(width-18,64),18)
    for x,y,sx,sy in ((5,5,1,1),(width-5,5,-1,1),(5,height-5,1,-1),(width-5,height-5,-1,-1)):
        for thickness,alpha in ((12,18),(7,38),(3,115),(1.8,255)):
            painter.setPen(QPen(QColor(255,68,82,alpha),thickness))
            painter.drawLine(x+sx*54,y,x+sx*16,y)
            painter.drawLine(x+sx*16,y,x,y+sy*16)
            painter.drawLine(x,y+sy*16,x,y+sy*45)
    painter.setPen(QPen(QColor(100,227,241,80),1))
    painter.drawLine(65,6,max(65,width-65),6)
    painter.setPen(QPen(QColor(104,240,255,120),1))
    for x in range(76,max(76,width-68),18):
        painter.drawLine(x,height-7,min(width-65,x+5),height-7)
    for y in range(74,height-50,15):painter.drawLine(width-9,y,width-12,y)
    painter.end();return plate


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
