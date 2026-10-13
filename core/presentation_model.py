"""Contrato defensivo para dados parciais de ferramentas, sem fabricar fatos."""
import math


def finite_number(value):
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def normalize_model(value):
    result=dict(value)
    for field in ('items','forecast'):
        rows=value.get(field)
        result[field]=[dict(row) for row in rows if isinstance(row,dict)] if isinstance(rows,list) else []
        for row in result[field]:
            for text_field in ('title','detail','due','source','sender','subject','snippet','date'):
                if text_field in row and not isinstance(row[text_field],str):row[text_field]=''
            for key, number in list(row.items()):
                if isinstance(number,(int,float)) and not isinstance(number,bool) and not finite_number(number):row[key]=None
    for field in ('title','city','condition','source','text','error'):
        if not isinstance(result.get(field),str):result[field]=''
    for field in ('emptyText','region','observed','uptime'):
        if field in result and not isinstance(result[field],str):result[field]=''
    for key, number in list(result.items()):
        if isinstance(number,(int,float)) and not isinstance(number,bool) and not finite_number(number):result[key]=None
    if not result['title']:
        result['title']={'weather':'CLIMA','system':'SISTEMA','tasks':'TAREFAS','calendar':'AGENDA',
                         'news':'NOTÍCIAS','files':'ARQUIVOS','memory':'MEMÓRIA','search':'BUSCA',
                         'gmail':'GMAIL','whatsapp':'WHATSAPP','status':'VERIFICANDO'}.get(result.get('kind'),'INFORMAÇÕES')
    try:focus=int(result.get('focus',0))
    except (ValueError,TypeError,OverflowError):focus=0
    result['focus']=max(0,min(max(0,len(result['items'])-1),focus))
    return result


def shown_number(value):
    if finite_number(value):
        return str(value)
    return '--'


def record_text(row):
    title = row.get('title') or ''
    detail = row.get('detail') or row.get('due') or ''
    return ' · '.join(part for part in (title, detail) if isinstance(part,str) and part.strip())
