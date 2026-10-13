"""Entrada e quatro previas de demonstracao, sem contas pessoais."""
import os
import sys
import json
import threading
from pathlib import Path
from unittest.mock import patch
os.environ['QT_QPA_PLATFORM']='windows'
BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE));sys.path.insert(0,str(BASE/'tests'))
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
import test_fui_screens
app=QApplication(sys.argv)
fixture=test_fui_screens.AllSettingsPagesTests();fixture.app=app
inventory=patch('core.connection_verifier.saved_checks',return_value=[]);inventory.start()
fixture.setUp();window=fixture.window;window.resize(1366,768);window.hud.hud_style='core'
window._ui_sounds.enabled=False
OUTPUT=BASE/'validation/universal-opening';OUTPUT.mkdir(parents=True,exist_ok=True)
errors=[];checks=[];samples=[];finished=False;hub=None

def finish():
    global finished
    if finished:return
    finished=True
    if hub:hub.close();hub.deleteLater()
    (OUTPUT/'result.json').write_text(json.dumps({'checks':checks,'errors':errors,'samples':samples},indent=2),encoding='utf-8')
    fixture.tearDown();inventory.stop();app.quit()

sys.excepthook=lambda kind,error,tb:(errors.append(kind.__name__),finish())

def loading():
    veil=window._opening_veil
    if veil and veil.isVisible():
        window.grab().save(str(OUTPUT/'loading-distant-hub.png'));checks.append('native-distant-hub-visible-during-loading')
    else:errors.append('loading-hub-missing')
    wait_ready()

def wait_ready():
    core=window.hud._spatial_core
    if not core or not core._ready or not window._environment.started:
        QTimer.singleShot(100,wait_ready);return
    sample()

def sample():window.hud._spatial_core.page().runJavaScript('window.hologramDiagnostics()',received)

def received(value):
    if not value:errors.append('no-core-diagnostics');finish();return
    samples.append({key:value[key] for key in ('framesRendered','coreVisible','travel')})
    window.grab().save(str(OUTPUT/f'entrance-{len(samples)}.png'))
    if len(samples)<4:QTimer.singleShot(700,sample)
    else:
        if not all(a['travel']>b['travel'] for a,b in zip(samples,samples[1:])):errors.append('camera-not-approaching')
        else:checks.append('shared-camera-approaches-without-reset')
        if not all(item['coreVisible'] for item in samples):errors.append('core-hidden-during-entrance')
        else:checks.append('core-visible-throughout-entrance')
        if not all(b['framesRendered']>a['framesRendered'] for a,b in zip(samples,samples[1:])):errors.append('render-stalled')
        else:checks.append('frames-advance-during-entrance')
        QTimer.singleShot(2500,pins)

def pins():
    for kind,value,items in [('weather','clima',[]),('calendar','agenda',[{'title':'Compromisso de teste','detail':'14h'}]),
        ('tasks','tarefas',[{'title':'Tarefa de teste'}]),('news','noticias',[{'title':'Noticia de demonstracao','detail':'Conteudo sintetico'}])]:
        window._show_manifestation({'kind':kind,'title':value.capitalize(),'code':61,'temperature':23,'condition':'Chuva','city':'Cidade de demonstracao','count':1,'items':items,'narrationDriven':False})
        request={'action':'pin','value':value,'done':threading.Event()};window._apply_interface_request(request)
        if not request['result']['ok']:errors.append('pin-'+kind)
    checks.append('four-different-domains-pin-through-portuguese-commands')
    QTimer.singleShot(2200,capture_pins)

def capture_pins():
    window.grab().save(str(OUTPUT/'four-personalized-pins.png'))
    for key,value in window._pin_previews.items():
        if not value['widget'].isVisible():errors.append('pin-not-visible-'+key)
    from core.settings_hub import SettingsHub
    import ui
    global hub
    hub=SettingsHub(window,ui.API_FILE,ui.C);hub.showFullScreen()
    QTimer.singleShot(700,settings)

def settings():
    hub.grab().save(str(OUTPUT/'settings-refined.png'));finish()

QTimer.singleShot(40,loading)
QTimer.singleShot(25000,lambda:(errors.append('timeout'),finish()))
app.exec()
print(json.dumps({'ok':not errors,'checks':checks,'errors':errors,'samples':samples}))
sys.exit(bool(errors))
