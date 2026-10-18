"""Local-only Three.js view of the user's alpha12 core."""
import json
import time
from pathlib import Path
from PyQt6.QtCore import QUrl, QTimer, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings
from PyQt6 import sip


class LocalPage(QWebEnginePage):
    def acceptNavigationRequest(self, url, kind, main_frame):
        return url.isLocalFile() or url.scheme() == "about"


class SpatialCoreView(QWebEngineView):
    unavailable = pyqtSignal()
    ready = pyqtSignal()
    ultron_unavailable = pyqtSignal()
    neural_finished = pyqtSignal(str)
    def __init__(self, parent, document="index.html"):
        super().__init__(parent)
        self.setPage(LocalPage(self))
        self.page().setBackgroundColor(QColor('transparent') if document=='index.html' else QColor("#00060a"))
        self.settings().setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, False)
        self._loaded = False
        self.failed = False
        self._closing=False
        self._ready=False
        self._created = time.monotonic()
        self._payload = {}
        self._news_payload = None
        self._neural_payload = None
        self._neural_observed = {}
        self._ultron_payload=None
        self._news_sent = False
        self._environment_payload = {'staging':True} if document=='index.html' else None
        self._environment_sent = False
        self.loadFinished.connect(self._on_loaded)
        self.page().renderProcessTerminated.connect(lambda *_: self._fail())
        self.page().urlChanged.connect(self._window_key)
        self._health = QTimer(self)
        self._health.timeout.connect(self._check_health)
        self._health.start(1000)
        url=QUrl.fromLocalFile(str(Path(__file__).parent / "spatial" / document))
        if document in ('index.html','space.html'):url.setQuery('staged=1')
        self.load(url)

    def _on_loaded(self, ok):
        if not self._alive():return
        self._loaded = ok
        if ok:
            self.page().runJavaScript("""if(!window.diefWindowKeys){window.diefWindowKeys=true;let serial=0;
                addEventListener('keydown',event=>{if(event.key==='F11'&&!event.repeat){
                    event.preventDefault();event.stopImmediatePropagation();location.hash='window-fullscreen-'+(++serial);
                }},true);} """)
            self._created=time.monotonic()
            self.sync(self._payload)
            if self._ultron_payload:self.sync_ultron(self._ultron_payload)
            self._news_sent=False
            self.sync_news(self._news_payload)
            if self._neural_payload:
                payload=self._neural_payload
                self.sync_neural({'requestId':payload.get('requestId'),'pending':True})
                self.sync_neural(payload)
            self._environment_sent = False
            self.sync_environment(self._environment_payload)
        else:
            self._fail()

    def _window_key(self,url):
        if not url.fragment().startswith('window-fullscreen-'):return
        owner=self.window()
        if hasattr(owner,'_fullscreen_key'):owner._fullscreen_key(owner)

    def _fail(self):
        if not self._alive() or self.failed:return
        self.failed = True
        self._health.stop()
        self.hide()
        self.unavailable.emit()

    def _check_health(self):
        if not self._alive() or self.failed:return
        if not self._loaded and time.monotonic()-self._created>20:
            self._fail()
        elif self._loaded:
            self.page().runJavaScript("({ready:document.body.dataset.ready,error:document.body.dataset.error,ultronError:document.body.dataset.ultronError,neural:window.neuralMemoryDiagnostics?.()})", self._health_result)

    def _health_result(self, result):
        if not self._alive() or self.failed:return
        if isinstance(result,dict) and isinstance(result.get('neural'),dict):
            self._neural_observed=result['neural']
            cached=self._neural_payload or {}
            if not result['neural'].get('active') and cached.get('active') and cached.get('requestId')==result['neural'].get('requestId'):
                self._neural_payload=None
                self.neural_finished.emit(str(cached['requestId']))
        if isinstance(result,dict) and result.get('ultronError') and not getattr(self,'_ultron_failed',False):
            self._ultron_failed=True;self.ultron_unavailable.emit()
        if isinstance(result, dict) and (result.get("error") or
                (not result.get("ready") and time.monotonic() - self._created > 20)):
            self._fail()
            return
        if isinstance(result,dict) and result.get('ready') and not self._ready:
            self._ready=True
            self.ready.emit()

    def _alive(self):
        return not self._closing and not sip.isdeleted(self)

    def closeEvent(self,event):
        self._closing=True;self._loaded=False;self._health.stop()
        super().closeEvent(event)

    def sync(self, payload):
        self._payload = payload
        if self._alive() and self._loaded and not self.failed:
            self.page().runJavaScript("window.updateCore && window.updateCore(" + json.dumps(payload) + ")")

    def sync_neural(self,payload):
        self._neural_payload=payload
        if self._alive() and self._loaded and not self.failed:
            self.page().runJavaScript('window.updateNeuralMemory && window.updateNeuralMemory('+json.dumps(payload,ensure_ascii=False)+')')

    def cancel_neural(self):
        self._neural_payload=None
        if self._alive() and self._loaded and not self.failed:
            self.page().runJavaScript('window.cancelNeuralMemory && window.cancelNeuralMemory()')

    def narrate_neural(self,text):
        if self._alive() and self._loaded and not self.failed and self._neural_payload:
            self.page().runJavaScript('window.narrateNeuralMemory && window.narrateNeuralMemory('+json.dumps(str(text)[:1200],ensure_ascii=False)+')')

    def sync_ultron(self,payload):
        self._ultron_payload=payload
        if self._alive() and self._loaded and not self.failed:
            self.page().runJavaScript('window.updateUltron && window.updateUltron('+json.dumps(payload,ensure_ascii=False)+')')

    def advance_ultron(self,beat):
        if self._alive() and self._loaded and not self.failed:
            self.page().runJavaScript('window.advanceUltron && window.advanceUltron('+json.dumps(beat,ensure_ascii=False)+')')

    def sync_news(self, payload):
        if payload == self._news_payload and self._news_sent:
            return
        self._news_payload = payload
        self._news_sent=False
        if self._alive() and self._loaded and not self.failed:
            def delivered(ok):
                if ok and payload == self._news_payload:
                    self._news_sent=True
            self.page().runJavaScript("Boolean(window.updateNewsCore && (window.updateNewsCore(" + json.dumps(payload) + "), true))",delivered)

    def sync_environment(self, payload):
        if payload is None or (payload == self._environment_payload and self._environment_sent):
            return
        self._environment_payload = payload
        self._environment_sent = False
        if self._alive() and self._loaded and not self.failed:
            def delivered(ok):
                if ok and payload == self._environment_payload:
                    self._environment_sent = True
            self.page().runJavaScript("Boolean(window.updateEnvironment && (window.updateEnvironment(" +
                                      json.dumps(payload) + "), true))", delivered)

    def hideEvent(self, event):
        self.sync({**self._payload, "visible": False})
        super().hideEvent(event)

    def showEvent(self, event):
        self.sync({**self._payload, "visible": True})
        super().showEvent(event)
