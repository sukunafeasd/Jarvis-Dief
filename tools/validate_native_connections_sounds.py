"""Validacao nativa isolada, sem acessar contas pessoais."""
import os
import sys
import json
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
inventory=patch('core.connection_verifier.saved_checks',return_value=[('google_drive',lambda:(True,'Conta de demonstracao verificada.'))]);inventory.start()
status=patch('core.resource_policy.external_status',return_value={'connected':True,'configured':True,'account':'Conta de demonstracao'});status.start()
fixture.setUp();window=fixture.window;window.resize(1366,768)
window._ui_sounds.enabled=False
window.get_plugins=lambda:[{'name':'google_drive','valid':True,'enabled':True}]
OUTPUT=BASE/'validation/connections-sounds';OUTPUT.mkdir(parents=True,exist_ok=True)
errors=[];checks=[];finished=False;hub=None

def finish():
    global finished
    if finished:return
    finished=True
    if hub:hub.close()
    result={'checks':checks,'errors':errors}
    (OUTPUT/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    fixture.tearDown();inventory.stop();status.stop();app.quit()

sys.excepthook=lambda kind,error,tb:(errors.append(kind.__name__),finish())

def inspect():
    global hub
    from core.settings_hub import SettingsHub
    import ui
    if window._connection_checks.get('google_drive').get('state')!='connected':errors.append('startup-verification')
    else:checks.append('startup-verifies-saved-account-without-opening-settings')
    hub=SettingsHub(window,ui.API_FILE,ui.C)
    hub.open_page('connections');hub.show();hub.refresh()
    if hub.connections_page.states.get('plugin:google_drive')!='connected':errors.append('shared-state')
    else:checks.append('settings-shares-startup-verification')
    hub.close();hub.deleteLater()
    import ui
    hub=SettingsHub(window,ui.API_FILE,ui.C)
    hub.open_page('connections');hub.show();hub.refresh()
    if hub.connections_page.states.get('plugin:google_drive')!='connected':errors.append('reopened-settings')
    else:checks.append('reopening-settings-keeps-live-verification')
    QTimer.singleShot(500,capture)

def capture():
    hub.grab().save(str(OUTPUT/'connections.png'))
    from PyQt6.QtMultimedia import QSoundEffect
    effects=window._ui_sounds.effects
    if len(effects)<16 or any(effect.status()!=QSoundEffect.Status.Ready for effect in effects.values()):errors.append('sound-assets-not-ready')
    else:checks.append('native-audio-assets-loaded')
    window.showMinimized()
    if window._ui_sounds.visible:errors.append('minimized-audio')
    else:checks.append('minimized-window-suspends-ambient-sound')
    finish()

QTimer.singleShot(3500,inspect)
QTimer.singleShot(18000,lambda:(errors.append('timeout'),finish()))
app.exec()
print(json.dumps({'ok':not errors,'checks':checks,'errors':errors}))
sys.exit(bool(errors))
