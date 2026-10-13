"""Painel completo com dados sinteticos e nenhum acesso a contas."""
import os
import sys
import json
from pathlib import Path
from unittest.mock import patch
os.environ['QT_QPA_PLATFORM']='windows'
BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE));sys.path.insert(0,str(BASE/'tests'))
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication
import test_fui_screens
app=QApplication(sys.argv)
fixture=test_fui_screens.AllSettingsPagesTests();fixture.app=app
inventory=patch('core.connection_verifier.saved_checks',return_value=[]);inventory.start()
fixture.setUp();window=fixture.window
window._ui_sounds.enabled=False;window.resize(1366,768);window.hud.hud_style='core';window._ready=True;window._apply_state('LISTENING')
OUTPUT=BASE/'validation/unframed-native';OUTPUT.mkdir(parents=True,exist_ok=True)
errors=[];checks=[];finished=False;hub=None;first_time=0

def finish():
    global finished
    if finished:return
    finished=True
    if hub:hub.close();hub.deleteLater()
    result={'checks':checks,'errors':errors}
    (OUTPUT/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    fixture.tearDown();inventory.stop();app.quit()

sys.excepthook=lambda kind,error,tb:(errors.append(kind.__name__),finish())

def begin():
    window._pin_data({'kind':'weather','title':'Clima','city':'Cidade de demonstracao','code':61,
                     'temperature':23,'condition':'Chuva','humidity':62,'wind':12,'rain':80})
    window._show_manifestation({'kind':'gmail','title':'Mensagens importantes','narrationDriven':False,'items':[
        {'title':'Confirmacao de compromisso','detail':'Reuniao de demonstracao amanha as 14h.'},
        {'title':'Atualizacao do projeto','detail':'Dados sinteticos para conferir a leitura.'}]})
    QTimer.singleShot(3200,capture)

def capture():
    window.grab().save(str(OUTPUT/'gmail-and-weather-pin.png'))
    if 'weather' not in window._pin_previews:errors.append('missing-weather-pin')
    else:checks.append('weather-pin-persists-next-to-open-projection')
    if 'background: transparent' not in window._content_panel.styleSheet():errors.append('opaque-native-panel')
    else:checks.append('native-information-panel-is-transparent')
    window._content_spatial.page().runJavaScript('({...window.holographicMotionDiagnostics(),hidden:document.hidden,osReduced:matchMedia("(prefers-reduced-motion: reduce)").matches,status:window.presentationStatus()})',first)

def first(value):
    global first_time
    first_time=(value or {}).get('time',0)
    QTimer.singleShot(650,lambda:window._content_spatial.page().runJavaScript('({...window.holographicMotionDiagnostics(),hidden:document.hidden,osReduced:matchMedia("(prefers-reduced-motion: reduce)").matches,status:window.presentationStatus()})',second))

def second(value):
    if not value or value.get('time',0)<=first_time:errors.append({'check':'native-icon-motion','diagnostic':value,'prior':first_time})
    else:checks.append('native-holographic-icon-is-animated')
    from core.settings_hub import SettingsHub
    import ui
    hub_local=SettingsHub(window,ui.API_FILE,ui.C)
    global hub
    hub=hub_local;hub.showFullScreen()
    QTimer.singleShot(700,settings)

def settings():
    hub.grab().save(str(OUTPUT/'settings-profile.png'))
    if hub._ambient.state()!=hub._ambient.State.Running:errors.append('settings-motion')
    else:checks.append('settings-conductors-are-animated')
    finish()

QTimer.singleShot(4200,begin)
QTimer.singleShot(25000,lambda:(errors.append('timeout'),finish()))
app.exec()
print(json.dumps({'ok':not errors,'checks':checks,'errors':errors}))
sys.exit(bool(errors))
