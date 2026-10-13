"""Resolve ordinal references against the visible semantic scene before cached pages."""


def resolve_selection(domain,index,context=None,player=None,collection=None):
    if not isinstance(index,int) or isinstance(index,bool) or index<1:
        raise ValueError('Use uma posição positiva da lista realmente consultada.')
    if player is not None:
        observed=player.control_interface('inspect')
        if isinstance(observed,dict) and observed.get('ok'):
            screen=observed.get('screen',{})
            presentation=screen.get('presentation',{})
            usable=presentation.get('visible') and presentation.get('kind')==domain
            if domain=='whatsapp' and presentation.get('reading'):usable=False
            if usable:
                matches=[item for item in screen.get('references',[]) if item.get('position')==index and item.get('domain')==domain]
                if len(matches)!=1 or matches[0].get('id') is None:
                    raise ValueError('Esse item não existe na apresentação atual. Não usei uma lista antiga.')
                result={'id':matches[0]['id'],'title':matches[0].get('title','')}
                if matches[0].get('thread_id'):result['thread_id']=matches[0]['thread_id']
                if domain=='whatsapp':result['contact']=result['id']
                return result
    if context is None:raise ValueError('Consulte a lista antes de selecionar por número.')
    return context.resolve_record(collection or domain,index)
