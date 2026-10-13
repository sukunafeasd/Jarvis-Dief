"""Home Assistant REST: destino fixado nas configuracoes, token protegido por DPAPI."""
import re
from urllib.parse import urlsplit
import requests
from core import integration_tokens as tokens
from core.resource_jobs import request


def settings():
    from memory.config_manager import get_plugin_config
    return get_plugin_config('home_automation')


def endpoint():
    base=str(settings().get('base_url','')).strip().rstrip('/')
    url=urlsplit(base)
    if url.scheme not in ('http','https') or not url.hostname or url.username or url.password or url.query or url.fragment or url.path not in ('','/'):
        raise ValueError('Configure a URL raiz do seu Home Assistant, sem senha na URL.')
    return base


def configure(values):
    endpoint()
    secret=str(values.get('access_token','')).strip()
    if secret:
        if len(secret)<20:raise ValueError('Token de acesso invalido.')
        tokens.write('home_automation',{'token':secret})
        from memory.config_manager import save_plugin_config
        save_plugin_config('home_automation',{'access_token':''})
    result=call('GET','/api/')
    return bool(result.get('message')),'Home Assistant respondeu ao teste da API.'


def call(method,path,data=None):
    token=tokens.read('home_automation').get('token')
    if not token:raise ValueError('Salve um token do Home Assistant nas conexoes.')
    response=requests.request(method,endpoint()+path,headers={'Authorization':'Bearer '+token},json=data,timeout=(5,15),allow_redirects=False)
    if response.status_code in (301,302,303,307,308):raise ValueError('Redirecionamento recusado; configure a URL final do servidor.')
    response.raise_for_status()
    if len(response.content)>2*1024*1024:raise ValueError('Resposta acima do limite.')
    return response.json()


def status():
    try:
        configured=bool(settings().get('base_url'));saved=bool(tokens.read('home_automation').get('token'))
        return {'configured':configured,'connected':saved,'verified':False}
    except Exception:return {'configured':False,'connected':False,'verified':False}


def verify():
    call('GET','/api/');return True,'Conexao confirmada com o Home Assistant.'


def run(p):
    action=p.get('action','status')
    if action=='status':return status()
    if action=='entities':
        items=call('GET','/api/states')
        query=str(p.get('query','')).casefold()
        items=[{'id':item['entity_id'],'state':item['state'],'name':item.get('attributes',{}).get('friendly_name','')} for item in items if query in (item['entity_id']+' '+item.get('attributes',{}).get('friendly_name','')).casefold()]
        offset=max(0,int(p.get('offset',0)));limit=max(1,min(100,int(p.get('limit',30))))
        return {'items':items[offset:offset+limit],'total':len(items),'next_offset':offset+limit if offset+limit<len(items) else None,'data_is_untrusted':True}
    entity=str(p.get('entity_id',''))
    if not re.fullmatch(r'[a-z_]+\.[a-z0-9_]+',entity):raise ValueError('Use entity_id real da consulta anterior.')
    if action=='read':return {'entity':call('GET','/api/states/'+entity),'data_is_untrusted':True}
    domain=entity.split('.')[0]
    service=p.get('service')
    allowed={'light':{'turn_on','turn_off'},'switch':{'turn_on','turn_off'},'fan':{'turn_on','turn_off'}}
    if action!='control' or service not in allowed.get(domain,set()):raise ValueError('Controle inicial permite somente ligar/desligar luzes, interruptores e ventiladores; nao controla fechaduras ou alarmes.')
    call('GET','/api/states/'+entity)
    def execute():
        call('POST','/api/services/'+domain+'/'+service,{'entity_id':entity})
        observed=call('GET','/api/states/'+entity)
        expected='on' if service=='turn_on' else 'off'
        return {'ok':observed.get('state')==expected,'entity_id':entity,'state':observed.get('state'),'uncertain':observed.get('state')!=expected}
    return request('Controlar dispositivo da casa',entity+' · '+service,execute)
