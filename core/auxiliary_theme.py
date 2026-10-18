"""Approved observatory controls for auxiliary surfaces, without changing forms."""
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (QWidget,QPushButton,QLineEdit,QTextEdit,QComboBox,
    QSpinBox,QCheckBox,QScrollArea,QLabel)
from core.settings_style import SETTINGS_STYLE
from core.ui_assets import glyph

SURFACE_STYLE=SETTINGS_STYLE+'''
QFrame { background:transparent; border:0; }
QTextEdit { font-family:'Cascadia Mono','Consolas'; font-size:12px; }
QPushButton { padding:4px 9px; min-height:0; }
QPushButton:checked { background:#12699e; color:#ffffff; border:1px solid #c1eeff; border-bottom:2px solid #77dcff; }
QPushButton#primaryAction { padding:7px 16px; border-radius:12px; }
QLineEdit,QComboBox,QSpinBox { padding:5px 8px; }
QProgressBar { background:#031321; color:#dff6ff; border:1px solid #285f80; border-radius:4px; text-align:center; }
QProgressBar::chunk { background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #0877bd,stop:.7 #29c7ff,stop:1 #b8f4ff); border-radius:3px; }
'''


def apply_auxiliary_theme(root):
    """Only called for legacy windows; approved settings/pins keep their styles."""
    root.setProperty('independentTheme',True)
    controls=(QPushButton,QLineEdit,QTextEdit,QComboBox,QSpinBox,QCheckBox,QScrollArea)
    for widget in root.findChildren(QWidget):
        if isinstance(widget,controls):
            widget.setStyleSheet('')
            font=QFont('Consolas' if isinstance(widget,QTextEdit) else 'Segoe UI')
            font.setPointSize(10 if widget.height()>32 else 9)
            widget.setFont(font)
            if isinstance(widget,QPushButton) and widget.maximumHeight()<28:
                widget.setStyleSheet('QPushButton { padding:1px 4px; min-height:0; font-size:11px; }')
            if isinstance(widget,QPushButton) and widget.icon().isNull():
                text=widget.text().casefold()
                symbol=next((name for word,name in (('salvar','save'),('fechar','x'),('cancelar','x'),
                    ('voltar','arrow-left'),('testar','refresh-cw'),('conectar','link'),('iniciar','bot')) if word in text),None)
                if symbol:widget.setIcon(glyph(symbol))
        elif isinstance(widget,QLabel):
            font=widget.font()
            if font.family() in ('Courier New','Courier'):font.setFamily('Segoe UI');widget.setFont(font)
    root.setStyleSheet(SURFACE_STYLE)
