"""Blue optical glass for settings and pinned projections; cached native material."""
from PyQt6.QtCore import Qt,QRectF
from PyQt6.QtGui import QColor,QPainter,QPainterPath,QPixmap,QPen,QLinearGradient
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def space_texture():
    return QPixmap(str(Path(__file__).parent/'spatial/assets/deep-space.png'))

ACCENTS={'weather':'#63d9ff','tasks':'#65efbc','calendar':'#ffd58a','gmail':'#ffa4b8',
         'whatsapp':'#66edb2','news':'#b7bdff','system':'#6fd8ef','memory':'#ccadff',
         'files':'#7bc5ff','search':'#76e6dd','photo':'#becaff','data':'#8dcaff'}


def optical_plate(width,height,scale=1,accent='#7ebcff'):
    scale=min(1.5,scale)
    image=QPixmap(max(1,round(width*scale)),max(1,round(height*scale)))
    image.setDevicePixelRatio(scale);image.fill(Qt.GlobalColor.transparent)
    p=QPainter(image);p.setRenderHint(QPainter.RenderHint.Antialiasing)
    path=QPainterPath();path.addRoundedRect(QRectF(6,6,max(1,width-12),max(1,height-12)),14,14)
    glass=QLinearGradient(0,0,width,height)
    for at,color in ((0,'#082438'),(.30,'#03131f'),(.72,'#020d18'),(1,'#06334d')):
        c=QColor(color);c.setAlpha(249);glass.setColorAt(at,c)
    p.fillPath(path,glass);p.save();p.setClipPath(path)
    texture=space_texture()
    if not texture.isNull():
        p.setOpacity(.13);p.drawPixmap(QRectF(0,0,width,height),texture,QRectF(texture.rect()));p.setOpacity(1)
    sheen=QLinearGradient(0,0,width*.75,height*.40)
    sheen.setColorAt(0,QColor(164,209,255,25));sheen.setColorAt(.35,QColor(130,170,255,7));sheen.setColorAt(1,QColor(0,0,0,0))
    p.fillPath(path,sheen)
    p.restore()
    edge=QColor(accent)
    for size,alpha in ((12,8),(8,18),(5,28),(2,130),(1,235)):
        edge.setAlpha(alpha);p.setPen(QPen(edge,size));p.drawPath(path)
    inset=QPainterPath();inset.addRoundedRect(QRectF(10,10,max(1,width-20),max(1,height-20)),10,10)
    p.setPen(QPen(QColor(73,167,228,65),1));p.drawPath(inset)
    highlight=QLinearGradient(15,6,width-15,6)
    for at,c in ((0,'#3c9de0'),(.18,'#ecfaff'),(.42,'#1a5579'),(.83,'#b1e6ff'),(1,'#237fb5')):highlight.setColorAt(at,QColor(c))
    p.setPen(QPen(highlight,1.4));p.drawLine(22,6,width-22,6)
    # Etched conductors remain on the rim, clear of labels and controls.
    if width>250:
        x=width*.65
        rail=QPainterPath();rail.moveTo(x-36,7);rail.lineTo(x-28,14);rail.lineTo(x+28,14);rail.lineTo(x+36,7)
        p.setPen(QPen(QColor(67,192,255,150),1));p.drawPath(rail)
        p.setPen(QPen(QColor(148,226,255,210),1));p.drawLine(round(x-17),10,round(x+17),10)
    p.end();return image
