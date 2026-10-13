"""Identidade visual local do DIEF JARVIS, sem recursos externos."""
import math
from pathlib import Path

NAME = 'DIEF JARVIS'
ROOT = Path(__file__).resolve().parent.parent
ICON = ROOT / 'config' / 'dief-jarvis.ico'
PNG = ROOT / 'config' / 'dief-jarvis.png'
SPACE = ROOT / 'core' / 'spatial' / 'assets' / 'deep-space.png'
_fonts_loaded=False


def ensure_fonts():
    global _fonts_loaded
    if _fonts_loaded:return
    import os
    from PyQt6.QtGui import QFontDatabase
    folder=Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts'
    for name in ('segoeui.ttf','seguisb.ttf'):
        path=folder/name
        if path.exists():QFontDatabase.addApplicationFont(str(path))
    _fonts_loaded=True


def build_icon(out_path=ICON):
    from PIL import Image, ImageDraw, ImageFilter
    out_path = Path(out_path)
    size = 1024
    image = Image.new('RGBA', (size, size))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((40, 40, 984, 984), radius=190, fill='#090b19', outline='#ac94ec', width=16)
    glow = Image.new('RGBA', image.size)
    gd = ImageDraw.Draw(glow)
    gd.ellipse((230, 230, 794, 794), outline='#8064d8', width=38)
    image = Image.alpha_composite(image, glow.filter(ImageFilter.GaussianBlur(35)))
    draw = ImageDraw.Draw(image)
    draw.ellipse((206, 206, 818, 818), outline='#b4a1ed', width=12)
    draw.arc((260, 295, 764, 730), 15, 170, fill='#56dfdb', width=14)
    draw.arc((260, 295, 764, 730), 195, 350, fill='#56dfdb', width=14)
    # Duas orbitas elipticas e uma estrela formam o selo proprio do painel.
    draw.ellipse((160, 418, 864, 606), outline='#64c7dd', width=9)
    points=[]
    for index in range(8):
        angle=index*math.pi/4-math.pi/2
        radius=190 if index%2==0 else 62
        points.append((512+math.cos(angle)*radius,512+math.sin(angle)*radius))
    draw.polygon(points,fill='#e8e0ff')
    draw.ellipse((491,491,533,533),fill='#58dbd8')
    for x,y,r in ((170,228,14),(840,770,14),(820,206,8),(224,830,8)):
        draw.ellipse((x-r,y-r,x+r,y+r),fill='#aeb5e8')
    image=image.resize((256,256),Image.Resampling.LANCZOS)
    out_path.parent.mkdir(parents=True,exist_ok=True)
    image.save(out_path,format='ICO',sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])
    image.save(out_path.with_suffix('.png'))
    return True


def app_icon():
    from PyQt6.QtGui import QIcon
    if not ICON.exists():
        try:build_icon()
        except (ImportError,OSError):pass
    return QIcon(str(ICON))


def initialize_application(app):
    from core.app_identity import register_windows_identity
    register_windows_identity()
    app.setApplicationName(NAME);app.setApplicationDisplayName(NAME)
    app.setOrganizationName('DIEF');app.setWindowIcon(app_icon())


from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import QColor, QPainter, QPen, QPolygonF
from PyQt6.QtWidgets import QPushButton


class StarButton(QPushButton):
    def __init__(self, label, points=5, parent=None):
        super().__init__(parent)
        ensure_fonts()
        self.points=points
        self.setFixedSize(32,32)
        self.setCheckable(True)
        self.setAccessibleName(label)
        self.setToolTip(label)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet('QPushButton { background: transparent; border: none; }')

    def paintEvent(self,event):
        painter=QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        active=self.underMouse() or self.isChecked()
        vertices=[]
        for index in range(self.points*2):
            angle=index*math.pi/self.points-math.pi/2
            radius=12 if index%2==0 else 5
            vertices.append(QPointF(16+math.cos(angle)*radius,16+math.sin(angle)*radius))
        painter.setPen(QPen(QColor('#d9d0fa' if active else '#a8adc9'),1.3))
        painter.setBrush(QColor('#725aa7' if active else '#20263e'))
        painter.drawPolygon(QPolygonF(vertices))
        if self.hasFocus():
            painter.setPen(QPen(QColor('#6ce4dd'),1,Qt.PenStyle.DotLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(QPointF(16,16),15,15)
