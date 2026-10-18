"""Bounded real source collection; completion is not inferred from animation."""
import asyncio
import json
from datetime import datetime, timedelta
from core.bounded_work import BoundedWork

_SOURCE_WORK=BoundedWork(workers=8,capacity=16,name='DailySource')


def enabled_context(package):
    """Recheck opt-outs when a previously collected package is consumed."""
    from memory.config_manager import get_plugin_enabled
    data=dict(package.get('data',{}))
    disabled=[]
    if 'gmail' in data and not get_plugin_enabled('gmail_control'):disabled.append('gmail')
    calendar=data.get('calendar') or {}
    if not isinstance(calendar,dict):calendar={}
    if calendar.get('refresh',{}).get('provider')=='google_calendar' and not get_plugin_enabled('google_calendar'):
        disabled.append('calendar')
    for key in disabled:data.pop(key,None)
    return {**package,'data':data,'unavailable':[key for key in package.get('unavailable',[]) if key not in disabled]}


async def _collect_source(callback,timeout):
    # Timed-out synchronous providers cannot be killed, but remain bounded daemon
    # workers rather than keeping asyncio's default executor alive at shutdown.
    future=_SOURCE_WORK.submit(callback)
    return await asyncio.wait_for(asyncio.wrap_future(future),timeout=timeout)


def default_sources(news_fetch):
    from actions.organizer import organizer_action
    from actions.weather_report import weather_action
    from actions.system_monitor import get_system_status
    from core import gmail_connection as gmail
    from memory.config_manager import get_plugin_enabled
    def organizer(domain):
        parameters = {'domain':domain,'action':'list'}
        if domain == 'calendar':
            parameters.update(date_from=datetime.now().date().isoformat(), date_to=datetime.now().date().isoformat())
        value = json.loads(organizer_action(parameters))['data']
        value['items'] = value['items'][:10]
        value['summary_limit'] = 10
        if domain == 'calendar':
            value['emptyText'] = 'Nenhum compromisso na agenda local para hoje.'
        return value
    def weather():
        value = json.loads(weather_action({}))
        if not value.get('ok'):
            raise RuntimeError('Clima indisponivel')
        return value['weather']
    sources = {'news':('Notícias',news_fetch), 'calendar':('Agenda local',lambda:organizer('calendar')),
               'tasks':('Tarefas locais',lambda:organizer('tasks')),
               'weather':('Clima',weather), 'system':('Sistema',get_system_status)}
    if get_plugin_enabled('gmail_control') and gmail.status()['connected']:
        def messages():
            if not get_plugin_enabled('gmail_control'):raise RuntimeError('Gmail desativado')
            listing=gmail.list_messages('is:unread is:important',limit=5)
            if not listing.get('ok'):raise RuntimeError('Gmail indisponivel')
            if not get_plugin_enabled('gmail_control'):raise RuntimeError('Gmail desativado')
            try:
                counts=gmail.inbox_summary()
                if not isinstance(counts,dict) or counts.get('ok') is False or counts.get('error'):
                    counts={'counts_unavailable':True}
            except Exception:
                counts={'counts_unavailable':True}
            if not get_plugin_enabled('gmail_control'):raise RuntimeError('Gmail desativado')
            return {**counts,'kind':'gmail','source':'Gmail · importantes não lidos',
                    'items':[{'title':item.get('subject','Sem assunto'),'detail':item.get('from',''),
                              'id':item.get('id'),'date':item.get('date','')} for item in listing['messages']],
                    'note':'Cabeçalhos consultados. Corpos dos e-mails não foram lidos.',
                    'refresh':{'provider':'gmail','parameters':{'action':'list','query':'is:unread is:important','limit':5}}}
        sources['gmail'] = ('Gmail · importantes não lidos',messages)
    from core import google_services as google
    if get_plugin_enabled('google_calendar') and google.status('google_calendar').get('connected'):
        def calendar():
            if not get_plugin_enabled('google_calendar'):raise RuntimeError('Google Agenda desativada')
            midnight = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
            parameters = {'action':'list','limit':10,
                          'date_from':midnight.astimezone().isoformat(),
                          'date_to':(midnight + timedelta(days=1)).astimezone().isoformat()}
            result=google.calendar(parameters)
            if not get_plugin_enabled('google_calendar'):raise RuntimeError('Google Agenda desativada')
            return {'kind':'calendar','source':'Google Agenda',
                'emptyText':'Nenhum compromisso no Google Agenda para hoje.','items':[
                {**item,'title':item.get('summary','Sem título'),'due':item.get('start',{}).get('dateTime',item.get('start',{}).get('date',''))}
                for item in result['items']],'complete':result['complete'],'next_page_token':result['next_page_token'],
                'refresh':{'provider':'google_calendar','parameters':parameters}}
        sources['calendar']=('Google Agenda',calendar)
    return sources


async def collect_updates(news_fetch, progress, sources=None, timeout=30):
    sources = await _collect_source(lambda:default_sources(news_fetch),timeout) if sources is None else sources
    states = {key:{'id':key,'title':title,'status':'working','detail':'Consultando fonte'} for key,(title,_) in sources.items()}
    data = {}; failures = {}
    def publish():
        progress({'kind':'status','id':'daily-refresh','title':'ATUALIZANDO MEU CONTEXTO',
                  'items':[dict(item) for item in states.values()], 'narrationDriven':False,
                  'source':'Consultas reais · ' + datetime.now().strftime('%H:%M'),
                  'completed':sum(item['status']!='working' for item in states.values()),'total':len(states)})
    async def fetch(key, callback):
        try:
            value = await _collect_source(callback,timeout)
            if not value or (isinstance(value,dict) and (value.get('ok') is False or value.get('error'))):
                raise RuntimeError('Fonte indisponivel')
            if key == 'news' and (not value.get('model',{}).get('items') or not value.get('text')):
                raise RuntimeError('Noticias indisponiveis')
            data[key] = value
            states[key].update(status='ok',detail='Consulta concluída')
        except Exception as error:
            failures[key] = type(error).__name__
            states[key].update(status='warning',detail='Indisponível nesta atualização')
        publish()
    publish()
    await asyncio.gather(*(fetch(key,callback) for key,(_,callback) in sources.items()))
    return {'data':data,'unavailable':list(failures),'updated_at':datetime.now().isoformat()}
