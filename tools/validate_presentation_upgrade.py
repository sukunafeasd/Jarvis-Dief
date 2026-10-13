"""Native composition check using synthetic data, never connected accounts."""
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import ui
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

app=QApplication(sys.argv)
folder=tempfile.TemporaryDirectory()
config=patch.object(ui,'API_FILE',Path(folder.name)/'empty.json')
config.start()
window=ui.MainWindow(str(ui.BASE_DIR/'core/face_model.obj'))
window.show()
if window._overlay:
    window._overlay.hide()
window.hud.hud_style='core'
window._apply_state('LISTENING')
weather={'kind':'weather','title':'CLIMA · DEMONSTRAÇÃO','city':'Porto Alegre','temperature':19,
         'condition':'Chuva','code':61,'rain':80,'wind':12,'humidity':75,'narrationDriven':False}
window._show_manifestation(weather)
results=[]

def capture(name):
    window.grab().save(str(ui.BASE_DIR/f'validation/upgrade-native-{name}.png'))
    results.append(window.interface_snapshot())

def gmail():
    capture('weather')
    window._apply_interface_request({'action':'pin','done':__import__('threading').Event()})
    window._show_manifestation({'kind':'gmail','title':'GMAIL · DEMONSTRAÇÃO','narrationDriven':False,
        'items':[{'title':'Confirmação da reunião de amanhã','detail':'Equipe · exemplo sem conta conectada'},
                 {'title':'Documentos disponíveis para revisão','detail':'Projeto · exemplo sem conta conectada'}]})
    QTimer.singleShot(4000,whatsapp)

def whatsapp():
    capture('gmail-core')
    window.hud.hud_style='face'
    window._show_manifestation({'kind':'whatsapp','title':'WHATSAPP · DEMONSTRAÇÃO','narrationDriven':False,
        'items':[{'title':'Grupo de estudo','detail':'Podemos revisar o material amanhã?','value':'2'},
                 {'title':'Equipe do projeto','detail':'A reunião começa às 14h.','value':'1'}]})
    QTimer.singleShot(4000,finish)

def finish():
    capture('whatsapp-face')
    print('Native presentation snapshots:',len(results),'pins:',len(window._pin_previews))
    window.close();app.quit();config.stop();folder.cleanup()

QTimer.singleShot(4000,gmail)
app.exec()
