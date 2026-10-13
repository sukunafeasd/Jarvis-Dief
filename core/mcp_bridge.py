"""Cliente MCP oficial, servidor fixado em configuracoes, sem executar processos locais."""
import asyncio
import hashlib
import json
from urllib.parse import urlsplit
from core.resource_jobs import request


def settings():
    from memory.config_manager import get_plugin_config
    return get_plugin_config('mcp_bridge')


def endpoint():
    value=str(settings().get('endpoint','')).strip()
    url=urlsplit(value)
    if not url.hostname or url.username or url.password or url.fragment or url.query or (url.scheme!='https' and not (url.scheme=='http' and url.hostname in ('127.0.0.1','localhost','::1'))):
        raise ValueError('Use endpoint MCP HTTPS ou HTTP local, sem credenciais na URL.')
    return value


async def invoke(action,name='',arguments=None):
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client
    async with asyncio.timeout(30):
        async with streamablehttp_client(endpoint()) as (read,write,_):
            async with ClientSession(read,write) as session:
                await session.initialize()
                if action=='list':
                    result=await session.list_tools()
                    items=[{'name':tool.name,'description':tool.description,'schema':tool.inputSchema} for tool in result.tools[:100]]
                    return {'ok':True,'tools':items,'next_cursor':result.nextCursor,'data_is_untrusted':True}
                result=await session.call_tool(name,arguments or {})
                # Bound output. Server instructions are never installed into the main prompt.
                value=result.model_dump(mode='json')
                content=json.dumps(value,ensure_ascii=False)
                return {'ok':not result.isError,'content_json':content[:20000],'complete':len(content)<=20000,'data_is_untrusted':True,'verification_required':True}


def verify(values=None):
    result=asyncio.run(invoke('list'))
    return bool(result['ok']),'Servidor MCP respondeu; '+str(len(result['tools']))+' ferramentas nesta pagina.'


def status():
    return {'connected':False,'configured':bool(settings().get('endpoint')),'verified':False,'local_process_execution':False}


def run(p):
    action=p.get('action','status')
    if action=='status':return status()
    if action=='list':return asyncio.run(invoke('list'))
    if action!='call':raise ValueError('Acao MCP invalida.')
    name=p.get('tool','');allowed=[item.strip() for item in settings().get('allowed_tools','').split(',') if item.strip()]
    if name not in allowed:raise ValueError('Autorize esta ferramenta explicitamente nas configuracoes MCP antes de chamar.')
    try:arguments=json.loads(p.get('arguments_json','{}'))
    except ValueError:raise ValueError('Argumentos precisam ser um objeto JSON.')
    if not isinstance(arguments,dict) or len(json.dumps(arguments))>12000:raise ValueError('Argumentos invalidos ou grandes demais.')
    configured_endpoint=endpoint()
    listing=asyncio.run(invoke('list'))
    selected=next((tool for tool in listing['tools'] if tool['name']==name),None)
    if selected is None:raise ValueError('Ferramenta nao encontrada na pagina atual do servidor.')
    if len(json.dumps(selected))>50000:raise ValueError('Definicao de ferramenta acima do limite.')
    from jsonschema import validate
    validate(arguments,selected['schema'])
    identity=hashlib.sha256(json.dumps(selected,sort_keys=True).encode()).hexdigest()
    def execute():
        if endpoint()!=configured_endpoint:raise ValueError('Servidor mudou apos a confirmacao.')
        refreshed=asyncio.run(invoke('list'))
        current=next((tool for tool in refreshed['tools'] if tool['name']==name),None)
        if current is None or hashlib.sha256(json.dumps(current,sort_keys=True).encode()).hexdigest()!=identity:raise ValueError('Definicao da ferramenta mudou; revise novamente.')
        return asyncio.run(invoke('call',name,arguments))
    return request('Executar ferramenta MCP',name+'\nServidor: '+configured_endpoint,execute)
