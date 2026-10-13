"""Record native FUI surfaces using isolated settings and no connected accounts."""
import os
os.environ['QT_QPA_PLATFORM']='offscreen'
import sys
import json
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch
from contextlib import ExitStack

BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE))
from PyQt6.QtWidgets import QApplication
from PyQt6.QtTest import QTest
from PyQt6.QtGui import QPainter,QPixmap,QColor
from PyQt6.QtCore import QByteArray,QBuffer,QIODevice
from core.elevation_dialog import ElevationDialog
from core.settings_hub import SettingsHub
import ui


def encode_frames(output,frame):
    ffmpeg=Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'AppData/Local')))/'ms-playwright/ffmpeg-1011/ffmpeg-win64.exe'
    if not ffmpeg.is_file():return
    encoder=subprocess.Popen([str(ffmpeg),'-hide_banner','-loglevel','error','-f','image2pipe',
        '-vcodec','mjpeg','-framerate','10','-i','pipe:0','-c:v','libvpx','-b:v','1500k','-y',
        str(BASE/'validation/all-screens-fui.webm')],stdin=subprocess.PIPE,
        creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    try:
        for index in range(frame):
            data=QByteArray();buffer=QBuffer(data);buffer.open(QIODevice.OpenModeFlag.WriteOnly)
            image=QPixmap(str(output/f'frame-{index:04d}.png'))
            if not image.save(buffer,'JPEG',95):raise RuntimeError('Não foi possível codificar um quadro.')
            encoder.stdin.write(bytes(data));buffer.close()
    finally:
        encoder.stdin.close()
        code=encoder.wait(timeout=120)
    if code:raise RuntimeError('Não foi possível codificar a gravação de validação.')
    print('Native UI movie saved.')


def main():
    output=BASE/'validation/all-screens/frames';output.mkdir(parents=True,exist_ok=True)
    app=QApplication.instance() or QApplication([]);app.setStyle('Fusion')
    if '--encode-only' in sys.argv:
        encode_frames(output,len(list(output.glob('frame-*.png'))));return
    frame=0
    def capture(widget,count):
        nonlocal frame
        for _ in range(count):
            QTest.qWait(100)
            image=QPixmap(1200,800);image.fill(QColor('#05080e'))
            painter=QPainter(image);shot=widget.grab()
            painter.drawPixmap((1200-shot.width())//2,(800-shot.height())//2,shot);painter.end()
            image.save(str(output/f'frame-{frame:04d}.png'));frame+=1
    with tempfile.TemporaryDirectory() as folder,ExitStack() as stack:
        root=Path(folder);config=root/'profile.json'
        config.write_text(json.dumps({'reduce_motion':False,'hud_style':'core','ui_color':'#ff303b'}),encoding='utf-8')
        for target,value in [('ui.API_FILE',config),('memory.config_manager.CONFIG_FILE',config),
            ('core.profile.CONFIG',config),('core.integration_tokens.ROOT',root),
            ('memory.memory_manager.MEMORY_PATH',root/'memory.json'),
            ('core.gmail_connection.TOKEN',root/'gmail.bin'),
            ('core.gmail_connection.CREDENTIALS',root/'oauth.json'),
            ('core.whatsapp_web.PROFILE',root/'whatsapp')]:stack.enter_context(patch(target,value))
        window=ui.MainWindow(str(BASE/'core/face_model.obj'));window.resize(1200,800)
        admin=ElevationDialog(lambda:False);admin.show();capture(admin,24);admin.close()
        setup=ui.SetupOverlay();setup.resize(580,420);setup.show();capture(setup,20);setup.close()
        hub=SettingsHub(window,config,ui.C);hub.resize(1200,800);hub.show()
        for key in hub.page_indices:
            hub.open_page(key);capture(hub,15)
        hub.close();window.close()
        for widget in (admin,setup,hub,window):widget.deleteLater()
        app.processEvents()
    print(f'Recorded {frame} native UI frames with isolated demo settings.')

    encode_frames(output,frame)


if __name__=='__main__':main()
