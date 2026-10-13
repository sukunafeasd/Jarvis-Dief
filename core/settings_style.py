"""Independent dark-glass settings with red/cyan luminous detailing."""
from PyQt6.QtCore import Qt, QEvent, QPropertyAnimation, QEasingCurve, pyqtProperty
from PyQt6.QtGui import QColor, QPainter, QFontDatabase, QPalette, QIcon,QPixmap,QLinearGradient,QPen,QRegion
from core.hud_glass import paint_hud_light
from core.fui_paint import glass_plate
from PyQt6.QtWidgets import QDialog, QGraphicsDropShadowEffect, QPushButton
from pathlib import Path
import os

SETTINGS_STYLE = """
QDialog { background:#050d12; color:#edfaff; }
QWidget { background:transparent; color:#edfaff; font-family:'Segoe UI'; font-size:16px; }
QLabel { background:transparent; }
QLabel#settingsBrand { color:#75edf7; font-size:13px; font-weight:600; padding-bottom:8px; }
QLabel#settingsTitle { font-size:25px; font-weight:600; color:#f2fbff; }
QLabel#sectionTitle { font-size:17px; font-weight:500; color:#9ebbc6; padding-bottom:18px; }
QLabel#settingsGroup { color:#c8edf4; font-size:15px; font-weight:600; padding:12px 14px; margin-top:14px; border-left:3px solid #ec6e98; border-bottom:1px solid #49545e; background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #293140,stop:0.6 #18242e,stop:1 #161f29); }
QLabel#settingsMeta { color:#a7bdc8; font-size:12px; }
QLabel#connectionTitle { font-size:15px; font-weight:600; color:#edfaff; }
QLabel#connectionState { font-size:12px; font-weight:600; color:#9ebbc6; }
QLabel#connectionState[tone="ok"] { color:#83d2b6; }
QLabel#connectionState[tone="notice"] { color:#e8c787; }
QLabel#connectionState[tone="error"] { color:#e7a39f; }
QLabel#connectionState[tone="muted"] { color:#9bb7c3; }
QLabel#connectionNotice { color:#a4eff7; font-size:12px; padding-top:10px; padding-bottom:10px; }
QFrame#connectionRow { background:transparent; border:0; }
QWidget#credentialsEditor { background:#0b1b23; border:0; border-left:2px solid #ff4f58; }
QFrame#settingsRail { background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #293342,stop:0.3 #141d28,stop:0.65 #191c2a,stop:1 #302c3b); border:0; border-right:1px solid #8699ac; }
QListWidget { border:0; background:transparent; outline:0; font-size:14px; }
QListWidget::item { padding:13px 10px; margin:3px 0; border-radius:4px; color:#b8d4dc; }
QListWidget::item:selected { background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #692e4c,stop:0.4 #2d294d,stop:1 #16475b); color:#ffffff; border:1px solid #68648f; border-left:3px solid #ff6a92; }
QListWidget::item:hover { background:#142a34; }
QLineEdit,QTextEdit,QComboBox,QSpinBox { background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #131b26,stop:0.12 #1c2734,stop:1 #232d3b); color:#edfaff; padding:12px; border:1px solid #596579; border-top-color:#9caabd; border-bottom-color:#373e57; border-radius:8px; selection-background-color:#2c7182; selection-color:#ffffff; }
QLineEdit:hover,QComboBox:hover,QSpinBox:hover { border-color:#49b4c3; }
QLineEdit:focus,QTextEdit:focus,QComboBox:focus,QSpinBox:focus { border:1px solid #78f4ff; border-bottom:2px solid #78f4ff; background:#13303b; }
QComboBox QAbstractItemView { background:#0d2028; color:#edfaff; selection-background-color:#225765; border:1px solid #49b4c3; }
QComboBox::drop-down { border:0; width:28px; }
QPushButton { background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #2b4b59,stop:0.12 #1b3440,stop:0.5 #102631,stop:1 #142e3b); color:#dcf7fc; padding:10px 14px; border:1px solid #386778; border-top-color:#70b6c3; border-bottom-color:#1a414f; border-radius:5px; min-height:18px; }
QPushButton:hover { background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #355d6e,stop:0.45 #173a47,stop:1 #102c38); border-color:#65e8f3; }
QPushButton:pressed { background:#17313c; }
QPushButton:focus { border:2px solid #65e8f3; }
QPushButton:disabled { color:#8599a2; background:#10212a; }
QPushButton#primaryAction { background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #72324d,stop:0.55 #392545,stop:1 #21374c); color:#ffffff; border-color:#ff6c94; font-weight:600; }
QPushButton#primaryAction:hover { background:#70303a; border-color:#ff9b9f; }
QPushButton#settingsClose { border:0; background:transparent; padding:8px; }
QPushButton#rowConfigure { padding:6px; }
QCheckBox { spacing:10px; padding:8px 0; }
QCheckBox::indicator { width:18px; height:18px; border:1px solid #4ba7b7; border-radius:3px; background:#0b1c24; }
QCheckBox::indicator:checked { background:#47d9e9; border:3px solid #205764; }
QScrollArea { border:0; background:transparent; }
QScrollBar:vertical { background:#0c1920; width:9px; margin:0; }
QScrollBar::handle:vertical { background:#38899b; min-height:28px; border-radius:4px; }
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical { height:0; }
QScrollBar::add-page:vertical,QScrollBar::sub-page:vertical { background:transparent; }
QToolTip { background:#0b2029; color:#edfaff; border:1px solid #48b6c7; padding:6px; }
"""


def settings_icon(icon):
    pixmap = icon.pixmap(24,24)
    painter = QPainter(pixmap)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceAtop)
    painter.setOpacity(.55)
    painter.fillRect(pixmap.rect(),QColor('#7ceaf5'))
    painter.end()
    return QIcon(pixmap)


class SettingsSurface(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        if 'Segoe UI' not in QFontDatabase.families():
            fonts = Path(os.environ.get('WINDIR','C:/Windows')) / 'Fonts'
            for name in ('segoeui.ttf','seguisb.ttf'):
                if (fonts / name).exists():
                    QFontDatabase.addApplicationFont(str(fonts / name))
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint)
        self.setProperty('independentTheme', True)
        palette = self.palette()
        for role in (QPalette.ColorRole.WindowText,QPalette.ColorRole.Text,QPalette.ColorRole.ButtonText):
            palette.setColor(role,QColor('#edfaff'))
        palette.setColor(QPalette.ColorRole.Base,QColor('#0b1a22'))
        palette.setColor(QPalette.ColorRole.Button,QColor('#142b35'))
        palette.setColor(QPalette.ColorRole.Highlight,QColor('#2c7182'))
        palette.setColor(QPalette.ColorRole.HighlightedText,QColor('#ffffff'))
        palette.setColor(QPalette.ColorRole.PlaceholderText,QColor('#9ebbc6'))
        self.setPalette(palette)
        self.setStyleSheet(SETTINGS_STYLE)
        self._reveal = 1.0
        self._plate=None;self._plate_key=None
        self._entrance = QPropertyAnimation(self,b'reveal',self)
        self._entrance.setDuration(420)
        self._entrance.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._light_phase=0.0
        self._ambient=QPropertyAnimation(self,b'lightPhase',self)
        self._ambient.setDuration(6500);self._ambient.setStartValue(0.0);self._ambient.setEndValue(1.0);self._ambient.setLoopCount(-1)
        self._texture=QPixmap(64,64);self._texture.fill(Qt.GlobalColor.transparent)
        painter=QPainter(self._texture);painter.setPen(QColor(117,227,243,12))
        for y in range(0,64,8):
            for x in range(4 if y%16 else 0,64,8):painter.drawPoint(x,y)
        painter.setPen(QColor(44,159,193,5))
        for offset in (0,32):
            painter.drawLine(offset,0,offset,63);painter.drawLine(0,offset,63,offset)
        painter.setPen(QColor(92,205,229,23))
        painter.drawLine(0,0,4,0);painter.drawLine(0,0,0,4)
        painter.end()

    @pyqtProperty(float)
    def lightPhase(self):
        return self._light_phase

    @lightPhase.setter
    def lightPhase(self,value):
        self._light_phase=value
        region=QRegion(0,70,self.width(),16).united(QRegion(self.width()-18,0,18,self.height()))
        region=region.united(QRegion(0,self.height()-16,self.width(),16))
        self.update(region)

    @pyqtProperty(float)
    def reveal(self):
        return self._reveal

    @reveal.setter
    def reveal(self,value):
        self._reveal=value
        self.update()

    def showEvent(self,event):
        super().showEvent(event)
        self.animate_entry()
        for button in self.findChildren(QPushButton,'primaryAction'):
            if button.graphicsEffect() is None:
                glow=QGraphicsDropShadowEffect(button)
                glow.setBlurRadius(18); glow.setOffset(0,0); glow.setColor(QColor(255,65,73,65))
                button.setGraphicsEffect(glow)

    def animate_entry(self,*_):
        self._entrance.stop()
        if hasattr(self,'_config') and self._config().get('reduce_motion',False):
            self._ambient.stop()
            self.reveal=1.0
            return
        if self.isVisible() and not self.isMinimized() and self._ambient.state()!=QPropertyAnimation.State.Running:
            self._ambient.start()
        self._entrance.setStartValue(0.0); self._entrance.setEndValue(1.0); self._entrance.start()

    def hideEvent(self,event):
        self._ambient.stop()
        self._entrance.stop()
        super().hideEvent(event)

    def changeEvent(self,event):
        super().changeEvent(event)
        if event.type()==QEvent.Type.WindowStateChange and hasattr(self,'_ambient'):
            if self.isMinimized(): self._ambient.stop()
            elif self.isVisible(): self.animate_entry()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(),QColor('#0a1522'))
        key=(self.width(),self.height(),min(1.5,self.devicePixelRatioF()))
        if key!=self._plate_key:self._plate_key=key;self._plate=glass_plate(*key)
        painter.drawPixmap(0,0,self._plate);painter.drawTiledPixmap(self.rect(),self._texture)
        rail=getattr(self,'rail',None);start=(rail.width() if rail else 210)+(18 if self.width()<1000 else 30)
        margin=18 if self.width()<1000 else 30
        end=start+int(max(0,self.width()-start-margin)*self._reveal)
        painter.setPen(QColor('#24535f')); painter.drawLine(start,77,self.width()-margin,77)
        if self._reveal<1:
            painter.setPen(QColor('#43dff0')); painter.drawLine(start,77,end,77)
        painter.setPen(QPen(QColor('#245c6c'),1));painter.drawLine(self.width()-1,0,self.width()-1,self.height())
        painter.setPen(QPen(QColor('#ff525d'),2));painter.drawLine(start,77,min(start+44,self.width()-margin),77)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w=self.width();h=self.height()
        reflection=QLinearGradient(start,82,w,220)
        reflection.setColorAt(0,QColor(124,228,244,16));reflection.setColorAt(.35,QColor(89,200,228,5));reflection.setColorAt(1,QColor(10,20,30,0))
        painter.fillRect(start,82,max(0,w-start-margin),max(0,h-100),reflection)
        painter.setPen(QPen(QColor(41,144,170,50),1))
        for y in range(110,h-48,12):
            painter.drawLine(w-14,y,w-18,y)
        painter.setPen(QColor(80,215,232,32))
        for offset in range(0,72,12):
            painter.drawLine(self.width()-margin-72+offset,18,self.width()-margin-64+offset,26)
        if self._ambient.state()==QPropertyAnimation.State.Running:
            painter.save();painter.setClipRect(start,70,max(0,self.width()-start),self.height()-70)
            paint_hud_light(painter,self.width(),self.height(),self._light_phase,77)
            painter.restore()
        painter.end()
