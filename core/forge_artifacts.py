"""Read-only saved FORJA components, in isolated native browser profiles."""
import threading
from PyQt6.QtCore import pyqtSignal,QUrl
from PyQt6.QtGui import QColor
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEnginePage,QWebEngineProfile
from core.forge_controller import ForgeRequests

class ArtifactPage(QWebEnginePage):
    expected_origin=None
    def acceptNavigationRequest(self,url,kind,main_frame):
        if url.scheme()=='about':return True
        return url.scheme()=='http' and url.host()=='127.0.0.1' and url.port()==self.expected_origin

class ForgeArtifactView(QWebEngineView):
    ready=pyqtSignal()
    unavailable=pyqtSignal()
    resolved=pyqtSignal(object)
    def __init__(self,parent,window,artifact_id):
        super().__init__(parent);self._ready=False;self.failed=False;self._closing=False;self._url=None;self._visible=True
        self.profile=QWebEngineProfile(self)
        self.interceptor=ForgeRequests(self.profile);self.profile.setUrlRequestInterceptor(self.interceptor)
        self.setPage(ArtifactPage(self.profile,self));self.page().setBackgroundColor(QColor('#000000'))
        self.loadFinished.connect(self._loaded);self.resolved.connect(self._resolved)
        def load():
            try:
                from core.forge_host import runtime_for
                result=runtime_for(window).command('preview_library',artifact_id=artifact_id)
            except Exception:result={'accepted':False}
            try:self.resolved.emit(result)
            except RuntimeError:pass
        threading.Thread(target=load,name='ForgeArtifact',daemon=True).start()

    def _resolved(self,result):
        if self._closing:return
        url=QUrl(str(result.get('preview_url') or ''))
        if not result.get('accepted') or url.scheme()!='http' or url.host()!='127.0.0.1':
            self.failed=True;self.unavailable.emit();return
        self._url=url;self.interceptor.preview_port=url.port();self.page().expected_origin=url.port()
        if self._visible:self.load(url)

    def _loaded(self,ok):
        if self._closing:return
        self._ready=bool(ok)
        if ok:self.ready.emit()
        elif self._url:self.failed=True;self.unavailable.emit()

    def sync(self,payload):
        visible=payload.get('visible',True)
        if self._visible==visible:return
        self._visible=visible
        if visible and self._url:self.load(self._url)
        elif not visible:self.setUrl(QUrl('about:blank'))

    def hideEvent(self,event):
        self.sync({'visible':False});super().hideEvent(event)

    def showEvent(self,event):
        self.sync({'visible':True});super().showEvent(event)

    def closeEvent(self,event):
        self._closing=True;self.stop();super().closeEvent(event)

def pin_artifact(window,data):
    from PyQt6.QtWidgets import QVBoxLayout,QLabel
    from PyQt6.QtCore import Qt
    from core.hud_glass import PinnedPreviewFrame
    import os,re
    identifier=data.get('artifact_id','')
    if not re.fullmatch(r'[0-9a-f]{32}',identifier):raise ValueError('Artefato invalido.')
    key='forge:'+identifier
    if key in window._pin_previews:return
    if key not in window._pin_capacity() and len(window._pin_capacity())>=6:raise ValueError('Ja ha seis previas fixadas.')
    frame=PinnedPreviewFrame(window._scene_stage);frame.set_accent('#67d9ad')
    layout=QVBoxLayout(frame);layout.setContentsMargins(8,8,8,8)
    title=QLabel(str(data.get('title') or 'Criacao FORJA'));title.setTextFormat(Qt.TextFormat.PlainText);layout.addWidget(title)
    label=QLabel('Carregando artefato salvo...');layout.addWidget(label)
    view=None
    if os.environ.get('QT_QPA_PLATFORM')!='offscreen':
        view=ForgeArtifactView(frame,window,identifier);layout.addWidget(view,1)
        view.ready.connect(label.hide);view.unavailable.connect(lambda:label.setText('Artefato salvo indisponivel. Nenhum codigo novo foi gerado.'))
    window._pin_previews[key]={'widget':frame,'view':view,'label':label,'restore':title,'accent':'#67d9ad','data':dict(data),'slot':1}
    if not window._save_pins():
        window._pin_previews.pop(key);frame.deleteLater();raise ValueError('Nao consegui persistir o artefato fixado.')
    frame.show();window._position_pin()
