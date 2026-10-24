"""Read-only WebEngine scene diagnostic, independent of voice and credentials."""
import json
import sys
from pathlib import Path
from PyQt6.QtCore import QTimer, QUrl
from PyQt6.QtWidgets import QApplication
from PyQt6.QtWebEngineCore import QWebEnginePage
from PyQt6.QtWebEngineWidgets import QWebEngineView


class Page(QWebEnginePage):
    def javaScriptConsoleMessage(self, level, message, line, source):
        print('CONSOLE', level.name, Path(source).name, line, message, flush=True)


app = QApplication(sys.argv)
root = Path(sys.argv[1]).resolve()
output = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else root.parents[1]
views = []
for document in ('index.html', 'space.html', 'presentation.html'):
    view = QWebEngineView()
    view.setPage(Page(view))
    view.resize(960, 700)
    view.loadFinished.connect(lambda ok, name=document: print('LOADED', name, ok, flush=True))
    view.load(QUrl.fromLocalFile(str(root / document)))
    view.show()
    views.append((document, view))


def inspect():
    for name, view in views:
        view.page().runJavaScript("({dataset:{...document.body.dataset},canvas:document.querySelectorAll('canvas').length,core:window.hologramDiagnostics?.(),space:window.spaceDiagnostics?.()})",
            lambda result, name=name: print('RESULT', name, json.dumps(result), flush=True))
        view.grab().save(str(output / ('probe-' + name + '.png')))
    QTimer.singleShot(1000, app.quit)


QTimer.singleShot(12000, inspect)
app.exec()
