"""Disposable foreign-process UIA target containing only synthetic test content."""
import json
from pathlib import Path
import sys
import os
import psutil
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication,QWidget,QVBoxLayout,QLabel,QPushButton

app=QApplication(['Espectro synthetic target'])
window=QWidget();window.setWindowTitle('ESPECTRO SYNTHETIC TEST')
layout=QVBoxLayout(window);layout.addWidget(QLabel('Synthetic task output'))
layout.addWidget(QPushButton('Test failed - synthetic fixture'))
layout.addWidget(QLabel('This is synthetic test data.'))
window.setGeometry(160,160,520,280);window.show();window.raise_();window.activateWindow()
Path(sys.argv[1]).write_text(json.dumps({'handle':int(window.winId()),'pid':os.getpid(),'created':psutil.Process().create_time()}),encoding='utf-8')
QTimer.singleShot(60000,app.quit)
app.exec()
