"""Compositor da cena: posicoes seguras, texto nativo e simbolos WebGL locais."""
import copy
import math
import time
from PyQt6.QtCore import QObject,QTimer,Qt,QRectF,QPointF
from PyQt6.QtGui import QColor,QFont,QFontMetrics,QPainter,QPen
from PyQt6.QtWidgets import QWidget,QLabel
from core import visual_library as library
from core.presentation_clock import PresentationClock


class SymbolFallback(QWidget):
    def __init__(self,parent):
        super().__init__(parent);self.item={}
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def paintEvent(self,event):
        item=self.item
        if not item:return
        painter=QPainter(self);painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor(item['colors'][0]),1.5));painter.setBrush(Qt.BrushStyle.NoBrush)
        center=QPointF(self.width()/2,self.height()/2)
        family=item.get('recipe',{}).get('family','ring')
        if family in ('slabs','message','circuit','grid','columns'):
            for index in range(3):
                painter.drawRoundedRect(QRectF(center.x()-22+index*8,center.y()-19-index*4,36,28),2,2)
        else:
            painter.drawEllipse(center,28,28);painter.drawEllipse(center,32,12)
            for index in range(3):
                angle=index*math.tau/3
                painter.drawEllipse(QPointF(center.x()+math.cos(angle)*28,center.y()+math.sin(angle)*28),3,3)


class VisualSceneController(QObject):
    def __init__(self,window):
        super().__init__(window)
        self.window=window;self.items={};self.layout='livre';self.labels={};self.symbols={};self.view=None
        import ui
        self._motion_reduced=bool(ui._read_full_config().get('reduce_motion',False))
        self.cancelled=False;self.clock=PresentationClock();self._placements=[];self._last_payload=None
        self.pending_cues=[];self.speech_end=0
        self.layer=QWidget(window._scene_stage);self.layer.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.layer.setStyleSheet('background: transparent;');self.layer.hide()
        self.timer=QTimer(self);self.timer.timeout.connect(self.tick)
        self.expiry=QTimer(self);self.expiry.setSingleShot(True);self.expiry.timeout.connect(self.expire)
        window.destroyed.connect(self.timer.stop)
        window.destroyed.connect(self.expiry.stop)

    def reduced(self):
        return self._motion_reduced

    def font(self,item):
        font=QFont('Segoe UI',16 if item['role'] in ('titulo','valor') else 11)
        font.setBold(item['role'] in ('titulo','valor','pergunta'))
        return font

    def wrap(self,text,metrics,width):
        lines=[];line=''
        for character in text:
            if character=='\n':lines.append(line);line='';continue
            if line and metrics.horizontalAdvance(line+character)>width-2:lines.append(line.rstrip());line=''
            line+=character
        lines.append(line)
        return '\n'.join(lines)

    def measure(self,item,width):
        metrics=QFontMetrics(self.font(item))
        return max(26,len(self.wrap(item['text'],metrics,width).split('\n'))*metrics.lineSpacing()+6)

    def blocked(self):
        window=self.window;rect=window._center_split.geometry()
        obstacles=[{'x':rect.x()+int(rect.width()*.34),'y':rect.y()+int(rect.height()*.25),
                    'width':int(rect.width()*.32),'height':int(rect.height()*.5)}]
        for widget in (window._content_panel,window._terminal,window._execution,window._command_bar):
            if widget.isVisible():
                rect=widget.geometry();obstacles.append({'x':rect.x(),'y':rect.y(),'width':rect.width(),'height':rect.height()})
        for preview in window._pin_previews.values():
            rect=preview['widget'].geometry();obstacles.append({'x':rect.x(),'y':rect.y(),'width':rect.width(),'height':rect.height()})
        return obstacles

    def ensure_view(self):
        import os
        if self.view is not None or os.environ.get('QT_QPA_PLATFORM')=='offscreen':return
        try:
            from core.spatial_view import SpatialCoreView
            self.view=SpatialCoreView(self.layer,'visual_library.html')
            self.view.page().setBackgroundColor(QColor(Qt.GlobalColor.transparent))
            self.view.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            self.view.unavailable.connect(lambda:self.reflow(force=True));self.view.show();self.view.lower()
        except ImportError:pass

    def apply(self,request):
        command=library.validate_request(request);action=command['action'];now=time.monotonic()
        if action=='compose':
            incoming=command['elements'];preserved={key:item for key,item in self.items.items() if item['pinned']}
            if len(set(preserved)|{item['id'] for item in incoming})>12:raise ValueError('A cena já tem prévias fixadas. Remova uma antes de adicionar mais de 12 elementos.')
            for item in incoming:
                if item['id'] in preserved:item['pinned']=True
                preserved[item['id']]={**item,'created':now,'expires':now+command['duration'],
                    'revealed':not bool(item['cue']),'chars':0,'focused':False,'timing':'aguardando-fala' if item['cue'] else 'visual'}
            self.items=preserved;self.layout=command['layout'];self.cancelled=False;self.clock.reset();self.pending_cues=[];self.speech_end=0
        elif action=='clear':self.items={key:item for key,item in self.items.items() if item['pinned']}
        elif action!='inspect':
            identifier=command['id']
            if identifier not in self.items:raise ValueError('Elemento inexistente. Consulte inspect antes de agir.')
            item=self.items[identifier]
            if action=='remove':del self.items[identifier]
            elif action=='pin':item['pinned']=True
            elif action=='unpin':item['pinned']=False;item['expires']=now+command['duration']
            elif action=='focus':
                for entry in self.items.values():entry['focused']=False
                item['focused']=True;item['revealed']=True;item['focused_until']=now+3
            elif action=='update':
                original={key:value for key,value in item.items() if key in {'id','icon','text','anchor','x','y','role','palette','animation','cue','scale','parts','pinned'}}
                patch=command['patch']
                if 'anchor' in patch and 'x' not in patch:original.pop('x',None);original.pop('y',None)
                candidate=library.validate_element({**original,**patch})
                if sum(len(entry['text']) for key,entry in self.items.items() if key!=identifier)+len(candidate['text'])>1800:raise ValueError('Texto demais na cena.')
                self.items[identifier]={**candidate,'created':now,'expires':now+command['duration'],
                    'revealed':not bool(candidate['cue']),'chars':0,'focused':item['focused'],'timing':'visual'}
                self.cancelled=False;self.clock.reset();self.pending_cues=[];self.speech_end=0
        self.ensure_view() if self.items else None
        self.reflow(force=True);self.tick()
        self.schedule_expiry()
        if action in ('compose', 'update'):
            self.clock.elapsed = self.window._presentation_clock.elapsed
        return {'ok':True,'scene':self.snapshot(),'note':'Posições resolvidas para preservar o holograma, as informações reais e os controles. Símbolos são ilustrativos.'}

    def reflow(self,force=False):
        import ui
        self._motion_reduced=bool(ui._read_full_config().get('reduce_motion',False))
        stage=self.window._scene_stage;self.layer.setGeometry(stage.rect())
        self._placements=library.resolve_layout(list(self.items.values()),stage.width(),stage.height(),self.blocked(),self.layout,self.measure)
        visible=bool(self.items) and not self.window._resting and not self.window.isMinimized() and self.window.isVisible()
        self.layer.setVisible(visible)
        if visible:self.layer.raise_()
        if self.view:self.view.setGeometry(self.layer.rect())
        for identifier in list(self.labels):
            if identifier not in self.items:
                self.labels.pop(identifier).deleteLater();self.symbols.pop(identifier).deleteLater()
        for item in self._placements:
            identifier=item['id']
            if identifier not in self.labels:
                label=QLabel(self.layer);label.setTextFormat(Qt.TextFormat.PlainText);label.setWordWrap(True)
                label.setAlignment(Qt.AlignmentFlag.AlignTop|Qt.AlignmentFlag.AlignHCenter);label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
                self.labels[identifier]=label;self.symbols[identifier]=SymbolFallback(self.layer)
            label=self.labels[identifier];symbol=self.symbols[identifier];symbol.item=item
            shown=visible and item['visible'] and item['revealed']
            label.setVisible(shown);symbol.setVisible(shown and bool(item.get('recipe') or item['parts']) and (not self.view or self.view.failed))
            if not item['bounds']:continue
            box=item['bounds'];symbol.setGeometry(box['x'],box['y'],box['width'],84);symbol.update()
            symbol_height=88 if item.get('recipe') or item['parts'] else 0
            label.setGeometry(box['x'],box['y']+symbol_height,box['width'],box['height']-symbol_height)
            label.setFont(self.font(item))
            label.setStyleSheet('background:transparent;color:'+item['colors'][0]+';')
            label.setAccessibleName(item['text'] or item.get('recipe',{}).get('label','Símbolo composto'))
            label.setToolTip(item['text']);label.raise_()
            self.render_text(item)
        payload={'visible':visible,'reduced':self.reduced() or self.cancelled,'elements':self._placements}
        # O WebGL recebe apenas alteracoes semanticas, nao o contador de letras a 25 Hz.
        compact={**payload,'elements':[{key:value for key,value in item.items() if key not in ('chars','created','expires','text','timing')} for item in self._placements]}
        if self.view and (force or compact!=self._last_payload):self.view.sync(compact)
        self._last_payload=compact

    def render_text(self,item):
        label=self.labels[item['id']]
        text=item['text'] if self.reduced() else item['text'][:item['chars']]
        # Quebra inclusive uma palavra longa para manter o texto dentro da sua area.
        value=self.wrap(text,label.fontMetrics(),label.width())
        if label.text()!=value:label.setText(value)

    def tick(self):
        now=time.monotonic();changed=False;writing=False
        visible=not self.window._resting and self.window.isVisible() and not self.window.isMinimized()
        for identifier,item in list(self.items.items()):
            if not item['pinned'] and now>=item['expires']:del self.items[identifier];changed=True;continue
            if item.get('focused_until',math.inf)<=now:item['focused']=False;item.pop('focused_until',None);changed=True
            if not visible or self.cancelled:continue
            if not item['revealed'] and not self.clock.active and now-item['created']>=6:
                item['revealed']=True;item['timing']='fallback-visual';changed=True
            if item['revealed'] and item['chars']<len(item['text']):
                item['chars']=len(item['text']) if self.reduced() else min(len(item['text']),item['chars']+3)
                self.render_text(item);writing=item['chars']<len(item['text']) or writing
        if changed:self.reflow(force=True)
        if self.items and (not self.cancelled) and (writing or any(not item['revealed'] or item.get('focused_until') for item in self.items.values())):
            self.timer.start(40 if writing else 500)
        else:self.timer.stop()

    def schedule_expiry(self):
        deadlines=[item['expires'] for item in self.items.values() if not item['pinned']]
        if deadlines:self.expiry.start(max(1,int((min(deadlines)-time.monotonic())*1000)))
        else:self.expiry.stop()

    def expire(self):
        now=time.monotonic()
        self.items={identifier:item for identifier,item in self.items.items() if item['pinned'] or item['expires']>now}
        self.reflow(force=True);self.schedule_expiry()

    def enqueue(self,packet):
        if self.cancelled:return
        text=packet.get('text','') if isinstance(packet,dict) else packet
        at=packet.get('at') if isinstance(packet,dict) else None
        duration=packet.get('duration') if isinstance(packet,dict) else None
        words=library.key(text).split('-')
        if not text.strip():return
        base=at if isinstance(at,(int,float)) and not isinstance(at,bool) and math.isfinite(at) else max(self.clock.elapsed,self.speech_end)
        already={event['id'] for event in self.pending_cues}
        word_duration=duration/max(1,len(words)) if isinstance(duration,(int,float)) and duration>0 else .35
        for item in self.items.values():
            if not item['cue'] or item['revealed'] or item['id'] in already:continue
            cue=library.key(item['cue']).split('-')
            for index in range(len(words)-len(cue)+1):
                if words[index:index+len(cue)]==cue:
                    self.pending_cues.append({'id':item['id'],'at':base+index*word_duration,'created':item['created']});break
        self.pending_cues.sort(key=lambda event:event['at'])
        self.speech_end=max(self.speech_end,base+len(words)*word_duration)

    def advance(self,seconds):
        self.clock.advance(seconds);changed=False
        if self.cancelled:return
        while self.pending_cues and self.pending_cues[0]['at']<=self.clock.elapsed:
            event=self.pending_cues.pop(0);item=self.items.get(event['id'])
            if item and item['created']==event['created']:
                item['revealed']=True;item['timing']='audio-estimado';changed=True
        if changed:self.reflow(force=True);self.tick()

    def cancel(self):
        self.cancelled=True;self.clock.cancel();self.pending_cues=[];self.timer.stop();self.reflow(force=True)

    def finish(self):
        if self.cancelled or not self.clock.active:return
        for item in self.items.values():
            if not item['revealed']:item['revealed']=True;item['timing']='fim-da-fala'
        self.pending_cues=[];self.reflow(force=True);self.tick()

    def clear_all(self,preserve_pinned=False):
        self.items={key:item for key,item in self.items.items() if preserve_pinned and item['pinned']}
        self.clock.cancel();self.pending_cues=[];self.timer.stop();self.expiry.stop();self.reflow(force=True)

    def snapshot(self):
        return {'layout':self.layout,'count':len(self.items),'cancelled':self.cancelled,
            'renderer':'WebGL' if self.view and not self.view.failed else 'alternativa-2D',
            'elements':[{**{key:copy.deepcopy(item.get(key)) for key in ('id','icon','text','anchor','bounds','revealed','pinned','timing','focused','placement_note')},
                'visible':bool(item['visible'] and item['revealed'] and self.layer.isVisible()),
                'displayed_text':self.labels[item['id']].text() if item['id'] in self.labels and item['revealed'] else ''} for item in self._placements]}
