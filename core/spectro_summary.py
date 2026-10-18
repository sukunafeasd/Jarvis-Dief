"""Compact desktop notes from actual structured presentation results."""


def summary(data):
    title=str(data.get('title') or data.get('kind') or 'Informacao')
    if data.get('error'):return (title+': '+str(data['error']))[:220]
    parts=[]
    if data.get('kind')=='weather':
        if data.get('city'):parts.append(str(data['city']))
        if data.get('temperature') is not None:parts.append(str(data['temperature'])+' C')
        if data.get('condition'):parts.append(str(data['condition']))
    else:
        text=data.get('text') or data.get('summary')
        if text:parts.append(str(text))
        items=data.get('items')
        if isinstance(items,list):
            if not items:parts.append('Nenhum item retornado nesta consulta')
            for item in items[:3]:
                if isinstance(item,dict):
                    value=next((item[k] for k in ('title','name','subject','text','summary') if item.get(k)),None)
                    if value:parts.append(str(value))
                elif isinstance(item,str):parts.append(item)
            if len(items)>3:parts.append('+ '+str(len(items)-3)+' itens')
        for key,label in (('cpu','CPU'),('memory','Memoria'),('disk','Disco')):
            if type(data.get(key)) in (int,float):parts.append(label+': '+str(data[key])+'%')
    return (title+(': '+' | '.join(parts) if parts else ''))[:220]
