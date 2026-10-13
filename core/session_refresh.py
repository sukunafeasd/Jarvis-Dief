"""Bounded real source collection; completion is not inferred from animation."""
import asyncio
import json
from datetime import datetime


def default_sources(news_fetch):
    from actions.organizer import organizer_action
    from actions.weather_report import weather_action
    from actions.system_monitor import get_system_status
    from core import gmail_connection as gmail
    def organizer(domain):
        parameters = {'domain':domain,'action':'list'}
        if domain == 'calendar':
            parameters.update(date_from=datetime.now().date().isoformat(), date_to=datetime.now().date().isoformat())
        value = json.loads(organizer_action(parameters))['data']
        value['items'] = value['items'][:10]
        value['summary_limit'] = 10
        return value
    def weather():
        value = json.loads(weather_action({}))
        if not value.get('ok'):
            raise RuntimeError('Clima indisponivel')
        return value['weather']
    sources = {'news':('Notícias',news_fetch), 'calendar':('Agenda local',lambda:organizer('calendar')),
               'tasks':('Tarefas locais',lambda:organizer('tasks')),
               'weather':('Clima',weather), 'system':('Sistema',get_system_status)}
    if gmail.status()['connected']:
        def messages():
            counts=gmail.inbox_summary()
            listing=gmail.list_messages('is:unread is:important',limit=5)
            if not listing.get('ok'):raise RuntimeError('Gmail indisponivel')
            return {**counts,'kind':'gmail','source':'Gmail · importantes não lidos',
                    'items':[{'title':item.get('subject','Sem assunto'),'detail':item.get('from',''),
                              'id':item.get('id'),'date':item.get('date','')} for item in listing['messages']],
                    'note':'Cabeçalhos consultados. Corpos dos e-mails não foram lidos.'}
        sources['gmail'] = ('Gmail · importantes não lidos',messages)
    from core import google_services as google
    from memory.config_manager import get_plugin_enabled
    if get_plugin_enabled('google_calendar') and google.status('google_calendar').get('connected'):
        def calendar():
            result=google.calendar({'action':'list','limit':10})
            return {'kind':'calendar','source':'Google Agenda','items':[
                {**item,'title':item.get('summary','Sem título'),'due':item.get('start',{}).get('dateTime',item.get('start',{}).get('date',''))}
                for item in result['items']],'complete':result['complete'],'next_page_token':result['next_page_token']}
        sources['calendar']=('Google Agenda',calendar)
    return sources


async def collect_updates(news_fetch, progress, sources=None, timeout=30):
    sources = default_sources(news_fetch) if sources is None else sources
    states = {key:{'id':key,'title':title,'status':'working','detail':'Consultando fonte'} for key,(title,_) in sources.items()}
    data = {}; failures = {}
    def publish():
        progress({'kind':'status','id':'daily-refresh','title':'ATUALIZANDO MEU CONTEXTO',
                  'items':[dict(item) for item in states.values()], 'narrationDriven':False,
                  'source':'Consultas reais · ' + datetime.now().strftime('%H:%M'),
                  'completed':sum(item['status']!='working' for item in states.values()),'total':len(states)})
    async def fetch(key, callback):
        try:
            value = await asyncio.wait_for(asyncio.to_thread(callback),timeout=timeout)
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
