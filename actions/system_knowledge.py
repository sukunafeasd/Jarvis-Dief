"""Read-only introspection of the assistant's own approved structure."""
import json
from core.system_knowledge import system_catalog,component_outline,execution_guide


def system_knowledge(parameters,player=None,available_tools=None,session_memory=None,**kwargs):
    try:
        action=parameters.get('action','catalog')
        if action=='catalog':result=system_catalog(available_tools)
        elif action=='guide':result=execution_guide(parameters.get('target') or (session_memory.user_text if session_memory else ''),session_memory,available_tools)
        elif action=='component':
            result=component_outline(parameters.get('target',''),parameters.get('offset',0),parameters.get('limit',30))
        elif action=='tool':
            target=parameters.get('target','')
            declaration=next((item for item in (available_tools or []) if item.get('name')==target),None)
            if declaration is None:raise ValueError('Ferramenta não confirmada como disponível nesta sessão.')
            result={'declaration':declaration,'registered':True,'connection_verified':False}
        elif action=='runtime':
            if player is None:raise ValueError('Interface indisponível.')
            result=player.control_interface('inspect','','')
            if result.get('ok') is not True:return json.dumps(result,ensure_ascii=False)
            if session_memory:result['application_context']=session_memory.snapshot()
        else:raise ValueError('Ação desconhecida.')
        return json.dumps({'ok':True,'result':result,'source':'Estrutura local do DIEF JARVIS'},ensure_ascii=False)
    except (ValueError,TypeError,OSError,SyntaxError) as error:
        return json.dumps({'ok':False,'error':str(error)},ensure_ascii=False)


TOOL={'name':'system_knowledge','description':'Consulte SEU próprio sistema: catalog descreve páginas e domínios; component lista funções reais de módulo aprovado com paginação; tool fornece schema da ferramenta disponível; runtime inspeciona cena/contexto; guide sugere sequência observar/agir/verificar para o pedido humano atual. Não lê chaves, não executa código e não confunde ferramenta com conexão autorizada.',
    'parameters':{'type':'OBJECT','properties':{'action':{'type':'STRING','enum':['catalog','component','tool','runtime','guide']},
        'target':{'type':'STRING'},'offset':{'type':'INTEGER'},'limit':{'type':'INTEGER'}},'required':['action']},'handler':system_knowledge}
