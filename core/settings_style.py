"""Independent dark-glass settings with red/cyan luminous detailing."""
from PyQt6.QtCore import Qt, QEvent, QPropertyAnimation, QEasingCurve, pyqtProperty
from PyQt6.QtGui import QColor, QPainter, QFontDatabase, QPalette, QIcon,QPixmap,QLinearGradient,QPen,QRegion
from core.hud_glass import paint_hud_light
from core.observatory_theme import space_texture
from PyQt6.QtWidgets import QDialog, QGraphicsDropShadowEffect, QPushButton
from pathlib import Path
import os

SETTINGS_STYLE = """
QDialog { background:#020a12; color:#f2f6ff; }
QWidget { background:transparent; color:#edfaff; font-family:'Segoe UI'; font-size:13px; }
QLabel { background:transparent; }
QLabel#settingsBrand { color:#a7dcff; font-size:14px; font-weight:600; padding-bottom:2px; }
QLabel#settingsTitle { font-size:28px; font-weight:600; color:#d7f2ff; }
QLabel#sectionTitle { font-size:11px; color:#82abc5; padding-bottom:18px; }
QLabel#settingsGroup { color:#c8eaff; font-size:13px; font-weight:600; padding:8px 4px; border-bottom:1px solid #1c5679; }
QLabel#sectionHeading { color:#c6e7ff; font-size:14px; font-weight:600; }
QLabel#fieldTitle { color:#e1f2ff; font-size:13px; }
QLabel#settingsMeta { color:#87b1cb; font-size:11px; }
QLabel#railClock { color:#bdeaff; font-size:13px; padding:14px 8px; border-top:1px solid #1b5677; }
QLabel#connectionTitle { font-size:14px; font-weight:600; color:#e3f3ff; }
QLabel#connectionState { font-size:12px; font-weight:600; color:#9ebbc6; }
QLabel#connectionState[tone="ok"] { color:#29e8a1; }
QLabel#connectionState[tone="notice"] { color:#e8c787; }
QLabel#connectionState[tone="error"] { color:#e7a39f; }
QLabel#connectionState[tone="muted"] { color:#9bb7c3; }
QLabel#connectionNotice { color:#a4eff7; font-size:12px; padding-top:10px; padding-bottom:10px; }
QFrame#connectionRow,QFrame#settingsSection,QFrame#corePreview { background:transparent; border:0; }
QWidget#credentialsEditor { background:#041725; border:1px solid #25658a; border-radius:10px; }
QFrame#settingsRail { background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 rgba(2,12,23,235),stop:1 rgba(3,18,30,210)); border:0; border-right:1px solid #4ebbea; }
QListWidget { border:0; background:transparent; outline:0; font-size:14px; }
QListWidget::item { padding:14px 9px; margin:4px 0; border:1px solid transparent; border-radius:9px; color:#b8d8ed; }
QListWidget::item:selected { background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #471723,stop:.5 #21121c,stop:1 #45141d); color:#ffffff; border:1px solid #ff5865; }
QListWidget::item:hover { background:#0e3045; border-color:#246989; }
QLineEdit,QTextEdit,QComboBox,QSpinBox { background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #020d19,stop:1 #092136); color:#eaf5ff; padding:8px 11px; border:1px solid #27658d; border-top-color:#578eab; border-bottom-color:#2378a9; border-radius:7px; selection-background-color:#176aa2; selection-color:#ffffff; }
QLineEdit:hover,QComboBox:hover,QSpinBox:hover { border-color:#49b4c3; }
QLineEdit:focus,QTextEdit:focus,QComboBox:focus,QSpinBox:focus { border:1px solid #a0d5ff; border-bottom:2px solid #88c7ff; background:#18355a; }
QComboBox QAbstractItemView { background:#0d1f3e; color:#f4f8ff; selection-background-color:#285480; border:1px solid #729ac7; }
QComboBox::drop-down { border:0; width:28px; }
QComboBox::down-arrow { image:url(@ICONS@/chevron-down.svg); width:14px; height:14px; }
QSpinBox::up-button { subcontrol-origin:border; subcontrol-position:top right; width:24px; border:0; border-left:1px solid #285b7b; border-bottom:1px solid #285b7b; }
QSpinBox::down-button { subcontrol-origin:border; subcontrol-position:bottom right; width:24px; border:0; border-left:1px solid #285b7b; }
QSpinBox::up-arrow { image:url(@ICONS@/chevron-up.svg); width:12px; height:12px; }
QSpinBox::down-arrow { image:url(@ICONS@/chevron-down.svg); width:12px; height:12px; }
QPushButton { background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #16446b,stop:0.18 #092239,stop:1 #0c3353); color:#dcf3ff; padding:7px 12px; border:1px solid #298ec3; border-top-color:#88d2f8; border-bottom-color:#12699e; border-radius:6px; min-height:18px; }
QPushButton:hover { background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #355d6e,stop:0.45 #173a47,stop:1 #102c38); border-color:#65e8f3; }
QPushButton:pressed { background:#17313c; }
QPushButton:focus { border:2px solid #65e8f3; }
QPushButton:disabled { color:#8599a2; background:#10212a; }
QPushButton#primaryAction { background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #51cdff,stop:.16 #0782ce,stop:.52 #075393,stop:1 #18a5ea); color:#ffffff; border:1px solid #a1edff; border-radius:18px; padding:11px 30px; font-size:14px; font-weight:600; }
QPushButton#primaryAction:hover { background:#307ac2; border-color:#c3e4ff; }
QPushButton#settingsClose { border:0; background:transparent; padding:8px; }
QPushButton#rowConfigure { padding:6px; }
QCheckBox { spacing:10px; padding:8px 0; }
QCheckBox::indicator { width:34px; height:18px; border:1px solid #3d6684; border-radius:10px; background:qradialgradient(cx:.25,cy:.5,radius:.25,fx:.25,fy:.5,stop:0 #c0e3ff,stop:.85 #90b9dd,stop:.95 #123047,stop:1 #071421); }
QCheckBox::indicator:checked { border-color:#57dfff; background:qradialgradient(cx:.75,cy:.5,radius:.25,fx:.75,fy:.5,stop:0 #ffffff,stop:.8 #d3f8ff,stop:.95 #00b8ff,stop:1 #007aba); }
QCheckBox::indicator:focus { border:2px solid #e6f9ff; }
QScrollArea { border:0; background:transparent; }
QTabBar::tab { color:#a7d3ed; background:#03101d; border:1px solid #25618a; border-radius:6px; padding:10px 18px; margin-right:6px; min-width:64px; }
QTabBar::tab:selected { background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #167bb3,stop:.5 #064478,stop:1 #138ccb); color:#ffffff; border-color:#8cddff; }
QTabBar::tab:hover { border-color:#84c8ec; color:#ffffff; }
QScrollBar:vertical { background:#0c1920; width:9px; margin:0; }
QScrollBar::handle:vertical { background:#38899b; min-height:28px; border-radius:4px; }
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical { height:0; }
QScrollBar::add-page:vertical,QScrollBar::sub-page:vertical { background:transparent; }
QToolTip { background:#0b2029; color:#edfaff; border:1px solid #48b6c7; padding:6px; }
"""
SETTINGS_STYLE=SETTINGS_STYLE.replace('@ICONS@',(Path(__file__).resolve().parents[1]/'resources/ui-icons').as_posix())


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
        region=QRegion(0,58,self.width(),16).united(QRegion(self.width()-18,0,18,self.height()))
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
                glow.setBlurRadius(18); glow.setOffset(0,0); glow.setColor(QColor(94,165,255,65))
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
        painter.fillRect(self.rect(),QColor('#020912'))
        key=(self.width(),self.height(),min(1.5,self.devicePixelRatioF()))
        if key!=self._plate_key:
            self._plate_key=key
            self._plate=space_texture().scaled(self.size(),Qt.AspectRatioMode.KeepAspectRatioByExpanding,Qt.TransformationMode.SmoothTransformation)
        painter.setOpacity(.58);painter.drawPixmap(0,0,self._plate);painter.setOpacity(1)
        shade=QLinearGradient(0,0,0,self.height())
        shade.setColorAt(0,QColor(1,9,17,130));shade.setColorAt(.65,QColor(1,9,17,190));shade.setColorAt(1,QColor(2,17,29,70))
        painter.fillRect(self.rect(),shade)
        rail=getattr(self,'rail',None);start=(rail.width() if rail else 210)+(18 if self.width()<1000 else 30)
        margin=18 if self.width()<1000 else 30
        end=start+int(max(0,self.width()-start-margin)*self._reveal)
        painter.setPen(QColor('#24535f')); painter.drawLine(start,64,self.width()-margin,64)
        if self._reveal<1:
            painter.setPen(QColor('#43dff0')); painter.drawLine(start,64,end,64)
        painter.setPen(QPen(QColor('#245c6c'),1));painter.drawLine(self.width()-1,0,self.width()-1,self.height())
        painter.setPen(QPen(QColor('#88bdff'),2));painter.drawLine(start,64,min(start+44,self.width()-margin),64)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w=self.width();h=self.height()
        reflection=QLinearGradient(start,82,w,220)
        reflection.setColorAt(0,QColor(124,228,244,7));reflection.setColorAt(.35,QColor(89,200,228,0));reflection.setColorAt(1,QColor(10,20,30,0))
        painter.fillRect(start,82,max(0,w-start-margin),max(0,h-100),reflection)
        painter.setPen(QPen(QColor(41,144,170,50),1))
        for y in range(110,h-48,12):
            painter.drawLine(w-14,y,w-18,y)
        painter.setPen(QColor(80,215,232,32))
        for offset in range(0,72,12):
            painter.drawLine(self.width()-margin-72+offset,18,self.width()-margin-64+offset,26)
        if self._ambient.state()==QPropertyAnimation.State.Running:
            painter.save();painter.setClipRect(start,58,max(0,self.width()-start),self.height()-58)
            x=start+max(0,self.width()-start-margin)*self._light_phase
            beam=QLinearGradient(x-40,64,x+40,64)
            beam.setColorAt(0,QColor(130,196,255,0));beam.setColorAt(.5,QColor(218,239,255,200));beam.setColorAt(1,QColor(130,196,255,0))
            painter.setPen(QPen(beam,2));painter.drawLine(max(start,int(x-40)),64,min(self.width()-margin,int(x+40)),64)
            painter.restore()
        painter.end()
