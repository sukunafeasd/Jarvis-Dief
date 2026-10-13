"""Native keyboard bridge and pinned-widget lifecycle with synthetic data."""
import os
import sys
import json
import threading
from pathlib import Path
os.environ['QT_QPA_PLATFORM']='windows'
BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE));sys.path.insert(0,str(BASE/'tests'))
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
import test_fui_screens
app=QApplication(sys.argv)
fixture=test_fui_screens.AllSettingsPagesTests();fixture.app=app;fixture.setUp()
window=fixture.window;window.resize(1366,768);window.hud.hud_style='core';window._ui_sounds.enabled=False
errors=[];checks=[];finished=False
OUTPUT=BASE/'validation/controls-tenth';OUTPUT.mkdir(parents=True,exist_ok=True)


def finish():
    global finished
    if finished:return
    finished=True
    (OUTPUT/'result.json').write_text(json.dumps({'checks':checks,'errors':errors},indent=2),encoding='utf-8')
    fixture.tearDown();app.quit()


sys.excepthook=lambda kind,error,tb:(errors.append({'type':kind.__name__}),finish())


def command(action,value=''):
    request={'action':action,'value':value,'done':threading.Event()}
    window._apply_interface_request(request)
    if not request['result']['ok']:errors.append({'check':action})


def start():
    window._show_manifestation({'kind':'weather','temperature':23,'condition':'Nublado'})
    command('pin');command('clear')
    if 'weather' not in window._pin_previews or not window._pin_previews['weather']['widget'].isVisible():errors.append({'check':'clear-preserves-pin'})
    checks.append('clear-keeps-native-weather-preview')
    QTimer.singleShot(500,keyboard)


def keyboard():
    window.grab().save(str(OUTPUT/'clear-keeps-weather.png'))
    window.showFullScreen()
    window.hud._spatial_core.page().runJavaScript("dispatchEvent(new KeyboardEvent('keydown',{key:'F11',bubbles:true,cancelable:true}))")
    QTimer.singleShot(450,exited)


def exited():
    if window.isFullScreen():errors.append({'check':'browser-key-exit'})
    checks.append('browser-f11-bridge-exits-fullscreen')
    window.hud._spatial_core.page().runJavaScript("dispatchEvent(new KeyboardEvent('keydown',{key:'F11',bubbles:true,cancelable:true}))")
    QTimer.singleShot(450,entered)


def entered():
    if not window.isFullScreen():errors.append({'check':'browser-key-enter'})
    checks.append('browser-f11-bridge-enters-fullscreen')
    finish()


QTimer.singleShot(3500,start)
QTimer.singleShot(18000,lambda:(errors.append({'check':'timeout'}),finish()))
app.exec()
print(json.dumps({'ok':not errors,'checks':checks,'errors':errors}))
sys.exit(1 if errors else 0)
