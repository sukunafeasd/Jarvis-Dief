"""Desktop presence using the existing Three.js model and the current voice session."""
import ctypes
import math
import os
import time
from collections import deque
from PyQt6.QtCore import Qt,QTimer,QRect,QPoint,QSize,QPropertyAnimation,QEasingCurve,pyqtSignal,QAbstractNativeEventFilter
from PyQt6.QtGui import QRegion,QGuiApplication
from PyQt6.QtWidgets import QWidget,QVBoxLayout,QLabel


class EscapeFilter(QAbstractNativeEventFilter):
    def __init__(self,window):super().__init__();self.window=window
    def nativeEventFilter(self,eventType,message):
        from ctypes import wintypes
        msg=wintypes.MSG.from_address(int(message))
        if msg.message==0x0312 and msg.wParam==self.window.HOTKEY:
            QTimer.singleShot(0,self.window.request_return);return True,0
        return False,0


def clamped_rect(rect,area):
    size=min(rect.width(),rect.height(),area.width(),area.height())
    return QRect(max(area.left(),min(rect.x(),area.right()-size+1)),
                 max(area.top(),min(rect.y(),area.bottom()-size+1)),size,size)


class SpectroWindow(QWidget):
    return_requested=pyqtSignal()
    failed=pyqtSignal()
    ready=pyqtSignal()
    user_moved=pyqtSignal()
    HOTKEY=0x4D53

    def __init__(self,owner,view_factory=None):
        super().__init__(None,Qt.WindowType.Tool|Qt.WindowType.FramelessWindowHint|
                         Qt.WindowType.WindowStaysOnTopHint|Qt.WindowType.WindowDoesNotAcceptFocus)
        self.owner=owner;self._drag=None;self._closed=False;self._hotkey=None
        self.setWindowTitle('DIEF JARVIS - Espectro')
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setWindowOpacity(.68)
        if view_factory is None:
            from core.spatial_view import SpatialCoreView
            view_factory=SpatialCoreView
        self.view=view_factory(self)
        self.view.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout=QVBoxLayout(self);layout.setContentsMargins(0,0,0,0);layout.addWidget(self.view)
        self.view.ready.connect(self._ready)
        self.view.unavailable.connect(self.failed)
        self.timer=QTimer(self);self.timer.setInterval(100);self.timer.timeout.connect(self.sync)
        self._animation=QPropertyAnimation(self,b'geometry',self)
        self._animation.setDuration(260);self._animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._opacity_animation=QPropertyAnimation(self,b'windowOpacity',self)
        self._opacity_animation.setDuration(240)
        self._opacity_animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.capture_excluded=False
        self._observation_badge=QLabel('\u25c9',self)
        self._observation_badge.setStyleSheet('color:#54dcff;background:transparent;font-size:18px;')
        self._observation_badge.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._observation_badge.setToolTip('Observacao autorizada');self._observation_badge.hide()

    def _ready(self):
        if self._closed:return
        self.view.sync_environment({'staging':False,'entrance':None,'mode':'assistant'})
        self.sync();self.ready.emit()

    def sync(self):
        hud=self.owner.hud
        controller=getattr(self.owner,'_spectro_controller',None)
        observing=bool(controller and controller.observer and controller.observer.enabled)
        self._observation_badge.setVisible(observing)
        self._observation_badge.setGeometry(self.width()//2-10,self.height()-35,22,24);self._observation_badge.raise_()
        phase={'PROCESSING':'executing','THINKING':'thinking','ERROR':'error','WARNING':'warning',
               'OFFLINE':'offline','SLEEPING':'sleeping'}.get(hud.state,'idle')
        if hud.speaking:phase='speaking'
        elif hud.state=='LISTENING' or hud._amp_disp>.02 and hud.state in ('IDLE','READY'):phase='listening'
        if hud.muted or hud.resting:phase='sleeping'
        color=getattr(self.owner,'_spectro_color',lambda:'#ff303b')()
        self.view.sync({'visible':self.isVisible(),'phase':phase,'level':hud._amp_disp,'color':color,
                        'motion':'reduced' if hud.motion_reduced else 'full','resting':hud.resting})

    def resizeEvent(self,event):
        # OS-level input region: transparent desktop outside the hologram stays clickable.
        self.setMask(QRegion(self.rect(),QRegion.RegionType.Ellipse))
        super().resizeEvent(event)

    def mousePressEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton:
            self._animation.stop();self._drag=event.globalPosition().toPoint()-self.pos();event.accept()

    def mouseMoveEvent(self,event):
        if self._drag is not None:
            target=QRect(event.globalPosition().toPoint()-self._drag,self.size())
            screen=QGuiApplication.screenAt(event.globalPosition().toPoint()) or self.screen()
            self.setGeometry(clamped_rect(target,screen.availableGeometry()));event.accept()

    def mouseReleaseEvent(self,event):
        self._drag=None;self.user_moved.emit();event.accept()

    def animate_rect(self,rect):
        self._animation.stop()
        if self.owner.hud.motion_reduced:self.setGeometry(rect);return
        self._animation.setStartValue(self.geometry());self._animation.setEndValue(rect);self._animation.start()

    def animate_opacity(self,value):
        self._opacity_animation.stop()
        if self.owner.hud.motion_reduced:self.setWindowOpacity(value);return
        self._opacity_animation.setStartValue(self.windowOpacity());self._opacity_animation.setEndValue(value);self._opacity_animation.start()

    def destination_rect(self):
        return QRect(self._animation.endValue()) if self._animation.state()==QPropertyAnimation.State.Running else self.geometry()

    def destination_opacity(self):
        return float(self._opacity_animation.endValue()) if self._opacity_animation.state()==QPropertyAnimation.State.Running else self.windowOpacity()

    def register_escape(self):
        if os.name!='nt' or os.environ.get('QT_QPA_PLATFORM')=='offscreen':return
        from ctypes import wintypes
        api=ctypes.WinDLL('user32',use_last_error=True)
        api.RegisterHotKey.argtypes=[wintypes.HWND,ctypes.c_int,wintypes.UINT,wintypes.UINT]
        api.RegisterHotKey.restype=wintypes.BOOL
        api.UnregisterHotKey.argtypes=[wintypes.HWND,ctypes.c_int]
        api.UnregisterHotKey.restype=wintypes.BOOL
        # Ctrl+Alt+Shift+F12, independent of microphone and application focus.
        if not api.RegisterHotKey(int(self.winId()),self.HOTKEY,0x4007,0x7B):
            raise RuntimeError('O atalho global Ctrl+Alt+Shift+F12 esta em uso. Libere-o antes de abrir o Espectro.')
        self._hotkey=api
        self._key_filter=EscapeFilter(self);QGuiApplication.instance().installNativeEventFilter(self._key_filter)
        from core.spectro_annotations import exclude_capture
        self.capture_excluded=exclude_capture(self)

    def closeEvent(self,event):
        if not self._closed:
            event.ignore();self.return_requested.emit();return
        self.dispose()
        super().closeEvent(event)

    def request_return(self):
        if not self._closed:self.return_requested.emit()

    def dispose(self):
        self._closed=True;self.timer.stop();self._animation.stop();self._opacity_animation.stop()
        if self._hotkey:
            QGuiApplication.instance().removeNativeEventFilter(self._key_filter)
            self._hotkey.UnregisterHotKey(int(self.winId()),self.HOTKEY);self._hotkey=None
        self.view.stop();self.view.close()


class SpectroController:
    def __init__(self,owner,window_factory=SpectroWindow):
        self.owner=owner;self.factory=window_factory;self.window=None;self.active=False;self.ready=False;self._closed=False
        self.timeout=QTimer(owner);self.timeout.setSingleShot(True);self.timeout.timeout.connect(self._failed)
        from core.spectro_store import SpectroStore
        self.store=SpectroStore();self.observer=None;self.annotations=None
        self._last_app='desktop';self._manual_position=False;self._target_at=0
        self._target_shape='outline';self._target_text=''
        self._target_color=None
        self._drawing_window=None
        self._presence_history=deque(maxlen=12)
        self.observation_timer=QTimer(owner);self.observation_timer.setInterval(500);self.observation_timer.timeout.connect(self._poll)
        self.save_timer=QTimer(owner);self.save_timer.setSingleShot(True);self.save_timer.setInterval(500);self.save_timer.timeout.connect(self._save_preference)

    def snapshot(self):
        window=self.window
        observer=self.observer
        destination=window.destination_rect() if window else None
        moving=bool(window and any(animation.state()==QPropertyAnimation.State.Running for animation in (window._animation,window._opacity_animation)))
        bounds=lambda rect:{'x':rect.x(),'y':rect.y(),'width':rect.width(),'height':rect.height()} if rect is not None else None
        annotations=self.annotations.snapshot() if self.annotations else {'count':0}
        marking='pending' if observer and observer.target else 'idle'
        if annotations.get('count',0):marking='visible'
        elif observer and (observer.target_lost or observer.target_error):marking='lost'
        return {'active':self.active,'ready':self.ready,'observing_screen':bool(observer and observer.enabled),
                'renderer':'webgl' if self.ready else 'loading' if self.active else 'inactive',
                'emergency_shortcut':'Ctrl+Alt+Shift+F12','capabilities':['presence','drag','position','size','opacity','return','authorized_uia','annotations','initiative','app_preferences'],
                'capture_excluded':bool(window and window.capture_excluded),
                'observation':{'enabled':bool(observer and observer.enabled),'allowed_apps':sorted(observer.allowed) if observer else [],'last_error':observer.last_error if observer else ''},
                'quiet':bool(observer and observer.initiative.quiet),
                'annotations':annotations,'marking':{'state':marking,'control_id':observer.target if observer else None,
                    'error':observer.target_error if observer else ''},
                'audit':observer.audit[-12:] if observer else [],
                'audit_available':observer.audit_available if observer else True,
                'opacity':window.windowOpacity() if window else None,
                'can_undo_presence':bool(self._presence_history),
                'bounds':bounds(window.geometry()) if window else None,
                'transition':{'active':moving,'bounds':bounds(destination),'opacity':window.destination_opacity() if window else None}}

    def _ready(self,source=None):
        if not self.active or self.ready or source is not None and source is not self.window:return
        self.timeout.stop();self.ready=True
        destination=self.window.geometry()
        if not self.owner.hud.motion_reduced:
            size=min(460,self.window.screen().availableGeometry().height())
            core=getattr(self.owner.hud,'_spatial_core',None)
            origin=core.mapToGlobal(core.rect().center()) if core is not None else self.owner.mapToGlobal(self.owner.rect().center())
            start=QRect(origin-QPoint(size//2,size//2),QSize(size,size))
            self.window.setGeometry(clamped_rect(start,self.window.screen().availableGeometry()))
            self.window.animate_rect(destination)
        self.owner.hide();self.window.timer.start();self.window.sync()
        self.window.animate_opacity(.68)
        from core.spectro_annotations import Annotations
        self.annotations=Annotations(self.window)
        try:self.start_observation()
        except (ValueError,OSError):
            self._failed(self.window);return
        self.observation_timer.start()
        self._restore_preference('desktop')

    def start_observation(self):
        if self._closed:return
        if self.observer is None:
            from core.spectro_observer import Observer
            self.observer=Observer(self.store,automatic=True)
        self.observation_timer.start()

    def _failed(self,source=None):
        if not self.active or source is not None and source is not self.window:return
        self.apply('exit',{})
        self.owner.hud.append_log('SYS: O Espectro nao conseguiu carregar. A base foi restaurada.')

    def apply(self,operation,settings):
        if self._closed:raise ValueError('O Jarvis esta encerrando; o Espectro nao sera reaberto.')
        if operation=='next_notice':
            notice=None
            if self.active and self.ready and self.observer and self.observer.enabled:
                current=self.observer.context()
                if current.get('ok'):
                    self.observer.initiative.pending=deque(
                        (item for item in self.observer.initiative.pending if item['source'].get('tool') or (
                            item['source'].get('handle')==current.get('handle') and item['source'].get('process_id')==current.get('process_id') and
                            any(control.get('name')==item['source'].get('observed_text') for control in current.get('controls',[])))),maxlen=6)
                    notice=self.observer.initiative.next()
            return {'ok':True,'notice':notice}
        if operation=='enter':
            if self.active:return {'ok':True,'completed':self.ready,'spectro':self.snapshot()}
            forge=getattr(self.owner,'_forge_controller',None)
            ultron=getattr(self.owner,'_ultron_payload',None) or {}
            if getattr(forge,'active',False) or ultron.get('state',{}).get('phase','idle')!='idle':
                raise ValueError('Volte a base e encerre o protocolo ativo antes de abrir o Espectro.')
            window=self.factory(self.owner);self.window=window
            try:
                area=self.owner.screen().availableGeometry();size=min(320,area.width(),area.height())
                window.setGeometry(QRect(area.right()-size-24,area.bottom()-size-24,size,size))
                window.ready.connect(lambda:self._ready(window));window.failed.connect(lambda:self._failed(window))
                window.return_requested.connect(lambda:self._emergency(window))
                window.user_moved.connect(self._user_moved)
                window.setWindowOpacity(0.)
                self.active=True;self.ready=False;window.show();window.register_escape();self.timeout.start(20000)
            except Exception:
                window.dispose();window.close();window.deleteLater();self.window=None;self.active=False;raise
            return {'ok':True,'completed':False,'spectro':self.snapshot()}
        if operation=='exit':
            self._presence_history.clear()
            if self.save_timer.isActive():self._save_preference()
            self.timeout.stop();self.active=False;self.ready=False
            self.save_timer.stop()
            if self.annotations:self.annotations.clear();self.annotations=None
            if self.observer:self.observer.clear_target()
            if self.window:self.window.dispose();self.window.close();self.window.deleteLater();self.window=None
            self.owner.show();self.owner.raise_();self.owner.activateWindow()
            return {'ok':True,'completed':True,'spectro':self.snapshot()}
        if operation in ('context','privacy','resume_observation'):
            self.start_observation()
            return self._perception_command(operation,settings)
        if not self.active or not self.ready:raise ValueError('O Espectro ainda nao esta ativo e pronto.')
        if operation in ('observe_current','resume_observation','privacy','context','highlight','note','draw','clear','quiet','forget_app'):
            return self._perception_command(operation,settings)
        window=self.window;rect=window.destination_rect()
        screen=QGuiApplication.screenAt(rect.center()) or window.screen();area=screen.availableGeometry()
        previous=(QRect(rect),window.destination_opacity())
        if operation=='undo_presence':
            if not self._presence_history:raise ValueError('Nao ha ajuste anterior do holograma para desfazer nesta sessao.')
            old_rect,opacity=self._presence_history.pop()
            old_screen=QGuiApplication.screenAt(old_rect.center()) or screen
            window.animate_rect(clamped_rect(old_rect,old_screen.availableGeometry()))
            window.animate_opacity(opacity)
            self._manual_position=True;self.save_timer.start()
            return {'ok':True,'completed':False,'spectro':self.snapshot()}
        if operation=='opacity':
            delta=float(settings.get('delta',0));value=float(settings.get('value',window.destination_opacity()+delta))
            if not math.isfinite(value):raise ValueError('Opacidade invalida.')
            window.animate_opacity(max(.18,min(1.,value)))
        elif operation in ('scale','reset','minimal'):
            factor=float(settings.get('factor',1.))
            if not math.isfinite(factor) or factor<=0:raise ValueError('Tamanho invalido.')
            size=320 if operation=='reset' else 160 if operation=='minimal' else int(settings['size']) if 'size' in settings else round(rect.width()*min(1000,factor))
            size=max(140,min(640,size));rect=QRect(rect.center()-QPoint(size//2,size//2),QSize(size,size))
            window.animate_rect(clamped_rect(rect,area))
            if operation=='minimal':window.animate_opacity(.25)
            if operation=='reset':window.animate_opacity(.68)
        elif operation=='position':
            anchor=settings.get('anchor')
            if anchor=='opposite':anchor='left' if rect.center().x()>area.center().x() else 'right'
            if 'dx' in settings or 'dy' in settings:
                dx=float(settings.get('dx',0));dy=float(settings.get('dy',0))
                if not math.isfinite(dx) or not math.isfinite(dy):raise ValueError('Deslocamento invalido.')
                rect.translate(round(max(-area.width(),min(area.width(),dx))),round(max(-area.height(),min(area.height(),dy))))
            elif anchor=='next_monitor':
                screens=QGuiApplication.screens();current=screen
                area=screens[(screens.index(current)+1)%len(screens)].availableGeometry();rect.moveCenter(area.center())
            elif anchor in ('top','bottom'):rect.moveTop(area.top()+20 if anchor=='top' else area.bottom()-rect.height()-20)
            elif anchor in ('left','right','center'):rect.moveLeft(area.left()+20 if anchor=='left' else area.right()-rect.width()-20 if anchor=='right' else area.center().x()-rect.width()//2)
            else:raise ValueError('Posicao invalida.')
            window.animate_rect(clamped_rect(rect,area))
        else:raise ValueError('Operacao do Espectro desconhecida.')
        self._presence_history.append(previous)
        self._manual_position=True;self.save_timer.start()
        moving=any(animation.state()==QPropertyAnimation.State.Running for animation in (window._animation,window._opacity_animation))
        return {'ok':True,'completed':not moving,'spectro':self.snapshot()}

    def close(self):
        if self.save_timer.isActive():self._save_preference()
        self._closed=True;self.timeout.stop();self.active=False;self.ready=False
        self._stop_observation()
        if self.window:self.window.dispose();self.window.close();self.window.deleteLater();self.window=None

    def _emergency(self,source=None):
        if self._closed or not self.active or source is not None and source is not self.window:return
        interrupt=getattr(self.owner,'_do_interrupt',None)
        if callable(interrupt):interrupt()
        self.apply('exit',{})

    def _user_moved(self):
        if self.active and self.ready:self._manual_position=True;self.save_timer.start()

    def _save_preference(self):
        if not self.active or not self.ready or self.window is None:return
        window=self.window;rect=window.destination_rect()
        screen=QGuiApplication.screenAt(rect.center()) or window.screen();area=screen.availableGeometry()
        value={'screen':screen.name(),'x':(rect.x()-area.x())/max(1,area.width()),
               'y':(rect.y()-area.y())/max(1,area.height()),'size':rect.width(),'opacity':window.destination_opacity()}
        try:self.store.save(self._last_app,value)
        except (OSError,ValueError):self.owner.hud.append_log('SYS: Nao consegui salvar a preferencia do Espectro.')

    def _restore_preference(self,app):
        try:value=self.store.read()['preferences'].get(app)
        except (OSError,ValueError):return
        if not isinstance(value,dict):return
        try:
            numbers=[float(value[key]) for key in ('x','y','size','opacity')]
            if not all(math.isfinite(number) for number in numbers):return
            x,y,size,opacity=numbers;size=max(140,min(640,int(size)))
            screen=next((screen for screen in QGuiApplication.screens() if screen.name()==value.get('screen')),self.window.screen())
            area=screen.availableGeometry();rect=QRect(area.x()+round(x*area.width()),area.y()+round(y*area.height()),size,size)
            self.window.animate_rect(clamped_rect(rect,area));self.window.animate_opacity(max(.18,min(1.,opacity)))
        except (KeyError,TypeError,ValueError):return

    def _stop_observation(self):
        self.observation_timer.stop();self.save_timer.stop()
        if self.observer:self.observer.close();self.observer=None
        if self.annotations:self.annotations.clear();self.annotations=None
        self._manual_position=False;self._last_app='desktop'

    def _poll(self):
        if self.observer is None:return
        try:
            self.observer.poll()
            if not self.active or not self.ready or self.annotations is None:return
            if not self.observer.enabled:return
            current=self.observer.context()
            if not current.get('ok'):
                self.annotations.clear();return
            app=current.get('app')
            if self._drawing_window and self._drawing_window!=(current.get('handle'),current.get('process_id')):
                self.annotations.clear();self._drawing_window=None
            if app and app!=self._last_app:
                if self.save_timer.isActive():self._save_preference();self.save_timer.stop()
                self._last_app=app
                if not self._manual_position:self._restore_preference(app)
            target=self.observer.target_result
            if target and self.observer.target and time.monotonic()-self._target_at<25:
                self.annotations.update_target(target['rect'],self._target_text,self._target_shape,self._target_color)
            elif self.observer.target_lost:
                self.annotations.clear();self.observer.target_lost=False
            elif self.observer.target and time.monotonic()-self._target_at>=25:
                self.annotations.clear();self.observer.clear_target()
        except Exception as error:
            if self.annotations:self.annotations.clear()
            self.observer.last_error=type(error).__name__
            diagnostic=getattr(self.owner,'_spectro_error',None)
            if callable(diagnostic):
                import traceback
                diagnostic(traceback.format_exc())

    def _perception_command(self,operation,settings):
        observer=self.observer
        if operation not in ('context',):observer.record(operation)
        if operation=='observe_current':
            app=observer.allow_current(settings.get('expected_target'));self.annotations.clear()
            return {'ok':True,'app':app,'completed':False,'speech':'Vou acompanhar os elementos acessiveis deste aplicativo. Pode pedir para parar a qualquer momento.'}
        if operation=='resume_observation':observer.resume()
        elif operation=='privacy':
            observer.privacy()
            if self.annotations:self.annotations.clear()
        elif operation=='context':return observer.context()
        elif operation=='highlight':
            shape=settings.get('shape','outline')
            if shape not in ('outline','circle','arrow','marker','underline','cross'):raise ValueError('Forma do destaque invalida.')
            from core.spectro_annotations import annotation_color
            color=annotation_color(settings.get('color'))
            if settings.get('query') and not settings.get('control_id'):
                observer.highlight(query=settings['query'])
            else:observer.highlight(settings.get('control_id'))
            self._drawing_window=None
            self._target_color=color;self._target_at=time.monotonic()
            self.annotations.clear()
            self._target_shape=shape;self._target_text=str(settings.get('text',''))[:220]
            return {'ok':True,'completed':False,'speech':'Consultando a posicao atual desse elemento.'}
        elif operation=='note':
            text=str(settings.get('text','')).strip()
            if not text:raise ValueError('Informe o texto da anotacao.')
            observer.clear_target()
            self._drawing_window=None
            self.annotations.note(text)
        elif operation=='draw':
            current=observer.context()
            if not current.get('ok'):raise ValueError(current.get('error','Consulte a janela antes de desenhar.'))
            self.annotations.draw(settings.get('points'),settings.get('color'),str(settings.get('text',''))[:220],settings.get('screen'))
            observer.clear_target();self._drawing_window=(current['handle'],current['process_id'])
        elif operation=='clear':self.annotations.clear();observer.clear_target()
        elif operation=='quiet':observer.initiative.quiet=bool(settings.get('enabled',True));observer.initiative.clear()
        elif operation=='forget_app':observer.forget(settings.get('app',''));self.annotations.clear()
        return {'ok':True,'completed':True,'spectro':self.snapshot()}

    def record_event(self,name,state):
        if not isinstance(name,str) or not self.active or not self.observer or not self.observer.enabled:return
        base=name.split(':',1)[0]
        labels={'powershell_control':'comando do Windows','forge_protocol':'trabalho na Forja','file_processor':'processamento do arquivo','resource_backups':'backup'}
        if base not in labels or state not in ('failed','uncertain','finished','completed'):return
        text=('A etapa do '+labels[base]+' teve uma falha ou resultado incerto. Posso conferir o retorno antes de tentar novamente.'
              if state in ('failed','uncertain') else 'A etapa do '+labels[base]+' terminou. O retorno esta disponivel para conferir o resultado.')
        self.observer.initiative.offer(base+':'+state,text,{'tool':base,'state':state})
