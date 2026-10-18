"""Read-only pinned queries; timers never call providers on the GUI thread."""
import copy
import importlib
import json
import threading
import time
from datetime import datetime, timezone

INTERVALS = {'system':1, 'organizer':1, 'weather':120, 'news':300, 'search':300,
             'gmail':60, 'whatsapp':30, 'google_calendar':60}
MODULES = {'organizer':('actions.organizer','organizer_action'),
           'weather':('actions.weather_report','weather_action'),
           'gmail':('plugins.gmail_control','run'),
           'whatsapp':('plugins.whatsapp_web','run'),
           'google_calendar':('plugins.google_calendar','run'),
           'search':('actions.web_search','web_search')}
KINDS = {'system':('system',),'organizer':('tasks','calendar'),'weather':('weather',),'news':('news',),
         'gmail':('gmail',),'whatsapp':('whatsapp',),'google_calendar':('calendar',),'search':('search','data')}
FIELDS = {'organizer':{'domain','action','id','query','date_from','date_to','offset','limit'},
          'weather':{'city','time'}, 'gmail':{'action','query','scope','page_token','limit','include_spam_trash'},
          'whatsapp':{'action','limit'},'search':{'query','mode','items','aspect'},
          'google_calendar':{'action','calendar_id','query','date_from','date_to','page_token','limit','include_birthdays'}}


def enabled(spec):
    plugin={'gmail':'gmail_control','whatsapp':'whatsapp_web','google_calendar':'google_calendar'}.get(spec['provider'])
    if plugin:
        from memory.config_manager import get_plugin_enabled
        return get_plugin_enabled(plugin)
    return True


def specification(model):
    kind=model.get('kind')
    if kind=='system':return {'provider':'system','parameters':{}}
    value=model.get('refresh')
    if not isinstance(value,dict):
        if kind=='weather' and model.get('city'):
            value={'provider':'weather','parameters':{'city':model['city'],'time':model.get('period','today')}}
        else:return None
    provider=value.get('provider');params=value.get('parameters',{})
    if not isinstance(provider,str):return None
    if kind not in KINDS.get(provider,()) or not isinstance(params,dict):return None
    if provider=='news':return {'provider':provider,'parameters':{'query':str(params.get('query',''))[:1000]}}
    params={key:copy.deepcopy(value) for key,value in params.items() if key in FIELDS[provider]}
    action=params.get('action','list')
    if provider=='organizer' and (action not in ('list','read') or params.get('domain')!=kind):return None
    if provider in ('gmail','google_calendar') and action!='list':return None
    # Opening a chat can mark messages read; never do that on a background timer.
    if provider=='whatsapp' and action!='unread':return None
    if provider=='search' and params.get('mode','search') not in ('search','research','price','compare'):return None
    return {'provider':provider,'parameters':params}


class Capture:
    def __init__(self):self.model=None
    def show_manifestation(self,model):self.model=copy.deepcopy(model)
    def write_log(self,text):pass


def fetch(spec):
    provider=spec['provider'];params=spec['parameters']
    if not enabled(spec):raise ValueError('Conexao desativada')
    if provider=='system':
        from actions.system_monitor import get_system_status
        return {'kind':'system','title':'SISTEMA',**get_system_status()}
    if provider=='news':
        from actions.web_search import fetch_news_package
        model=fetch_news_package(params['query'])['model']
        if not model.get('items'):raise ValueError('Noticias indisponiveis')
        return model
    if provider in ('gmail','whatsapp','google_calendar'):
        from memory.config_manager import get_plugin_enabled
        plugin={'gmail':'gmail_control','whatsapp':'whatsapp_web','google_calendar':'google_calendar'}[provider]
        if not get_plugin_enabled(plugin):raise ValueError('Conexao desativada')
    module,name=MODULES[provider]
    capture=Capture()
    result=getattr(importlib.import_module(module),name)(copy.deepcopy(params),player=capture)
    if not enabled(spec):raise ValueError('Conexao desativada')
    if provider=='search':
        if capture.model is None:raise ValueError('Pesquisa indisponivel')
        return capture.model
    result=json.loads(result) if isinstance(result,str) else result
    if not isinstance(result,dict) or result.get('ok') is False or result.get('error') or capture.model is None:
        raise ValueError('Fonte indisponivel')
    return capture.model


class LivePins:
    """All scheduling state is owned by Qt; worker threads only emit results."""
    def __init__(self, emit, loader=fetch, clock=time.monotonic):
        self.emit=emit;self.loader=loader;self.clock=clock
        self.pending={};self.due={};self.closed=False;self.workers={};self.timed_out=set()

    def tick(self, previews):
        if self.closed:return
        now=self.clock()
        self.due={key:value for key,value in self.due.items() if key in previews}
        for key,job in list(self.pending.items()):
            preview=previews.get(key)
            if not preview or preview.get('live_token')!=job[0][0] or specification(preview['data'])!=job[1]:
                self.pending.pop(key,None)
            elif now-job[2]>=30 and job[0] not in self.timed_out:
                self.timed_out.add(job[0])
                self.emit({'key':key,'identity':job[0],'model':None,'error':'Consulta demorando; exibindo a ultima consulta.','timeout':True})
        ordered=sorted(previews.items(),key=lambda item:(item[0]!='system',self.due.get(item[0],(None,0))[1]))
        for key,preview in ordered:
            spec=specification(preview['data'])
            token=preview.get('live_token')
            if not spec or not enabled(spec) or token is None or key in self.pending:continue
            identity=(token,json.dumps(spec,sort_keys=True,ensure_ascii=False))
            previous=self.due.get(key)
            if previous and previous[0]==identity and now<previous[1]:continue
            # Reserve a slot for local telemetry even when external providers stall.
            external=sum(job['provider']!='system' for job in self.workers.values())
            if len(self.workers)>=4 or (spec['provider']!='system' and external>=3):continue
            self.pending[key]=(identity,spec,now)
            self.workers[identity]=spec
            threading.Thread(target=self._work,args=(key,identity,spec),daemon=True,name='JarvisPinnedQuery').start()

    def _work(self,key,identity,spec):
        try:
            model=self.loader(spec)
            if not isinstance(model,dict) or model.get('error') or model.get('kind') not in KINDS[spec['provider']]:
                raise ValueError('Dados invalidos')
            if spec['provider']=='organizer' and model.get('kind')!=spec['parameters']['domain']:
                raise ValueError('Dominio da consulta alterado')
            result={'key':key,'identity':identity,'model':model,'error':None,
                    'updated_at':datetime.now(timezone.utc).isoformat()}
        except Exception:
            result={'key':key,'identity':identity,'model':None,'error':'Fonte indisponivel; exibindo a ultima consulta.'}
        if not self.closed:
            try:self.emit(result)
            except RuntimeError:pass  # Window may have closed while a query finished.

    def accept(self,result,previews):
        key=result['key'];job=self.pending.get(key)
        if not result.get('timeout'):
            self.workers.pop(result['identity'],None)
            self.timed_out.discard(result['identity'])
        if not job or job[0]!=result['identity']:return False
        interval=INTERVALS[job[1]['provider']]
        if not result.get('timeout'):
            self.pending.pop(key,None)
            if not enabled(job[1]):
                self.due.pop(key,None)
                return False
            self.due[key]=(job[0],self.clock()+max(30,interval) if result['error'] else job[2]+interval)
        preview=previews.get(key)
        return bool(not self.closed and preview and preview.get('live_token')==job[0][0]
                    and enabled(job[1])
                    and specification(preview['data'])==job[1]
                    and (result['error'] or result['model'].get('kind')==preview['data'].get('kind')))

    def close(self):self.closed=True
