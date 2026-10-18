"""Native renderer verification with a disposable owner and no provider access."""
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
os.environ['DIEF_JARVIS_DATA_DIR']=tempfile.mkdtemp(prefix='dief-spectro-data-')
from PyQt6.QtCore import QTimer,Qt,QCoreApplication,qInstallMessageHandler
from PyQt6.QtWidgets import QApplication,QWidget
from PyQt6.QtGui import QColor
from core.spatial_view import SpatialCoreView
from core.spectro import SpectroController
from core.spectro_commands import request as voice_request
from ui import MainWindow


def main():
    output=Path(tempfile.mkdtemp(prefix='dief-spectro-native-'))
    print('Native output: '+str(output),flush=True)
    import faulthandler
    crash_log=(output/'crash.log').open('w',encoding='utf-8')
    faulthandler.enable(crash_log,all_threads=True)
    def qt_message(kind,context,message):
        with (output/'qt.log').open('a',encoding='utf-8') as log:log.write(str(message)+'\n')
    qInstallMessageHandler(qt_message)
    QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
    def exception(kind,value,tb):
        import traceback
        (output/'exception.txt').write_text(''.join(traceback.format_exception(kind,value,tb)),encoding='utf-8')
        print(kind.__name__+': '+str(value),flush=True)
    sys.excepthook=exception
    app=QApplication.instance() or QApplication(['DIEF Spectro validation'])
    app.setQuitOnLastWindowClosed(False)
    owner=QWidget();owner.resize(800,600);owner.setWindowTitle('Teste local do Espectro')
    owner.hud=SimpleNamespace(motion_reduced=False,state='LISTENING',speaking=False,
        _amp_disp=.15,muted=False,resting=False,append_log=lambda text:None)
    owner._do_interrupt=lambda:None
    owner.show();controller=SpectroController(owner);report={'passed':False,'output':str(output)}
    owner._spectro_controller=controller
    owner.interface_snapshot=lambda:{'spectro':controller.snapshot()}
    deadline=time.monotonic()+35;stages={};ticker=QTimer()

    def finish():
        ticker.stop()
        (output/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps(report),flush=True)
        controller.close();owner.close();app.quit()

    def check():
        try:
            if time.monotonic()>deadline:
                report['error']='Renderer deadline';finish();return
            if stages.get('hotkey_sent'):
                if not controller.active:
                    report['emergency_return']=owner.isVisible()
                    report['passed']=report['passed'] and report['emergency_return']
                    finish()
                return
            if not controller.ready:return
            window=controller.window
            if 'at' not in stages:
                print('Renderer ready',flush=True);stages['at']=time.monotonic();return
            elapsed=time.monotonic()-stages['at']
            if elapsed>1 and 'first' not in stages:
                print('First frame sample',flush=True)
                stages['first']=True
                window.view.page().runJavaScript('window.hologramDiagnostics()',lambda result:report.update(first=result))
                owner.hud.speaking=True;owner.hud._amp_disp=.7
            if elapsed>3 and 'second' not in stages:
                print('Second frame sample',flush=True)
                stages['second']=True
                window.view.page().runJavaScript('window.hologramDiagnostics()',lambda result:report.update(second=result))
                window.grab().save(str(output/'espectro.png'))
                image=window.grab().toImage();pixels=0
                for y in range(0,image.height(),3):
                    for x in range(0,image.width(),3):
                        color=image.pixelColor(x,y)
                        if color.alpha()>0 and max(color.red(),color.green(),color.blue())>30:pixels+=1
                report['lit_pixels']=pixels;report['mask_corner_passes']=not window.mask().contains(window.rect().topLeft())
                report['corner_alpha']=image.pixelColor(0,0).alpha()
                report['mask_center_captures']=window.mask().contains(window.rect().center())
                report['emergency_registered']=bool(window._hotkey) if os.name=='nt' else None
                if os.name=='nt':
                    import ctypes
                    from ctypes import wintypes
                    api=ctypes.WinDLL('user32');api.WindowFromPoint.argtypes=[wintypes.POINT];api.WindowFromPoint.restype=wintypes.HWND
                    api.GetAncestor.argtypes=[wintypes.HWND,wintypes.UINT];api.GetAncestor.restype=wintypes.HWND
                    point=window.pos()+window.rect().topLeft()
                    hit=api.WindowFromPoint(wintypes.POINT(point.x(),point.y()))
                    report['native_corner_passes']=int(api.GetAncestor(hit,2) or 0)!=int(window.winId())
            if elapsed>3.5 and 'second' in report and 'adjust_at' not in stages:
                first=report.get('first') or {};second=report.get('second') or {}
                report['passed']=bool(second.get('framesRendered',0)>first.get('framesRendered',0) and
                    second.get('phase')=='speaking' and report['lit_pixels']>100 and
                    report['mask_corner_passes'] and report['mask_center_captures'] and
                    report['corner_alpha']==0 and (os.name!='nt' or report.get('native_corner_passes') and report['emergency_registered']))
                stages['adjust_at']=time.monotonic();stages['width']=window.width();stages['opacity']=window.windowOpacity()
                operation,settings=voice_request('diminua seu tamanho',True)
                import threading
                packet={'action':'spectro','value':operation,'setting':json.dumps(settings),'done':threading.Event()}
                MainWindow._apply_interface_request(owner,packet)
                report['resize_accepted']=packet['result'].get('ok')
            if 'adjust_at' in stages:
                adjustment=time.monotonic()-stages['adjust_at']
                if adjustment>.6 and 'moved' not in stages:
                    report['voice_resize_effect']=window.width()<stages['width']
                    stages['x']=window.x();stages['moved']=True
                    operation,settings=voice_request('se mova para a esquerda',True)
                    import threading
                    packet={'action':'spectro','value':operation,'setting':json.dumps(settings),'done':threading.Event()}
                    MainWindow._apply_interface_request(owner,packet)
                if adjustment>1.2 and 'opacity_set' not in stages:
                    report['voice_position_effect']=window.x()<stages['x'];stages['opacity_set']=True
                    operation,settings=voice_request('fique mais transparente',True)
                    import threading
                    packet={'action':'spectro','value':operation,'setting':json.dumps(settings),'done':threading.Event()}
                    MainWindow._apply_interface_request(owner,packet)
                if adjustment<1.8:return
                report['voice_opacity_effect']=window.windowOpacity()<stages['opacity']-.1
                report['passed']=report['passed'] and all(report.get(key) for key in ('voice_resize_effect','voice_position_effect','voice_opacity_effect'))
                if os.name=='nt':
                    import ctypes
                    from ctypes import wintypes
                    api=ctypes.WinDLL('user32');api.PostMessageW.argtypes=[wintypes.HWND,wintypes.UINT,wintypes.WPARAM,wintypes.LPARAM]
                    api.PostMessageW.restype=wintypes.BOOL
                    if not api.PostMessageW(int(window.winId()),0x0312,window.HOTKEY,0):raise RuntimeError('Cannot deliver local hotkey test')
                    stages['hotkey_sent']=True
                else:finish()
        except Exception as error:
            report['passed']=False;report['error']=str(error);finish()

    try:controller.apply('enter',{})
    except Exception as error:
        report['error']=str(error);finish();return 1
    ticker.timeout.connect(check);ticker.start(100);app.exec()
    return 0 if report['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
