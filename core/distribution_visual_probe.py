"""Ensaio agendado na entrada real main.py, sem fornecer credenciais."""
import os
from pathlib import Path
from PyQt6.QtCore import QTimer
from core.distribution_health import confirm_window


def schedule(window,app):
    root=Path(os.environ['DIEF_MANAGED_ROOT']);finished=False
    window._ui_sounds.enabled=False
    def finish(ok):
        nonlocal finished
        if finished:return
        finished=True
        if ok:
            folder=root/'validation';folder.mkdir(exist_ok=True)
            window.grab().save(str(folder/'application.png'))
            confirm_window(os.environ['DIEF_READY_FILE'])
            QTimer.singleShot(7000,lambda:(window.close(),app.exit(0)))
        else:window.close();app.exit(1)
    def inspect():
        if finished:return
        core=window.hud._spatial_core
        if core and core._ready and window._environment.started:
            core.page().runJavaScript('window.hologramDiagnostics()',lambda value:finish(True) if value and value.get('coreVisible') and value.get('framesRendered',0)>5 else QTimer.singleShot(100,inspect))
        elif core and core.failed:finish(False)
        else:QTimer.singleShot(100,inspect)
    QTimer.singleShot(100,inspect);QTimer.singleShot(60000,lambda:finish(False))
