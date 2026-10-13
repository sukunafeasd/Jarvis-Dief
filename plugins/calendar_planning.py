"""Disponibilidade derivada dos eventos consultados, nao uma promessa de agenda completa."""
from datetime import datetime,timedelta
from core.essential_plugins import respond
PLUGIN={'name':'calendar_planning','description':'Analisa conflitos e intervalos livres de eventos de uma agenda Google REAL ou de eventos explicitamente fornecidos como JSON. Datas ISO com fuso. Se a consulta estiver paginada, nao declara disponibilidade definitiva. Nao cria compromissos nem notificacoes. Locais all-day sao indicados separadamente e nao ignorados silenciosamente.',
 'parameters':{'type':'OBJECT','properties':{'action':{'type':'STRING','enum':['analyze']},'source':{'type':'STRING','enum':['google','provided']},
 **{key:{'type':'STRING'} for key in ('start','end','events_json','calendar_id')},'minutes':{'type':'INTEGER'}},'required':['action','source','start','end']}}


def moment(value):
    result=datetime.fromisoformat(value.replace('Z','+00:00'))
    if result.tzinfo is None:raise ValueError('Datas precisam de fuso horario.')
    return result


def execute(p):
    import json
    start=moment(p.get('start',''));end=moment(p.get('end',''))
    if end<=start or end-start>timedelta(days=7):raise ValueError('Escolha intervalo de ate sete dias, com fim maior que inicio.')
    if p.get('source')=='google':
        from core.google_services import calendar
        response=calendar({'action':'list','calendar_id':p.get('calendar_id','primary'),'date_from':start.isoformat(),'date_to':end.isoformat(),'limit':100})
        items=response['items'];complete=response['complete']
    elif p.get('source')=='provided':
        items=json.loads(p.get('events_json','[]'));complete=False
        if not isinstance(items,list) or len(items)>100:raise ValueError('Envie ate cem eventos.')
    else:raise ValueError('Fonte invalida.')
    intervals=[];unknown=[]
    for item in items:
        if not isinstance(item,dict):raise ValueError('Evento invalido.')
        if item.get('status')=='cancelled' or item.get('transparency')=='transparent':continue
        if not item.get('start',{}).get('dateTime') or not item.get('end',{}).get('dateTime'):
            unknown.append(item.get('summary','Evento sem horario'));continue
        a=moment(item['start']['dateTime']);b=moment(item['end']['dateTime'])
        if b<=a:raise ValueError('Evento com intervalo invalido.')
        if b>start and a<end:intervals.append((max(a,start),min(b,end),item.get('summary','Evento')))
    intervals.sort();conflicts=[];free=[];cursor=start
    for index,(a,b,title) in enumerate(intervals):
        for c,d,other in intervals[index+1:]:
            if c>=b:break
            conflicts.append({'a':title,'b':other,'start':max(a,c).isoformat(),'end':min(b,d).isoformat()})
    for a,b,title in intervals:
        if a>cursor:free.append({'start':cursor.isoformat(),'end':a.isoformat()})
        cursor=max(cursor,b)
    if cursor<end:free.append({'start':cursor.isoformat(),'end':end.isoformat()})
    minutes=max(1,min(480,int(p.get('minutes',30))))
    free=[item for item in free if moment(item['end'])-moment(item['start'])>=timedelta(minutes=minutes)]
    return {'conflicts':conflicts,'free_intervals':free,'unresolved_events':unknown,'availability_confirmed':complete and not unknown,
        'source_complete':complete,'note':'Considera somente a agenda/fonte consultada; nao conhece outras contas ou eventos privados indisponiveis.','data_is_untrusted':True}

def run(parameters,**kwargs):return respond(lambda:execute(parameters))
