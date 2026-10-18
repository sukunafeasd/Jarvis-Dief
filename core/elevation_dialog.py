"""Tela de acesso elevado. Nenhuma conta ou ferramenta inicia aqui."""
import time
from PyQt6.QtCore import Qt, QTimer, QPointF,QEvent
from PyQt6.QtGui import QColor, QPainter, QPen, QPixmap, QFont
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QWidget
from core.branding import NAME, SPACE, app_icon, ensure_fonts
from core.fui_paint import glass_plate,paint_core
from core.hud_glass import paint_hud_light
from core.settings_style import SETTINGS_STYLE


class ElevationDialog(QDialog):
    def __init__(self,restart,parent=None,reduced=False):
        super().__init__(parent)
        ensure_fonts()
        self.restart=restart
        self.setWindowTitle(NAME+' · Acesso ao sistema')
        self.setWindowIcon(app_icon())
        self.setMinimumSize(580,560)
        self.resize(720,620)
        self.background=QPixmap(str(SPACE))
        self._background_size=None
        self._background_scaled=QPixmap()
        self._plate=None;self._plate_key=None
        self.started=time.monotonic()
        self.motion_reduced=bool(reduced)
        self.setProperty('independentTheme',True)
        self.setStyleSheet(SETTINGS_STYLE)
        layout=QVBoxLayout(self);layout.setContentsMargins(40,26,40,28);layout.setSpacing(14)
        brand=QLabel(NAME);brand.setObjectName('settingsBrand');brand.setFont(QFont('Segoe UI',13,QFont.Weight.DemiBold));brand.setAlignment(Qt.AlignmentFlag.AlignCenter);layout.addWidget(brand)
        self.hologram=QWidget();self.hologram.setMinimumHeight(200);layout.addWidget(self.hologram,1)
        title=QLabel('Permissão para iniciar');title.setObjectName('settingsTitle');title.setFont(QFont('Segoe UI',23,QFont.Weight.DemiBold));title.setAlignment(Qt.AlignmentFlag.AlignCenter);layout.addWidget(title)
        self.notice=QLabel('O DIEF JARVIS precisa abrir como administrador.\nConfirme a solicitação do Windows para continuar.')
        self.notice.setWordWrap(True);self.notice.setFont(QFont('Segoe UI',11));self.notice.setAlignment(Qt.AlignmentFlag.AlignCenter);layout.addWidget(self.notice)
        row=QHBoxLayout();layout.addLayout(row)
        close=QPushButton('Fechar');close.setObjectName('dismiss');close.clicked.connect(self.reject);row.addWidget(close)
        self.continue_button=QPushButton('Reiniciar como administrador');self.continue_button.setObjectName('primaryAction');self.continue_button.clicked.connect(self.elevate);self.continue_button.setDefault(True);row.addWidget(self.continue_button,2)
        self.timer=QTimer(self);self.timer.timeout.connect(self.update)
        if not self.motion_reduced:self.timer.start(50)
        self.finished.connect(self.timer.stop)

    def elevate(self):
        self.continue_button.setEnabled(False)
        try:ok=self.restart()
        except OSError:ok=False
        if ok:self.accept()
        else:
            self.notice.setText('A permissão não foi concedida. Você pode tentar novamente ou fechar o Jarvis.')
            self.continue_button.setEnabled(True)

    def paintEvent(self,event):
        super().paintEvent(event)
        painter=QPainter(self);painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if not self.background.isNull():
            if self._background_size != self.size():
                self._background_scaled=self.background.scaled(self.size(),Qt.AspectRatioMode.KeepAspectRatioByExpanding,Qt.TransformationMode.SmoothTransformation)
                self._background_size=self.size()
            source=self._background_scaled
            painter.drawPixmap((self.width()-source.width())//2,(self.height()-source.height())//2,source)
        painter.fillRect(self.rect(),QColor(5,8,20,80))
        key=(self.width(),self.height(),min(1.5,self.devicePixelRatioF()))
        if key!=self._plate_key:self._plate_key=key;self._plate=glass_plate(*key)
        painter.drawPixmap(0,0,self._plate)
        center=self.hologram.geometry().center();cx,cy=center.x(),center.y();radius=min(100,self.hologram.height()*0.39)
        seconds=0 if self.motion_reduced else time.monotonic()-self.started
        paint_core(painter,QPointF(cx,cy),radius,seconds)
        paint_hud_light(painter,self.width(),self.height(),(seconds/9)%1)
        painter.setPen(QPen(QColor(58,209,232,90),1))
        painter.drawLine(40,18,self.width()-40,18)
        painter.setPen(QPen(QColor('#ff525e'),2))
        painter.drawLine(40,18,100,18)
        painter.end()

    def changeEvent(self,event):
        super().changeEvent(event)
        if event.type()==QEvent.Type.WindowStateChange and hasattr(self,'timer'):
            if self.isMinimized():self.timer.stop()
            elif self.isVisible() and not self.motion_reduced:self.timer.start(50)

    def hideEvent(self,event):
        self.timer.stop()
        super().hideEvent(event)

    def showEvent(self,event):
        super().showEvent(event)
        if not self.motion_reduced:self.timer.start(50)
