"""Render real weather inside both native avatars, without changing preferences."""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ui
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication
from actions.weather_report import weather_action
from actions.web_search import fetch_news_package

weather = json.loads(weather_action({"city": "Porto Alegre"}))
if not weather["ok"]:
    raise RuntimeError(weather["error"])
app = QApplication(sys.argv)
window = ui.MainWindow(str(ui.BASE_DIR / "core/face_model.obj"))
window.show()
if window._overlay:
    window._overlay.hide()
window.hud.hud_style = "face"
window._apply_state("LISTENING")
window._show_manifestation(weather["weather"])
status = {"ok": True}

def capture_face():
    window.grab().save(str(ui.BASE_DIR / "validation/weather-native-face.png"))
    if not window._content_spatial or window._content_spatial.failed:
        status["ok"] = False
    window.hud.hud_style = "core"
    QTimer.singleShot(6000, capture_core)

def capture_core():
    window.grab().save(str(ui.BASE_DIR / "validation/weather-native-core.png"))
    window._content_spatial.page().runJavaScript("({kind:document.body.dataset.kind,ready:document.body.dataset.ready,calls:document.body.dataset.drawCalls})", finish)

def finish(result):
    print("Native presentation:", result, "healthy:", status["ok"])
    if result.get("kind") != "weather" or result.get("ready") != "true":
        status["ok"] = False
    package=fetch_news_package("ciência Brasil")
    print('News records:',len(package['model']['items']),'real images:',sum(bool(i.get('image')) for i in package['model']['items']))
    window._show_manifestation({**package['model'],'narrationDriven':False})
    QTimer.singleShot(4000,finish_news)

def finish_news():
    window.grab().save(str(ui.BASE_DIR / "validation/news-native.png"))
    window.close();app.quit()

QTimer.singleShot(6000, capture_face)
app.exec()
sys.exit(0 if status["ok"] else 1)
