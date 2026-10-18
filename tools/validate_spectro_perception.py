"""Native UIA/annotations/privacy test against an isolated synthetic child app."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import threading
import types
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
output=Path(tempfile.mkdtemp(prefix='dief-spectro-perception-'))
os.environ['DIEF_JARVIS_DATA_DIR']=str(output/'data')
import ui
from PyQt6.QtWidgets import QApplication,QWidget
from PyQt6.QtTest import QTest
from core.spectro import SpectroController
from core import spectro_perception as perception
from actions.spectro_control import spectro_control


def main():
    report={'passed':False,'output':str(output)};child=None;controller=None;fixture=None
    app=QApplication(['Espectro perception test']);app.setQuitOnLastWindowClosed(False)
    def wait(condition,seconds=15):
        end=time.monotonic()+seconds
        while time.monotonic()<end:
            app.processEvents()
            if condition():return
            QTest.qWait(100)
        raise AssertionError('Condition deadline')
    owner=QWidget();owner.resize(600,400)
    owner.hud=SimpleNamespace(motion_reduced=True,state='LISTENING',speaking=False,_amp_disp=.1,muted=False,resting=False,append_log=lambda text:None)
    owner._do_interrupt=lambda:None;owner.show()
    owner._spectro_error=lambda text:(output/'poll-error.txt').write_text(text,encoding='utf-8')
    try:
        controller=SpectroController(owner);controller.apply('enter',{})
        owner._spectro_controller=controller
        owner.interface_snapshot=lambda:{'spectro':controller.snapshot()}
        owner._apply_interface_request=types.MethodType(ui.MainWindow._apply_interface_request,owner)
        bridge=ui.JarvisUI.__new__(ui.JarvisUI);bridge._win=owner
        bridge._ultron_context_lock=threading.RLock();bridge._ultron_user={'text':'','serial':0}
        owner._spectro_context_provider=bridge.ultron_user_context
        report['stage']='core_ready'
        wait(lambda:controller.ready)
        child=subprocess.Popen([sys.executable,str(ROOT/'tools/spectro_test_app.py'),str(output/'target.json')],creationflags=subprocess.CREATE_NO_WINDOW)
        report['stage']='fixture_ready';wait(lambda:(output/'target.json').exists())
        fixture=json.loads((output/'target.json').read_text(encoding='utf-8'));handle=fixture['handle']
        import win32gui
        win32gui.SetForegroundWindow(handle)
        report['stage']='fixture_foreground';wait(lambda:perception.foreground().get('process_id')==fixture['pid'])
        bridge.record_ultron_user('acompanhe este aplicativo')
        authorized=json.loads(spectro_control({'operation':'observe_current'},bridge))
        assert authorized.get('ok'),authorized
        report['stage']='uia_controls'
        wait(lambda:bool(controller.observer.current.get('controls')))
        current=controller.observer.context()
        assert current.get('ok') and current.get('process_id')==fixture['pid']
        report['observed_only_fixture']=current.get('title')=='ESPECTRO SYNTHETIC TEST'
        from core.spectro_capture import capture
        data,mime=capture(current,lambda:controller.observer.enabled)
        from PIL import Image
        import io
        image=Image.open(io.BytesIO(data));report['window_only_capture']=mime=='image/jpeg' and image.width<1000 and image.height<600
        (output/'fixture-capture.jpg').write_bytes(data)
        target=next(item for item in current['controls'] if 'Test failed' in item['name'])
        highlighted=json.loads(spectro_control({'operation':'highlight','control_id':target['control_id'],'shape':'arrow','text':'Synthetic failure indication'},bridge))
        assert highlighted.get('ok'),highlighted
        report['stage']='highlight'
        wait(lambda:controller.annotations.snapshot()['count']>0)
        report['real_target_highlight']=True
        first=list(controller.observer.target_result['rect'])
        window_rect=win32gui.GetWindowRect(handle)
        win32gui.SetWindowPos(handle,0,window_rect[0]+60,window_rect[1]+30,0,0,0x0015)
        report['stage']='tracking';wait(lambda:bool(controller.observer.target_result and controller.observer.target_result['rect'][0]!=first[0]))
        report['target_tracks_window']=True
        layer=next(iter(controller.annotations.layers.values()))
        assert layer.grab().save(str(output/'annotation.png'))
        report['annotation_clickthrough_flag']=bool(layer.windowFlags() & ui.Qt.WindowType.WindowTransparentForInput)
        notice=controller.observer.initiative.next()
        report['real_event_suggestion']=bool(notice and notice['source'].get('app'))
        bridge.control_interface('spectro','privacy','{}')
        report['privacy_immediate']=not controller.observer.enabled and not controller.observer.current and controller.annotations.snapshot()['count']==0
        report['passed']=all(report.get(key) for key in ('observed_only_fixture','window_only_capture','real_target_highlight','target_tracks_window','annotation_clickthrough_flag','real_event_suggestion','privacy_immediate'))
    except Exception as error:
        report['error']=type(error).__name__+': '+str(error)
        if controller and controller.observer:
            report['observation_error']=controller.observer.last_error
            report['controls_count']=len(controller.observer.current.get('controls',[]))
    finally:
        if controller:controller.close()
        owner.close();app.processEvents()
        if child:
            if fixture:
                import psutil
                try:
                    process=psutil.Process(fixture['pid'])
                    if process.create_time()==fixture['created']:
                        process.terminate()
                        try:process.wait(timeout=3)
                        except psutil.TimeoutExpired:process.kill();process.wait(timeout=3)
                except psutil.NoSuchProcess:pass
            child.terminate()
            try:child.wait(timeout=5)
            except subprocess.TimeoutExpired:child.kill();child.wait(timeout=5)
        (output/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps(report),flush=True)
    return 0 if report['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
