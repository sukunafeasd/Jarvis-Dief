"""Notion com token protegido e validacao de identidade antes de substituir conta."""
import re
import threading
import requests
from core import integration_tokens as tokens
from core.resource_jobs import request
LOCK=threading.RLock()


def settings():
    from memory.config_manager import get_plugin_config
    return get_plugin_config('notion_service')


def call(method,path,body=None,token=None):
    token=token or tokens.read('notion_service').get('token')
    if not token:raise ValueError('Conecte o Notion nas Conexoes e compartilhe as paginas com a integracao.')
    response=requests.request(method,'https://api.notion.com/v1'+path,headers={'Authorization':'Bearer '+token,'Notion-Version':'2025-09-03'},json=body,timeout=(5,20),allow_redirects=False)
    response.raise_for_status()
    if len(response.content)>2*1024*1024:raise ValueError('Resposta Notion acima do limite.')
    return response.json()


def validate(profile):
    identifier=profile.get('id')
    expected=str(settings().get('expected_identity_id','')).strip()
    if not identifier or expected and identifier!=expected:raise ValueError('Identidade Notion diferente da esperada; conexao anterior preservada.')
    return identifier


def connect(values=None):
    with LOCK:
        candidate=tokens.read('notion_candidate').get('token') or tokens.read('notion_service').get('token')
        if not candidate:return False,'Informe o token da integracao Notion no formulario, nao na conversa.'
        profile=call('GET','/users/me',token=candidate)
        identifier=validate(profile)
        label=profile.get('name') or profile.get('bot',{}).get('workspace_name') or identifier
        tokens.write('notion_service',{'token':candidate,'identity_id':identifier,'account':label})
        tokens.remove('notion_candidate')
        return True,'Notion confirmado: '+label+' · '+identifier


def status():
    try:
        saved=tokens.read('notion_service');expected=str(settings().get('expected_identity_id','')).strip()
        matches=not expected or expected==saved.get('identity_id')
        return {'configured':bool(saved.get('token') or tokens.read('notion_candidate').get('token')),'connected':bool(saved.get('token') and matches),'account':saved.get('account','') if matches else '', 'verified':False}
    except Exception:return {'configured':False,'connected':False,'verified':False}


def verify():
    profile=call('GET','/users/me');validate(profile)
    return True,'Identidade Notion confirmada: '+str(profile.get('name') or profile['id'])


def identifier(value):
    if not re.fullmatch(r'[0-9a-fA-F-]{32,36}',str(value or '')):raise ValueError('Use ID real da pagina/bloco obtido na pesquisa.')
    return value


def run(p):
    action=p.get('action','status')
    if action=='status':return status()
    if not status()['connected']:raise ValueError('Conecte a identidade Notion esperada antes de consultar paginas.')
    if action=='search':
        body={'page_size':max(1,min(50,int(p.get('limit',20)))),'filter':{'property':'object','value':'page'}}
        if p.get('query'):body['query']=str(p['query'])[:300]
        if p.get('cursor'):body['start_cursor']=str(p['cursor'])[:1000]
        result=call('POST','/search',body)
        items=[]
        for page in result.get('results',[]):
            titles=[prop.get('title',[]) for prop in page.get('properties',{}).values() if prop.get('type')=='title']
            items.append({'id':page['id'],'title':''.join(t.get('plain_text','') for group in titles for t in group),'url':page.get('url'),'edited':page.get('last_edited_time')})
        return {'items':items,'next_cursor':result.get('next_cursor'),'complete':not result.get('has_more'),'data_is_untrusted':True}
    if action=='read':
        block=identifier(p.get('id'));cursor=p.get('cursor','')
        from urllib.parse import urlencode
        params={'page_size':50}
        if cursor:params['start_cursor']=str(cursor)[:1000]
        result=call('GET','/blocks/'+block+'/children?'+urlencode(params))
        items=[]
        for item in result.get('results',[]):
            payload=item.get(item.get('type',''),{})
            items.append({'id':item['id'],'type':item.get('type'),'text':''.join(part.get('plain_text','') for part in payload.get('rich_text',[])),'has_children':bool(item.get('has_children'))})
        return {'items':items,'next_cursor':result.get('next_cursor'),'complete':not result.get('has_more') and not any(item['has_children'] for item in items),'data_is_untrusted':True,'note':'Filhos aninhados exigem read com ID do bloco; nem todos os tipos de bloco possuem texto extraivel.'}
    if action!='create':raise ValueError('Acao Notion invalida.')
    parent=identifier(p.get('parent_id'));title=str(p.get('title',''));text=str(p.get('text',''))
    if not title or len(title)>300 or len(text)>20000:raise ValueError('Informe titulo de ate 300 caracteres e texto de ate 20 mil.')
    call('GET','/pages/'+parent)
    saved=tokens.read('notion_service');identity=saved.get('identity_id')
    blocks=[{'object':'block','type':'paragraph','paragraph':{'rich_text':[{'type':'text','text':{'content':text[i:i+2000]}}]}} for i in range(0,len(text),2000)]
    body={'parent':{'page_id':parent},'properties':{'title':{'type':'title','title':[{'type':'text','text':{'content':title}}]}},'children':blocks}
    def create():
        if tokens.read('notion_service').get('identity_id')!=identity:raise ValueError('Identidade Notion mudou; prepare novamente.')
        validate(call('GET','/users/me'))
        page=call('POST','/pages',body)
        return {'ok':bool(page.get('id')),'id':page.get('id'),'url':page.get('url'),'verification_required':True}
    return request('Criar pagina Notion',title+'\nNa pagina compartilhada: '+parent,create)
