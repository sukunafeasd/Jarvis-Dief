"""Resolve ordinal references against the visible semantic scene before cached pages."""


def resolve_selection(domain,index,context=None,player=None,collection=None):
    if not isinstance(index,int) or isinstance(index,bool) or index<1:
        raise ValueError('Use uma posição positiva da lista realmente consultada.')
    if player is not None:
        observed=player.control_interface('inspect')
        if not isinstance(observed,dict) or observed.get('ok') is not True:
            raise ValueError('Nao consegui verificar a apresentacao atual. Consulte a lista novamente; nao usei uma lista antiga para escolher o alvo.')
        if isinstance(observed,dict) and observed.get('ok'):
            screen=observed.get('screen',{})
            if not isinstance(screen,dict):raise ValueError('Estado da tela invalido; consulte a lista novamente.')
            presentation=screen.get('presentation',{})
            if not isinstance(presentation,dict):raise ValueError('Apresentacao invalida; consulte a lista novamente.')
            usable=presentation.get('visible') and presentation.get('kind')==domain
            if domain=='whatsapp' and presentation.get('reading'):usable=False
            if usable:
                references=screen.get('references',[])
                if not isinstance(references,list):raise ValueError('Referencias indisponiveis na apresentacao atual.')
                matches=[item for item in references if isinstance(item,dict) and type(item.get('position')) is int and item.get('position')==index and item.get('domain')==domain]
                if len(matches)!=1 or matches[0].get('id') is None:
                    raise ValueError('Esse item não existe na apresentação atual. Não usei uma lista antiga.')
                identifier=matches[0]['id']
                if type(identifier) not in (str,int) or isinstance(identifier,str) and not identifier.strip():
                    raise ValueError('Identificador invalido na apresentacao atual; consulte a lista novamente.')
                result={'id':matches[0]['id'],'title':matches[0].get('title','')}
                if matches[0].get('thread_id'):result['thread_id']=matches[0]['thread_id']
                if domain=='whatsapp':result['contact']=result['id']
                if context is not None:context.remember_selection(collection or domain,result)
                return result
    if context is None:raise ValueError('Consulte a lista antes de selecionar por número.')
    return context.resolve_record(collection or domain,index)
