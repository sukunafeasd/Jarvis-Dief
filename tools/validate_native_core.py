"""Short, isolated native Qt renderer smoke test; never connects to Gemini."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication
import ui

app = QApplication(sys.argv)
window = ui.MainWindow(str(ui.BASE_DIR / "core/face_model.obj"))
window.show()
if window._overlay:
    window._overlay.hide()
window.hud.hud_style = "core"
window.hud.state = "LISTENING"
exit_code = 1

def inspect():
    view = window.hud._spatial_core
    if not view:
        finish(None)
        return
    view.page().runJavaScript("({ready:document.body.dataset.ready,phase:document.body.dataset.phase,calls:document.body.dataset.drawCalls})", finish)

def finish(result):
    global exit_code
    print("Native core:", result, flush=True)
    if isinstance(result, dict) and result.get("ready") == "true":
        window.grab().save(str(ui.BASE_DIR / "validation/core-native.png"))
        exit_code = 0
    window.close()
    app.quit()

QTimer.singleShot(6500, inspect)
QTimer.singleShot(15000, app.quit)
app.exec()
sys.exit(exit_code)
