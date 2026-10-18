"""Curated adapters; availability is measured, never inferred from enablement."""
import asyncio
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import hashlib
from contextlib import AsyncExitStack
from concurrent.futures import Future
from core import integration_tokens

ROOT = Path(__file__).resolve().parents[1]
CATALOG = {
 'playwright_mcp': {'title': 'Playwright MCP', 'source': 'https://github.com/microsoft/playwright-mcp', 'kind': 'stdio', 'entry': 'playwright-mcp.exe', 'module': None},
 'windows_mcp': {'title': 'Windows MCP', 'source': 'https://github.com/CursorTouch/Windows-MCP', 'kind': 'stdio', 'entry': 'windows-mcp.exe', 'args': ['serve'], 'module': None},
 'github_mcp': {'title': 'GitHub MCP', 'source': 'https://github.com/github/github-mcp-server', 'kind': 'http', 'endpoint': 'https://api.githubcopilot.com/mcp/', 'account': True, 'setup': 'https://github.com/settings/personal-access-tokens'},
 'context7': {'title': 'Context7', 'source': 'https://github.com/upstash/context7', 'kind': 'http', 'endpoint': 'https://mcp.context7.com/mcp', 'account': True, 'setup': 'https://context7.com/dashboard'},
 'markitdown': {'title': 'MarkItDown', 'source': 'https://github.com/microsoft/markitdown', 'kind': 'local', 'module': 'markitdown'},
 'qdrant_memory': {'title': 'Memória semântica Qdrant', 'source': 'https://github.com/qdrant/qdrant-client', 'kind': 'local', 'module': 'qdrant_client'},
 'deep_research': {'title': 'GPT Researcher', 'source': 'https://github.com/assafelovic/gpt-researcher', 'kind': 'local', 'module': 'gpt_researcher', 'account': True, 'setup': 'https://platform.openai.com/api-keys'},
 'local_transcription': {'title': 'Transcrição Faster Whisper', 'source': 'https://github.com/SYSTRAN/faster-whisper', 'kind': 'local', 'module': 'faster_whisper'},
}
WORKERS = {}
VERIFIED = {}
LOCK = threading.RLock()


def config(name):
    from memory.config_manager import get_plugin_config
    return get_plugin_config(name)


def command(name):
    record = CATALOG[name]
    path = str(config(name).get('executable', '')).strip()
    candidate = Path(path) if path else Path.home()/'.local/bin/windows-mcp.exe' if name=='windows_mcp' else Path(os.environ.get('LOCALAPPDATA',''))/'DIEF-JARVIS/runtime/node/node_modules/@playwright/mcp/cli.js'
    if not candidate.is_absolute() or not candidate.is_file() or candidate.suffix.lower() not in ('.exe', '.js'):
        raise ValueError('Selecione o executavel instalado desta ferramenta em Conexoes.')
    if candidate.suffix.lower() == '.js':
        node = Path(str(config(name).get('node_executable') or Path(os.environ.get('LOCALAPPDATA',''))/'DIEF-JARVIS/runtime/node/node.exe'))
        if not node.is_absolute() or not node.is_file() or node.name.lower() != 'node.exe':
            raise ValueError('Informe o caminho real do Node.js para este servidor.')
        return str(node), [str(candidate), '--headless']
    return str(candidate), record.get('args', [])


def fingerprint(name):
    value={'config':config(name),'token':integration_tokens.read(name) if CATALOG[name].get('account') else {}}
    return hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()


def research_python():
    return Path(os.environ.get('LOCALAPPDATA',''))/'DIEF-JARVIS/runtime/research/Scripts/python.exe'


def status(name):
    record = CATALOG[name]
    available = bool(importlib.util.find_spec(record['module'])) if record.get('module') else False
    if name=='qdrant_memory':available=available and bool(importlib.util.find_spec('fastembed'))
    if name=='deep_research':available=available or research_python().is_file()
    if record['kind'] == 'stdio':
        try:
            command(name);available = True
        except ValueError:
            pass
    if record['kind'] == 'http':
        available = bool(importlib.util.find_spec('mcp'))
    try:authorized = bool(integration_tokens.read(name).get('token')) if record.get('account') else True
    except Exception:authorized=False
    connected=bool(available and authorized and VERIFIED.get(name)==fingerprint(name))
    return {'ok': True, 'enabled': True, 'installed': available, 'authorized': authorized,
            'account_required': bool(record.get('account')), 'verified': False,
            'connected': connected, 'configured':authorized,'source': record['source'],
            'state': 'available' if available and authorized else 'disconnected' if not authorized else 'error',
            'message': 'Disponível para teste.' if available and authorized else 'Configure a autorização em Conexões.' if not authorized else 'Dependência ou executável ainda não instalado.'}


class ServerWorker:
    """All MCP contexts are owned and closed by the same coroutine/task."""
    def __init__(self, name):
        self.name = name;self.loop = asyncio.new_event_loop();self.queue = None
        self.ready = threading.Event();self.closed = False;self.closing=False;self.identity=fingerprint(name);self.main_task=None
        self.thread = threading.Thread(target=self._thread, name='Jarvis MCP '+name, daemon=True)
        self.thread.start();self.ready.wait(3)

    def _thread(self):
        asyncio.set_event_loop(self.loop)
        try:
            self.main_task=self.loop.create_task(self._run())
            self.loop.run_until_complete(self.main_task)
        except asyncio.CancelledError:pass
        finally:
            self.closed = True;self.loop.close()

    async def _run(self):
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        from mcp.client.streamable_http import streamablehttp_client
        self.queue = asyncio.Queue(maxsize=8);self.ready.set()
        current = None
        try:
            async with AsyncExitStack() as stack:
                record = CATALOG[self.name]
                if record['kind'] == 'stdio':
                    executable, args = command(self.name)
                    environment={key: value for key, value in os.environ.items() if key.upper() in ('PATH','SYSTEMROOT','TEMP','TMP','USERPROFILE','LOCALAPPDATA','APPDATA')}
                    environment['ANONYMIZED_TELEMETRY']='false'
                    if self.name=='windows_mcp':args=args+['--exclude-tools','App']
                    params = StdioServerParameters(command=executable, args=args,env=environment)
                    streams = await stack.enter_async_context(stdio_client(params))
                else:
                    token = integration_tokens.read(self.name).get('token')
                    if not token:
                        raise ValueError('Autorize esta conexao no painel.')
                    streams = await stack.enter_async_context(streamablehttp_client(record['endpoint'], headers={'Authorization': 'Bearer '+token}))
                session = await stack.enter_async_context(ClientSession(streams[0], streams[1]))
                async with asyncio.timeout(20):await session.initialize()
                while True:
                    item = await asyncio.wait_for(self.queue.get(), 300)
                    if item is None:
                        break
                    action, name, arguments, future, expected, expiry = item;current = future
                    if future.done() or time.monotonic()>expiry or self.closing:
                        if not future.done():future.set_exception(ValueError('Chamada expirada antes da execucao.'))
                        current=None;continue
                    try:
                        async with asyncio.timeout(90):
                            if self.identity!=fingerprint(self.name):raise ValueError('Configuracao mudou; conecte novamente.')
                            listing = [];cursor = None
                            for _ in range(5):
                                page = await session.list_tools(cursor=cursor)
                                listing.extend(page.tools);cursor = page.nextCursor
                                if not cursor:
                                    break
                            if action == 'list':
                                result = {'ok': True, 'tools': [{'name': tool.name, 'description': tool.description, 'schema': tool.inputSchema,'definition_hash':hashlib.sha256(json.dumps(tool.model_dump(mode='json'),sort_keys=True).encode()).hexdigest()} for tool in listing[:250]], 'complete': not cursor}
                            else:
                                from jsonschema import validate
                                selected = next((tool for tool in listing if tool.name == name), None)
                                if selected is None:
                                    raise ValueError('Ferramenta nao encontrada no catalogo atual.')
                                identity=hashlib.sha256(json.dumps(selected.model_dump(mode='json'),sort_keys=True).encode()).hexdigest()
                                if expected and identity!=expected:raise ValueError('Definicao mudou depois da confirmacao.')
                                validate(arguments, selected.inputSchema)
                                response = await session.call_tool(name, arguments)
                                value = json.dumps(response.model_dump(mode='json'), ensure_ascii=False)
                                result = {'ok': not response.isError, 'content_json': value[:20000], 'complete': len(value)<=20000, 'data_is_untrusted': True, 'verification_required': True}
                            if not future.done():future.set_result(result)
                    except Exception:
                        if not future.done():future.set_exception(ValueError('Servidor nao confirmou a operacao; nao repita alteracoes sem verificar.'))
                    finally:
                        current = None
        except Exception:
            if current and not current.done():current.set_exception(ValueError('Conexao MCP encerrada.'))
        finally:
            self.closed = True
            if current and not current.done():current.set_exception(ValueError('Conexao encerrada; resultado incerto.'))
            while not self.queue.empty():
                item = self.queue.get_nowait()
                if item is not None and not item[3].done():item[3].set_exception(ValueError('Servidor MCP indisponivel.'))

    def invoke(self, action, name='', arguments=None,expected=None):
        if self.closed or self.closing or self.queue is None:
            raise ValueError('Servidor MCP indisponivel; confira a conexao.')
        future = Future()
        def enqueue():
            if self.closed or self.closing or self.queue.full():future.set_exception(ValueError('Servidor ocupado ou encerrado.'))
            else:self.queue.put_nowait((action, name, arguments or {}, future,expected,time.monotonic()+95))
        self.loop.call_soon_threadsafe(enqueue)
        try:return future.result(100)
        except TimeoutError:
            future.cancel();self.close()
            raise ValueError('Tempo de espera esgotado; resultado incerto, nao repetir automaticamente.')

    def close(self):
        self.closing=True
        if not self.closed and self.main_task is not None:
            self.loop.call_soon_threadsafe(self.main_task.cancel)


def invoke_server(name, action, tool='', arguments=None,expected=None):
    from memory.config_manager import get_plugin_enabled
    if not get_plugin_enabled(name):raise ValueError('Plugin desativado.')
    with LOCK:
        worker = WORKERS.get(name)
        if worker is None or worker.closed or worker.closing:
            worker = ServerWorker(name);WORKERS[name] = worker
    return worker.invoke(action, tool, arguments,expected)


def shutdown():
    with LOCK:
        workers=list(WORKERS.values())
        for worker in workers:worker.close()
        WORKERS.clear()
    for worker in workers:worker.thread.join(timeout=2)


def reset(name):
    VERIFIED.pop(name,None)
    with LOCK:
        worker = WORKERS.pop(name, None)
        if worker:worker.close()


def run(name, parameters):
    action = parameters.get('action', 'status')
    if action == 'status':return status(name)
    if action == 'list' and CATALOG[name]['kind'] in ('stdio','http'):return invoke_server(name, 'list')
    if action == 'call' and CATALOG[name]['kind'] in ('stdio','http'):
        from core.resource_jobs import request
        arguments = json.loads(parameters.get('arguments_json', '{}'))
        if not isinstance(arguments, dict) or len(json.dumps(arguments))>12000:raise ValueError('Argumentos MCP invalidos.')
        tool = str(parameters.get('tool', ''))
        listing=invoke_server(name,'list')
        selected=next((entry for entry in listing['tools'] if entry['name']==tool),None)
        if selected is None:raise ValueError('Ferramenta nao encontrada.')
        from jsonschema import validate
        validate(arguments,selected['schema'])
        approved=fingerprint(name)
        expected=selected['definition_hash']
        def execute():
            if approved!=fingerprint(name):raise ValueError('Conta ou executavel mudou depois da confirmacao.')
            return invoke_server(name,'call',tool,arguments,expected)
        safe = {'context7': {'resolve-library-id', 'query-docs'}, 'github_mcp': {'get_file_contents', 'list_issues', 'search_repositories', 'search_code', 'get_me'}}
        if tool in safe.get(name, set()):return invoke_server(name,'call',tool,arguments)
        return request('Executar '+CATALOG[name]['title'], tool+'\n'+json.dumps(arguments, ensure_ascii=False)[:1000],
                       execute)
    if name == 'markitdown' and action == 'read':
        from core.file_library import safe_path
        path = safe_path(parameters.get('path', ''))
        if not path.is_file() or path.stat().st_size>25*1024*1024 or path.suffix.lower() not in ('.pdf','.docx','.pptx','.xlsx','.csv','.txt','.md','.html'):
            raise ValueError('Escolha documento local suportado de ate 25 MB.')
        from markitdown import MarkItDown
        content = MarkItDown(enable_plugins=False).convert(str(path)).text_content
        offset = max(0,int(parameters.get('offset',0)))
        return {'ok':True,'text':content[offset:offset+12000],'next_offset':offset+12000 if offset+12000<len(content) else None,'data_is_untrusted':True}
    if name == 'qdrant_memory':
        if action!='search':raise ValueError('Use search para consultar memoria semantica.')
        from core.semantic_memory import run as semantic_run
        return semantic_run(parameters)
    if name == 'local_transcription' and action == 'transcribe':
        from core.local_transcription import run as transcribe
        return transcribe(parameters)
    if name == 'deep_research' and action == 'research':
        from core.resource_jobs import request
        query = str(parameters.get('query','')).strip()
        if not query or len(query)>1200:raise ValueError('Pesquisa requer assunto de ate 1200 caracteres.')
        return request('Pesquisa aprofundada',query+'\nUsa API externa com custo; limite de 5 minutos.',lambda: research(query))
    raise ValueError('Acao nao suportada por esta ferramenta.')


def research(query):
    token = integration_tokens.read('deep_research').get('token')
    if not token:raise ValueError('Configure a chave de pesquisa em Conexoes.')
    environment = dict(os.environ, OPENAI_API_KEY=token, RETRIEVER='duckduckgo')
    executable=str(research_python()) if research_python().is_file() else sys.executable
    result = subprocess.run([executable,str(ROOT/'tools/research_worker.py'),query],
        env=environment,capture_output=True,text=True,encoding='utf-8',timeout=300,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    if result.returncode:raise ValueError('Pesquisa nao concluida; confira provedor e dependencias.')
    return json.loads(result.stdout.split('JARVIS_REPORT:')[-1])


def verify(name, values=None):
    reset(name)
    value = status(name)
    if not value['installed'] or not value['authorized']:return False,value['message']
    if CATALOG[name]['kind'] in ('stdio','http'):
        result = invoke_server(name,'list')
        if result['ok']:VERIFIED[name]=fingerprint(name)
        return bool(result['ok']),str(len(result['tools']))+' ferramentas responderam.'
    if name=='deep_research':
        import requests
        response=requests.get('https://api.openai.com/v1/models',headers={'Authorization':'Bearer '+integration_tokens.read(name)['token']},timeout=(5,20),allow_redirects=False)
        if response.status_code!=200:return False,'OpenAI nao confirmou a chave de pesquisa (HTTP '+str(response.status_code)+').'
        VERIFIED[name]=fingerprint(name)
        return True,'OpenAI autorizou consulta de modelos; pesquisa usa cota e requer confirmacao.'
    VERIFIED[name]=fingerprint(name)
    return True,'Dependencia local confirmada; modelo de audio/embeddings carregado somente ao usar.'
