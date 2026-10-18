"""Native FORJA scene coordinator. Generated previews never receive the host bridge."""
import json
import threading
import time
from pathlib import Path
from urllib.parse import unquote

from PyQt6.QtCore import QObject,QTimer,QUrl,Qt,QEvent,pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWebEngineCore import QWebEnginePage,QWebEngineProfile,QWebEngineSettings,QWebEngineUrlRequestInterceptor
from PyQt6.QtWebEngineWidgets import QWebEngineView

SPATIAL=Path(__file__).parent/'spatial'


class ForgeRequests(QWebEngineUrlRequestInterceptor):
    preview_port=None
    def interceptRequest(self,info):
        url=info.requestUrl()
        if url.scheme() in ('about','data','blob','qrc'):return
        if url.isLocalFile():
            try:Path(url.toLocalFile()).resolve().relative_to(SPATIAL.resolve());return
            except ValueError:pass
        if url.scheme()=='http' and url.host()=='127.0.0.1' and url.port()==self.preview_port:return
        info.block(True)


class ForgePage(QWebEnginePage):
    def acceptNavigationRequest(self,url,kind,main_frame):
        if main_frame:
            return url.isLocalFile() and Path(url.toLocalFile()).resolve()==(SPATIAL/'forja.html').resolve()
        return url.scheme() in ('about','data','blob') or url.scheme()=='http' and url.host()=='127.0.0.1'


class ForgeController(QObject):
    snapshot_ready=pyqtSignal(object)
    validation_ready=pyqtSignal(object)

    def __init__(self,window):
        super().__init__(window)
        self.window=window;self.phase='normal';self.generation=0;self.view=None
        self._request=None;self._saved=[];self._polling=False;self._snapshot={};self._signature=''
        self._deadline=0.;self._transition_started=False;self._entrance_started=False
        self._command_serial=-1
        self.timer=QTimer(self);self.timer.setInterval(80);self.timer.timeout.connect(self._tick)
        self.poll_timer=QTimer(self);self.poll_timer.setInterval(1000);self.poll_timer.timeout.connect(self._poll)
        self.snapshot_ready.connect(self._update)
        self.validation_ready.connect(self._validated)
        self._validating=None;self._validated_revisions=set()
        self._core_host=None;self._hud_sync=None
        self._view_failed=False
        window._scene_stage.installEventFilter(self)

    @property
    def active(self):return self.phase!='normal'

    def eventFilter(self,watched,event):
        if event.type()==QEvent.Type.Resize and self.active:self.layout()
        return False

    def _create_view(self):
        if self.view:
            if self._view_failed:
                self._view_failed=False
                self._command_serial=-1
                self.view.load(QUrl.fromLocalFile(str(SPATIAL/'forja.html')))
            return
        self.profile=QWebEngineProfile(self)
        self.interceptor=ForgeRequests(self.profile);self.profile.setUrlRequestInterceptor(self.interceptor)
        self.view=QWebEngineView(self.window._scene_stage)
        self.view.setPage(ForgePage(self.profile,self.view))
        self.view.page().setBackgroundColor(QColor('#000000'))
        self.view.settings().setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls,True)
        self.view.page().urlChanged.connect(self._navigation)
        self.view.page().renderProcessTerminated.connect(self._renderer_failed)
        self.view.loadFinished.connect(self._loaded)
        self.view.load(QUrl.fromLocalFile(str(SPATIAL/'forja.html')))
        self.view.hide()

    def _loaded(self,ok):
        if not ok:
            self._view_failed=True
            if self.active:self._fail('Nao consegui carregar a interface da Forja.')

    def _renderer_failed(self,*_):
        self._view_failed=True
        if self.active:self._fail('A tela da Forja foi encerrada; o projeto foi preservado.')

    def _navigation(self,url):
        fragment=url.fragment()
        if fragment.startswith('window-fullscreen-'):
            self.window._fullscreen_key(self.window);return
        if not fragment.startswith('forge-command-') or self.phase!='ready':return
        try:
            data=json.loads(unquote(fragment[len('forge-command-'):]))
            if not isinstance(data,dict):return
            serial=data.get('serial')
            if type(serial) is not int or serial<=self._command_serial or data.get('action') not in ('prompt','exit'):return
            self._command_serial=serial
            data={key:value for key,value in data.items() if key in ('action','prompt')}
            callback=getattr(self.window,'on_forge_command',None)
            if callback:callback(data)
        except (ValueError,TypeError):pass

    def request(self,packet):
        action=packet.get('action')
        if action=='enter':
            if self.active:
                self._finish(packet,{'ok':self.phase=='ready','phase':self.phase});return
            if not self.window._ready:
                self._finish(packet,{'ok':False,'error':'Configure a IA principal antes de entrar na Forja.'});return
            self.window._cancel_neural_memory()
            self.generation+=1;self._request=packet;self.phase='preparing'
            self._deadline=time.monotonic()+25;self._transition_started=False;self._entrance_started=False
            self._signature=''
            self._saved=[]
            self._old_style=self.window.hud.hud_style;self.window.hud.hud_style='core'
            for widget in self._ordinary_widgets():
                self._saved.append((widget,widget.isVisible()));widget.hide()
            for animation in getattr(self.window,'_scene_animations',[]):animation.stop()
            self.window._settle_timer.stop()
            self.window._center_split.setGeometry(self.window._scene_stage.rect());self.window._center_split.show()
            self._take_core()
            self._create_view();self.layout();self.timer.start();return
        if action=='exit':
            if not self.active:self._finish(packet,{'ok':True,'phase':'normal'});return
            if self._request:self._finish(self._request,{'ok':False,'cancelled':True})
            self.generation+=1;self._request=packet;self.phase='exiting';self._deadline=time.monotonic()+12
            self._exit_started=False;self._return_started=False;self.timer.start();return
        if action=='snapshot':self._update(packet.get('snapshot',{}));self._finish(packet,{'ok':True});return
        self._finish(packet,{'ok':False,'error':'Comando de cena desconhecido.'})

    def _ordinary_widgets(self):
        widgets=[]
        for name in ('_floating_controls','_title_lbl','_clock_lbl','_date_lbl','_content_panel','_terminal','_execution'):
            value=getattr(self.window,name,None)
            if value is not None:widgets.append(value)
        refresh=getattr(self.window,'_daily_refresh_view',None)
        if refresh is not None:refresh.hide()
        for pin in getattr(self.window,'_pin_previews',{}).values():
            widget=pin.get('widget')
            if widget is not None:widgets.append(widget)
        visual=getattr(self.window,'_visual_scene',None)
        layer=getattr(visual,'layer',None)
        if layer is not None:widgets.append(layer)
        for fragment in getattr(visual,'fragments',{}).values():
            widget=getattr(fragment,'view',None)
            if widget is not None:widgets.append(widget)
        return widgets

    def layout(self):
        if not self.active:return
        if self.view:self.view.setGeometry(self.window._scene_stage.rect())
        core=getattr(self.window.hud,'_spatial_core',None)
        if self._core_host and core:core.setGeometry(self.window._scene_stage.rect())
        if self.phase in ('preparing','travelling','blackout','returning'):
            self.window._center_split.setGeometry(self.window._scene_stage.rect())
        if self.view and self.phase in ('blackout','emerging','ready','exiting'):self.view.raise_()

    def _take_core(self):
        core=getattr(self.window.hud,'_spatial_core',None)
        if not core or self._core_host:return
        hud=self.window.hud
        self._core_host=(core.parentWidget(),core.geometry(),core.isVisible())
        self._hud_sync=(hud._sync_spatial_core,'_sync_spatial_core' in hud.__dict__)
        # The HUD timer owns a shorter avatar rectangle. Suspend that ownership
        # while the existing WebEngine occupies the native stage.
        hud._sync_spatial_core=lambda now:None
        core.setParent(self.window._scene_stage);core.setGeometry(self.window._scene_stage.rect())
        core.show();core.raise_();core.sync({**core._payload,'visible':True})

    def _release_core(self):
        core=getattr(self.window.hud,'_spatial_core',None)
        if self._core_host and core:
            parent,geometry,visible=self._core_host
            core.setParent(parent);core.setGeometry(geometry);core.setVisible(visible)
        self._core_host=None
        if self._hud_sync:
            callback,was_instance=self._hud_sync
            if was_instance:self.window.hud._sync_spatial_core=callback
            else:del self.window.hud._sync_spatial_core
            self._hud_sync=None

    def _tick(self):
        if not self.active:self.timer.stop();return
        if time.monotonic()>self._deadline and self.phase!='ready':
            self._fail('A transicao da Forja nao concluiu. Restaurei o Jarvis; o projeto permanece salvo.');return
        core=getattr(self.window.hud,'_spatial_core',None)
        if self.phase=='preparing':
            if not core or not core._ready or not self.view:return
            token=self.generation
            self.view.page().runJavaScript('Boolean(window.forgeReady)',lambda ready:self._begin_travel(ready,token))
        elif self.phase=='travelling' and core:
            token=self.generation
            core.page().runJavaScript('window.forgeTransitionPhase',lambda phase:self._blackout(phase,token))
        elif self.phase=='emerging' and self.view:
            token=self.generation
            self.view.page().runJavaScript('window.forgeScenePhase',lambda phase:self._ready(phase,token))
        elif self.phase=='blackout' and time.monotonic()>=self._black_until:
            self.phase='emerging'
            self.view.page().runJavaScript('window.beginForgeEntrance && window.beginForgeEntrance('+json.dumps({'reduced':self.window.hud.motion_reduced})+')')
        elif self.phase=='exiting':
            if not self._exit_started:
                self._exit_started=True
                if self.view and self.view.isVisible():self.view.page().runJavaScript('window.exitForgeScene && window.exitForgeScene('+json.dumps({'reduced':self.window.hud.motion_reduced})+')')
                else:self._return('exited',self.generation)
            elif self.view:
                token=self.generation
                self.view.page().runJavaScript('window.forgeScenePhase',lambda phase:self._return(phase,token))
        elif self.phase=='returning' and core:
            token=self.generation
            core.page().runJavaScript('window.forgeTransitionPhase',lambda phase:self._returned(phase,token))

    def _begin_travel(self,ready,token):
        if token!=self.generation or self.phase!='preparing' or not ready:return
        core=getattr(self.window.hud,'_spatial_core',None)
        if core:core.page().runJavaScript('!window.neuralMemoryDiagnostics?.().active',lambda settled:self._start_travel(settled,token))

    def _start_travel(self,settled,token):
        if token!=self.generation or self.phase!='preparing' or not settled:return
        self._take_core()
        self.phase='travelling';core=self.window.hud._spatial_core
        core.page().runJavaScript('window.enterForgeTransition && window.enterForgeTransition('+json.dumps({'reduced':self.window.hud.motion_reduced})+')')
        space=getattr(self.window,'_space_view',None)
        if space:space.page().runJavaScript('window.enterForgeTransition && window.enterForgeTransition('+json.dumps({'reduced':self.window.hud.motion_reduced})+')')

    def _blackout(self,phase,token):
        if token!=self.generation or self.phase!='travelling' or phase!='blackout':return
        self.phase='blackout';self._black_until=time.monotonic()+.24
        self.window._center_split.hide();self.view.show();self.view.raise_()
        self.view.page().runJavaScript('window.updateForge && window.updateForge({visible:true})')
        core=getattr(self.window.hud,'_spatial_core',None)
        if core:core.hide()
        space=getattr(self.window,'_space_view',None)
        if space:space.sync({'visible':False})

    def _ready(self,phase,token):
        if token!=self.generation or self.phase!='emerging' or phase!='ready':return
        self.phase='ready';self.timer.stop();self.poll_timer.start();self._poll()
        self.view.setFocus()
        self._finish(self._request,{'ok':True,'phase':'ready'});self._request=None

    def _return(self,phase,token):
        if token!=self.generation or self.phase!='exiting' or phase!='exited':return
        self.phase='returning';self.poll_timer.stop();self.window._center_split.show()
        core=getattr(self.window.hud,'_spatial_core',None)
        if self.view:self.view.hide()
        if core:
            core.show();core.raise_();core.sync({**core._payload,'visible':True})
            core.page().runJavaScript('window.exitForgeTransition && window.exitForgeTransition('+json.dumps({'reduced':self.window.hud.motion_reduced})+')')
        else:self._returned('normal',token)
        space=getattr(self.window,'_space_view',None)
        if space:
            space.sync({'visible':True})
            space.page().runJavaScript('window.exitForgeTransition && window.exitForgeTransition()')

    def _returned(self,phase,token):
        if token!=self.generation or self.phase!='returning' or phase!='normal':return
        packet=self._request;self._restore();self._finish(packet,{'ok':True,'phase':'normal'})

    def _poll(self):
        runtime=getattr(self.window,'_forge_runtime',None)
        if not runtime or self._polling or self.phase!='ready':return
        token=object();self._polling=token;generation=self.generation
        def read():
            try:snapshot=runtime.snapshot()
            except Exception:snapshot={'phase':'error','error':'Motor da Forja indisponivel. O projeto foi preservado.'}
            try:self.snapshot_ready.emit({'poll_token':token,'generation':generation,'snapshot':snapshot})
            except RuntimeError:pass
        threading.Thread(target=read,name='ForgeSceneSnapshot',daemon=True).start()

    def _update(self,snapshot):
        if not isinstance(snapshot,dict):return
        if 'poll_token' in snapshot:
            if snapshot['poll_token'] is not self._polling:return
            self._polling=False
            if snapshot.get('generation')!=self.generation:return
            snapshot=snapshot.get('snapshot')
        if self.phase!='ready' or not isinstance(snapshot,dict):return
        from core.forge_status import snapshot_current
        if not snapshot_current(snapshot,getattr(self.window,'_forge_runtime',None)):return
        if (type(snapshot.get('serial')) is int and type(self._snapshot.get('serial')) is int
                and snapshot['serial']<self._snapshot['serial']):return
        self._snapshot=snapshot
        preview=QUrl(str(snapshot.get('preview_url') or ''))
        self.interceptor.preview_port=preview.port() if preview.scheme()=='http' and preview.host()=='127.0.0.1' else None
        revision=snapshot.get('candidate_revision')
        candidate=snapshot.get('candidate_preview_url')
        project=snapshot.get('project') or {}
        validation_key=(project.get('id'),revision,candidate)
        if candidate and revision and snapshot.get('phase')!='running' and self._validating is None and validation_key not in self._validated_revisions:
            self._validating=validation_key
            generation=self.generation
            runtime=getattr(self.window,'_forge_runtime',None)
            def validate():
                if generation!=self.generation or self.phase!='ready':return
                try:
                    from core.forge_validation import validate_candidate
                    evidence=validate_candidate(candidate)
                    if generation!=self.generation or self.phase!='ready':return
                    result=runtime.command('validate_preview',project_id=validation_key[0],revision=revision,candidate_url=candidate,evidence=evidence)
                except Exception as error:result={'accepted':False,'error':'Previa ainda nao validada ('+type(error).__name__+').'}
                try:self.validation_ready.emit({'revision':revision,'key':validation_key,'result':result,'generation':generation})
                except RuntimeError:pass
            threading.Thread(target=validate,name='ForgePreviewValidation',daemon=True).start()
        from core.forge_status import project_snapshot
        projected=project_snapshot(snapshot)
        signature=json.dumps(projected,sort_keys=True,ensure_ascii=False,default=str)
        if self.phase=='ready' and self.view and signature!=self._signature:
            self._signature=signature
            self.view.page().runJavaScript('window.updateForge && window.updateForge('+json.dumps(projected,ensure_ascii=False,default=str)+')')
            callback=getattr(self.window,'on_forge_snapshot',None)
            if callback:callback(snapshot)

    def _validated(self,payload):
        if self.phase!='ready' or payload.get('generation',self.generation)!=self.generation:return
        key=payload.get('key')
        if self._validating==key:self._validating=None
        current=(self._snapshot.get('project') or {}).get('id'),self._snapshot.get('candidate_revision'),self._snapshot.get('candidate_preview_url')
        if key!=current:return
        result=payload['result']
        if result.get('accepted') or result.get('validation_failed'):self._validated_revisions.add(key)
        if result.get('retryable'):return
        if not result.get('accepted'):
            self.window._log.append_log('SYS: '+str(result.get('error') or 'Previa nao validada. Mantive a ultima versao utilizavel.'))
        self._poll()

    def _restore(self):
        self.generation+=1;self.phase='normal';self.timer.stop();self.poll_timer.stop()
        self._polling=False;self._validating=None
        if self.view:
            self.view.page().runJavaScript('window.updateForge && window.updateForge({visible:false})');self.view.hide()
        self.window.hud.hud_style=getattr(self,'_old_style',self.window.hud.hud_style)
        core=getattr(self.window.hud,'_spatial_core',None)
        if core:
            core.show();core.sync({**core._payload,'visible':True})
            core.page().runJavaScript('window.exitForgeTransition && window.exitForgeTransition({reduced:true})')
        self._release_core()
        for widget,visible in self._saved:widget.setVisible(visible)
        self._saved=[];self._request=None
        self.window._center_split.show();self.window._layout_scene()
        if not getattr(self.window,'_pins_restored',True):QTimer.singleShot(0,self.window._restore_saved_pins)
        space=getattr(self.window,'_space_view',None)
        if space:
            space.sync({'visible':True})
            space.page().runJavaScript('window.exitForgeTransition && window.exitForgeTransition({reduced:true})')

    def _fail(self,message):
        self._view_failed=True
        packet=self._request;self._restore();self._finish(packet,{'ok':False,'error':message})
        self.window._log.append_log('SYS: '+message)
        callback=getattr(self.window,'on_forge_scene_failure',None)
        if callback:callback(self.generation)

    @staticmethod
    def _finish(packet,result):
        if packet is not None:
            packet['result']=result
            done=packet.get('done')
            if done:done.set()

    def close(self):
        self.timer.stop();self.poll_timer.stop();self.generation+=1
        self._polling=False;self._validating=None;self.phase='normal'
        self._release_core()
        self._finish(self._request,{'ok':False,'cancelled':True});self._request=None
        if self.view:self.view.stop();self.view.close()
