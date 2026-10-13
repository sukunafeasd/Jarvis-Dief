"""Native UIA verification on our own harmless test button; no account login."""
import json
import sys
import threading
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PyQt6.QtCore import QTimer, QObject, pyqtSignal
from PyQt6.QtWidgets import QApplication, QDialog, QVBoxLayout, QPushButton
from core.windows_accessibility import operate
from core.plugin_loader import discover_plugins
from core.settings_hub import SettingsHub
import ui

app=QApplication(sys.argv)
dialog=QDialog();dialog.setWindowTitle("Jarvis teste de acessibilidade")
layout=QVBoxLayout(dialog);button=QPushButton("Verificar controle");layout.addWidget(button)
clicks=[];button.clicked.connect(lambda:clicks.append(True));dialog.show()
result={};exit_code=1

class Bridge(QObject):
    done=pyqtSignal(dict)
bridge=Bridge()

def inspect():
    handle=int(dialog.winId())
    def worker():
        try:
            snapshot=operate({"action":"inspect","handle":handle})
            buttons=[c for c in snapshot.get("controls",[]) if c["name"]=="Verificar controle" and c["type"]=="Button"]
            clicked=operate({"action":"invoke","handle":handle,"name":"Verificar controle","type":"Button"}) if len(buttons)==1 else {"ok":False}
            bridge.done.emit({"inspection_ok":snapshot.get("ok"),"button_identified":len(buttons)==1,"invoke_ok":clicked.get("ok")})
        except Exception as error:
            bridge.done.emit({"error":type(error).__name__})
    threading.Thread(target=worker,daemon=True).start()

def finish(value):
    result.update(value)
    QTimer.singleShot(600,capture)

def capture():
    global exit_code,window,hub
    result["native_button_clicked"]=len(clicks)==1
    dialog.close()
    registry=discover_plugins(ui.BASE_DIR/"plugins",set(),logger=lambda _:None)
    window=ui.MainWindow(str(ui.BASE_DIR/"core/face_model.obj"))
    window.get_plugins=registry.list_for_ui
    hub=SettingsHub(window,ui.API_FILE,ui.C)
    hub.navigation.setCurrentRow(3);hub.show()
    def save():
        global exit_code
        hub.grab().save(str(ui.BASE_DIR/"validation/connections-native.png"))
        result["plugins"]=[p["name"] for p in registry.list_for_ui() if p["valid"]]
        (ui.BASE_DIR/"validation/connections-native.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
        print(json.dumps(result),flush=True)
        exit_code=0 if all(result.get(key) for key in ("inspection_ok","button_identified","invoke_ok","native_button_clicked")) else 1
        hub.close();window.close();app.quit()
    QTimer.singleShot(1000,save)

bridge.done.connect(finish)
QTimer.singleShot(1200,inspect);QTimer.singleShot(20000,app.quit)
app.exec();sys.exit(exit_code)
