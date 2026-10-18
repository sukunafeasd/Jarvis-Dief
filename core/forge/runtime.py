"""Synchronous parent contract backed by one non-Qt asyncio worker.

Only trusted host code may call command/connect/validate_preview. Never expose
this facade to generated pages or accept model-supplied approval/export paths.
"""
from __future__ import annotations

import asyncio
from collections import deque
import copy
import json
import concurrent.futures
import os
from pathlib import Path
import re
import shutil
import threading
import time

from core.local_data import ROOT,atomic_write
from .files import ProjectStore, check_chain, hashes, relative, read_file
from .preview import PreviewServer
from .transport import AppServer, RpcError

DEFAULT_CODEX = Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'AppData/Local'))) / 'OpenAI/Codex/codex.exe'
INSTRUCTIONS = ('You create files only in the project cwd. Do not read host secrets, profiles, '
                'memory or credentials. Do not install globally, publish, export, or escalate '
                'privileges. Never use a Qt/native host bridge. For web projects provide local '
                'index.html and local assets. Report actual tests and failures, not assumed success. '
                'For 3D use the supplied vendor/three.module.js with its adjacent three.core.js. '
                'Use local ES imports (or an import map pointing three at ./vendor/three.module.js); '
                'no CDN or network imports. If vendor assets are absent, report that limitation.')


def discover_codex():
    found = shutil.which('codex.exe') or shutil.which('codex')
    if found and Path(found).suffix.lower() == '.exe':
        return Path(found)
    bundle = Path(os.environ.get('LOCALAPPDATA', '')) / 'OpenAI/Codex/bin'
    candidates = list(bundle.glob('*/codex.exe')) if bundle.is_dir() else []
    if candidates:
        return max(candidates, key=lambda p: p.stat().st_mtime)
    return DEFAULT_CODEX


def public_text(value):
    text = str(value)[:4096]
    text = re.sub(r'(?i)\b(?:sk-[a-z0-9_-]{8,}|eyJ[a-z0-9_.-]{20,})', '[redacted]', text)
    return re.sub(r'(?i)(api[_ -]?key|access[_ -]?token|refresh[_ -]?token|password|secret)'
                  r'\s*[:=]\s*[^\s,;]+', r'\1=[redacted]', text)


def public_error(value):
    text=public_text(value)
    if 'usage limit' in text.lower() or 'quota exceeded' in text.lower():
        return 'O limite de uso da sua conta Codex foi atingido. Aguarde a renovacao do limite ou consulte o uso da conta ChatGPT. A conexao continua valida e o projeto foi preservado.'
    return text


class ForgeRuntime:
    def __init__(self, *, data_root=None, executable=None, export_roots=(),
                 request_timeout=15, turn_timeout=900, transport_factory=AppServer):
        self.root = check_chain(Path(data_root) if data_root else ROOT / 'forge')
        self.executable = Path(executable) if executable else discover_codex()
        self.timeout = max(1, min(float(request_timeout), 60))
        self.turn_timeout = max(1, float(turn_timeout))
        self.factory = transport_factory
        self.export_roots = export_roots
        self.gate = threading.RLock()
        self.ready = threading.Event()
        self.closed = False
        self.events = deque(maxlen=256)
        self._command_epoch=0
        self.state = {'phase': 'idle', 'connection': 'not_configured', 'transport': 'stopped',
                      'authenticated': False, 'generation_verified': False, 'account': None,
                      'project': None, 'projects': [], 'activities': [], 'preview_url': None,
                      'candidate_preview_url': None, 'request': None, 'serial': 0,
                      'turn_id': None, 'preview_error': None, 'preview_validation':'none',
                      'command_epoch':0,'command_pending':False,
                      'sandbox': {'mode': 'workspace-write', 'readiness': 'unknown',
                                  'read_isolation': False, 'network_access': False,
                                  'limitation': 'Installed schema cannot restrict reads of host files.'},
                      'models': [], 'model': '', 'error': None}
        self.thread = threading.Thread(target=self._worker, name='ForgeRuntime', daemon=True)
        self.thread.start()
        if not self.ready.wait(5):
            raise RuntimeError('FORJA worker did not start')

    def _worker(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.operation_lock = asyncio.Lock()
        self.client = None
        self.store = None
        self.preview = None
        self.project = None
        self.active_turn = None
        self.finished_turns = deque(maxlen=128)
        self.watchdog = None
        self.login_id = None
        self.jobs = set()
        self._session_recovery = False
        self._restore_session()
        self.ready.set()
        try:
            self.loop.run_forever()
        finally:
            pending = asyncio.all_tasks(self.loop)
            for task in pending:
                task.cancel()
            self.loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            self.loop.run_until_complete(self.loop.shutdown_asyncgens())
            self.loop.close()

    def _restore_session(self):
        try:
            self.store=ProjectStore(self.root,self.export_roots)
            session=check_chain(self.root/'session.json')
            if session.exists():
                saved=json.loads(read_file(self.root,'session.json'))
                if not isinstance(saved,dict) or not isinstance(saved.get('project_id'),str) or not saved['project_id']:
                    raise ValueError('Invalid saved session')
                self.project=self.store.load(saved['project_id'])
            else:
                candidates=sorted((self.root/'projects').glob('*/manifest.json'),key=lambda p:p.stat().st_mtime,reverse=True)
                self.project=self.store.load(candidates[0].parent.name) if candidates else None
            if self.project:
                self._restore_project_status()
                self._project_state()
        except (ValueError,OSError,KeyError,TypeError,AttributeError):
            self.project=None
            self._session_recovery=True
            self._update(error='A sessao salva nao pode ser restaurada. O arquivo original foi preservado; consulte os projetos existentes.')
            if self.store:
                try:
                    candidates=sorted((self.store.root/'projects').glob('*/manifest.json'),key=lambda p:p.stat().st_mtime,reverse=True)
                except OSError:
                    return
                for candidate in candidates:
                    try:
                        self.project=self.store.load(candidate.parent.name)
                        recovery_error=self.snapshot()['error']
                        self._restore_project_status()
                        if not self.snapshot()['error']:
                            self._update(error=recovery_error)
                        self._project_state(persist=False)
                        break
                    except (ValueError,OSError,KeyError,TypeError,AttributeError):
                        self.project=None

    def _update(self, **values):
        with self.gate:
            self.state.update(copy.deepcopy(values))
            self.state['serial'] += 1

    def _activity(self, title, detail='', status='running', identifier=None):
        record = {'id': identifier or str(time.monotonic_ns()), 'title': public_text(title),
                  'detail': public_text(detail), 'status': status}
        with self.gate:
            self.state['activities'].append(record)
            self.state['activities'] = self.state['activities'][-100:]
            self.events.append(copy.deepcopy(record))
            self.state['serial'] += 1

    def snapshot(self):
        with self.gate:
            result = copy.deepcopy(self.state)
            result['connected'] = result['authenticated'] and result['transport'] == 'ready'
            return result

    def status(self):
        return self.snapshot()

    def drain_events(self):
        with self.gate:
            result = list(self.events)
            self.events.clear()
            return copy.deepcopy(result)

    def _call(self, coroutine):
        return self._wait(self._submit(coroutine))

    def _submit(self, coroutine):
        with self.gate:
            if self.closed:
                coroutine.close()
                raise RuntimeError('FORJA runtime is closed')
            if threading.current_thread() is self.thread:
                coroutine.close()
                raise RuntimeError('Do not call synchronous facade from FORJA worker')
            future = asyncio.run_coroutine_threadsafe(coroutine, self.loop)
        return future

    def _wait(self, future):
        try:
            return future.result(timeout=self.timeout * 5 + 5)
        except concurrent.futures.TimeoutError:
            future.cancel()
            raise TimeoutError('FORJA host operation timed out; inspect status before retrying')

    def connect(self, auth_mode=None, key='', model='', **aliases):
        auth_mode = aliases.pop('mode', auth_mode)
        key = aliases.pop('api_key', key)
        if aliases:
            raise ValueError('Unknown connection option')
        return self._call(self._connect(auth_mode, key, model))

    async def _ensure(self):
        if self.client and self.snapshot()['transport'] == 'stopped':
            await self.client.close()
            self.client = None
        if self.client:
            return
        self.store = self.store or ProjectStore(self.root, self.export_roots)
        home = check_chain(self.root / 'codex-home')
        home.mkdir(exist_ok=True)
        # Official credential manager is the sole owner; never create auth.json copies.
        self.client = self.factory(self.executable, home, self._event, self.timeout)
        self._update(connection='connecting')
        try:
            initialized = await self.client.start()
            self._update(transport='ready', server=initialized,
                         process_security=getattr(self.client.process, 'security', None)
                         if isinstance(self.client, AppServer) else None)
            if os.name == 'nt':
                result = await self.client.request('windowsSandbox/readiness', {})
                sandbox = self.snapshot()['sandbox']
                sandbox['readiness'] = result['status']
                self._update(sandbox=sandbox)
            await self._account()
            if self.project:
                try:
                    if self.project.get('thread_id') and self.snapshot()['authenticated']:await self._resume()
                    await self._prepare_preview()
                except (OSError,RuntimeError,ValueError,KeyError) as error:
                    self._update(project_error='Nao consegui retomar o projeto salvo. A conexao continua disponivel; os arquivos foram preservados.')
                    self._activity('Project restoration',type(error).__name__,'failed')
            self._refresh_projects()
        except BaseException:
            await self.client.close()
            self.client = None
            self._update(transport='stopped', connection='unavailable')
            raise

    async def _account(self):
        result = await self.client.request('account/read', {'refreshToken': False})
        account = result.get('account')
        public = ({k: public_text(account[k]) for k in ('type', 'email', 'planType') if k in account}
                  if isinstance(account, dict) else None)
        self._update(account=public, authenticated=bool(account),
                     connection='authenticated' if account else 'auth_required')
        return public

    async def _connect(self, mode, key, model):
        async with self.operation_lock:
            try:
                await self._ensure()
                if self.active_turn and (mode is not None or model):
                    raise ValueError('Cancel the active turn before changing authentication')
                if mode not in (None, 'apiKey', 'chatgpt'):
                    raise ValueError('Authentication mode must be apiKey or chatgpt')
                auth_url = None
                if mode:
                    params = {'type': mode}
                    if mode == 'apiKey':
                        if not isinstance(key, str) or not key.strip():
                            raise ValueError('An API key is required')
                        params['apiKey'] = key
                    if self.login_id:
                        await self.client.request('account/login/cancel', {'loginId': self.login_id})
                        self.login_id = None
                    login = await self.client.request('account/login/start', params)
                    auth_url = login.get('authUrl')
                    self.login_id = login.get('loginId')
                    params.clear()
                    key = ''
                await self._account()
                if model:
                    self._update(model=model)
                if self.snapshot()['authenticated']:
                    models = await self.client.request('model/list', {})
                    self._update(models=[{'id': m.get('id'), 'name': m.get('displayName'),
                                          'description': public_text(m.get('description', ''))}
                                         for m in models.get('data', [])])
                return {'accepted': True, 'auth_url': auth_url, 'login_id': self.login_id,
                        **self.status()}
            except (OSError, RuntimeError, ValueError, asyncio.TimeoutError) as error:
                # A login failure may echo the submitted credential. Do not publish raw auth errors.
                detail = 'Connection/authentication failed: ' + type(error).__name__
                self._update(connection='error', error=detail)
                return {'accepted': False, **self.status()}

    def command(self, action, prompt='', name='', destination='', project_id='', **options):
        epoch=None
        try:
            # Admission and scheduling share the gate; waiting must never hold it.
            with self.gate:
                if action in ('new','create','steer','continue','cancel','save','save_library','export','open','undo','redo'):
                    self._command_epoch+=1;epoch=self._command_epoch
                    self.state.update(command_epoch=epoch,command_pending=True)
                    self.state['serial']+=1
                future=self._submit(self._command(action,prompt,name,destination,project_id,options))
            return self._wait(future)
        except TimeoutError:
            if epoch is not None:
                with self.gate:
                    if epoch==self._command_epoch:
                        self.state.update(phase='error',error='O novo pedido nao confirmou a conclusao no prazo. Preservei o projeto; consulte o estado antes de tentar novamente.')
            raise
        finally:
            if epoch is not None:
                with self.gate:
                    if epoch==self._command_epoch:
                        self.state['command_pending']=False;self.state['serial']+=1

    def display_epoch(self):
        """Fast admission fence, independent of the async operation queue."""
        with self.gate:return self._command_epoch

    async def _command(self, action, prompt, name, destination, project_id, options):
        async with self.operation_lock:
            try:
                aliases = {'new': 'create', 'save_library': 'save_library', 'continue': 'steer'}
                action = aliases.get(action, action)
                if action == 'approve':
                    raise PermissionError('Permission escalation is disabled; no pending approval can be granted')
                if action not in ('create', 'steer', 'cancel', 'save', 'save_library', 'export',
                                  'undo', 'redo', 'list', 'open', 'validate_preview', 'preview_library'):
                    raise ValueError('Unknown FORJA command')
                self.store = self.store or ProjectStore(self.root, self.export_roots)
                if action == 'list':
                    self._refresh_projects()
                    return {'accepted': True, 'projects': self.snapshot()['projects'],
                            'library': self.store.catalog()}
                if action == 'preview_library':
                    record, root = self.store.artifact(options.get('artifact_id'))
                    self.preview = self.preview or PreviewServer()
                    url = self.preview.publish(root, record['files'], record['entrypoint'], category='library')
                    return {'accepted': True, 'preview_url': url, 'artifact': record}
                if action == 'cancel':
                    return await self._cancel()
                if action == 'steer':
                    await self._ensure()
                    self._require_project()
                    if not self.project.get('thread_id'):
                        raise ValueError('Project has no recoverable Codex thread; create a new project')
                    self._require_execution()
                    self._validate_prompt(prompt)
                    turn = self.active_turn
                    if turn:
                        try:
                            accepted = await self.client.request('turn/steer', {
                                'threadId': self.project['thread_id'], 'expectedTurnId': turn,
                                'input': [{'type': 'text', 'text': prompt}]})
                            return {'accepted': True, 'mode': 'steered', 'turn_id': accepted['turnId']}
                        except RpcError as error:
                            # Only explicit inactive/mismatched turn rejection permits a new turn.
                            if not re.search(r'(?i)(no active turn|not active|turn.*(?:completed|finished)|'
                                             r'expected.*turn|turn.*mismatch)', error.message):
                                raise
                            if self.active_turn == turn:
                                self.active_turn = None
                            await self._resume()
                            if self.active_turn:
                                accepted = await self.client.request('turn/steer', {
                                    'threadId': self.project['thread_id'], 'expectedTurnId': self.active_turn,
                                    'input': [{'type': 'text', 'text': prompt}]})
                                return {'accepted': True, 'mode': 'steered', 'turn_id': accepted['turnId']}
                    else:
                        await self._resume()
                    return await self._start_turn(prompt)
                if action=='validate_preview' and self.active_turn:
                    return {'accepted':False,'retryable':True,'error':'Aguarde o trabalho atual antes de conferir a previa.'}
                if self.active_turn:
                    raise ValueError('Cancel or wait for the current turn before this operation')
                if action == 'create':
                    self._validate_prompt(prompt)
                    await self._ensure()
                    self._require_execution()
                    self.project = self.store.create(name or 'Projeto FORJA')
                    self._update(preview_url=None,candidate_preview_url=None,candidate_revision=None,
                                 preview_error=None,preview_validation='none',generation_verified=False,error=None)
                    self._vendor_assets()
                    self._project_state()
                    result = await self.client.request('thread/start', self._thread_params())
                    self.project['thread_id'] = result['thread']['id']
                    self.store.write(self.project)
                    return await self._start_turn(prompt)
                if action == 'open':
                    self.project = self.store.load(project_id)
                    self._restore_project_status()
                    self._project_state()
                    if self.client and self.project['thread_id']:
                        await self._resume()
                    await self._prepare_preview()
                    return {'accepted': True, 'project': self.snapshot()['project']}
                self._require_project()
                if action in ('undo', 'redo'):
                    revision = getattr(self.store, action)(self.project)
                    self._update(preview_url=None)
                    await self._prepare_preview()
                    self._project_state()
                    return {'accepted': True, 'revision': revision['id']}
                if action in ('save', 'save_library', 'export'):
                    revision = self.store.checkpoint(self.project)
                    self._project_state()
                    if action == 'export':
                        return {'accepted': True, **self.store.export(self.project, destination)}
                    if action == 'save_library':
                        return {'accepted': True, 'artifact': self.store.register(self.project, name)}
                    await self._prepare_preview(options.get('entrypoint'))
                    return {'accepted': True, 'revision': revision['id']}
                if action == 'validate_preview':
                    return self._validate_preview({**options,'project_id':project_id})
            except (OSError, RuntimeError, ValueError, StopIteration, KeyError, asyncio.TimeoutError) as error:
                self._update(error=public_error(error), phase='error' if not self.active_turn else 'running')
                self._activity('Operation failed', error, 'failed')
                return {'accepted': False, 'error': public_error(error)}

    def _require_project(self):
        if not self.project:
            raise ValueError('Open or create a project first')

    def _restore_project_status(self):
        project = self.project
        status = project.get('generation_status')
        failed = status in ('failed', 'interrupted') or project.get('state') == 'error'
        verified = status == 'completed' if status else (
            project.get('state') in ('ready', 'completed') or bool(
                project.get('stable_revision') == project.get('revision') and
                project.get('validation') and project.get('state') != 'running'))
        self._update(phase='error' if failed else 'recovering' if status == 'inProgress' else 'idle',
                     generation_verified=bool(verified and not failed),
                     error=(project.get('generation_error') or 'O motor Codex nao concluiu a etapa.') if failed else None,
                     preview_url=None, candidate_preview_url=None, candidate_revision=None,
                     preview_error=None, preview_validation='none', turn_id=None,
                     project_error=None, activities=[])

    def grant_export_root(self, path):
        """Trusted host only: call after the user chooses an existing export folder."""
        return self._call(self._grant_export_root(path))

    async def _grant_export_root(self, path):
        async with self.operation_lock:
            root = Path(path)
            if not root.is_absolute():
                raise ValueError('Export root must be absolute')
            root = check_chain(root)
            if not root.is_dir() or root == Path(root.anchor):
                raise ValueError('Choose an existing non-root export directory')
            if root.is_relative_to(self.root) or self.root.is_relative_to(root):
                raise ValueError('Cannot grant FORJA private data as an export root')
            for variable in ('SystemRoot', 'ProgramFiles', 'ProgramFiles(x86)'):
                if os.environ.get(variable) and root.is_relative_to(Path(os.environ[variable])):
                    raise ValueError('Cannot export generated code to a protected system directory')
            self.store = self.store or ProjectStore(self.root, self.export_roots)
            if root not in self.store.export_roots:
                self.store.export_roots += (root,)
            return {'accepted': True, 'export_root': str(root)}

    def _vendor_assets(self):
        vendor = Path(__file__).resolve().parents[1] / 'spatial/vendor/package/build'
        workspace = self.store.workspace(self.project)
        files = {}
        for name in ('three.module.js', 'three.core.js'):
            if (vendor / name).is_file():
                files['vendor/' + name] = read_file(vendor, name)
        if len(files) == 2:
            self.store._write_files(workspace, files)
            self.store.checkpoint(self.project)
            self._activity('Local Three.js assets prepared', 'vendor/three.module.js, vendor/three.core.js', 'completed')
        else:
            self._activity('Local Three.js unavailable', 'No host private files were copied', 'failed')

    def _require_execution(self):
        if not self.snapshot()['authenticated']:
            raise ValueError('Codex authentication is required')
        if os.name == 'nt' and self.snapshot()['sandbox']['readiness'] != 'ready':
            raise PermissionError('Windows sandbox is not ready; configure it through official Codex setup')

    @staticmethod
    def _validate_prompt(prompt):
        if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 32000:
            raise ValueError('A nonempty prompt up to 32000 characters is required')

    def _thread_params(self):
        params = {'cwd': str(self.store.workspace(self.project)), 'sandbox': 'workspace-write',
                  'approvalPolicy': 'never', 'developerInstructions': INSTRUCTIONS,
                  'config': {'shell_environment_policy.inherit': 'none'}}
        if self.snapshot()['model']:
            params['model'] = self.snapshot()['model']
        return params

    async def _resume(self):
        params = self._thread_params()
        params['threadId'] = self.project['thread_id']
        result = await self.client.request('thread/resume', params)
        for turn in result.get('thread', {}).get('turns', []):
            if turn.get('status') == 'inProgress':
                self.active_turn = turn['id']
                self._update(phase='running', generation_verified=False, error=None, turn_id=turn['id'])
                self._arm_watchdog(turn['id'])

    async def _start_turn(self, prompt):
        params = {'threadId': self.project['thread_id'], 'input': [{'type': 'text', 'text': prompt}],
                  'cwd': str(self.store.workspace(self.project)), 'approvalPolicy': 'never',
                  'sandboxPolicy': {'type': 'workspaceWrite',
                                    'writableRoots': [str(self.store.workspace(self.project))],
                                    'networkAccess': False, 'excludeTmpdirEnvVar': True,
                                    'excludeSlashTmp': True}}
        result = await self.client.request('turn/start', params)
        turn = result['turn']['id']
        # Completion may arrive before the request response; never resurrect that turn.
        if turn not in self.finished_turns:
            self.active_turn = turn
            self.project['state'] = 'running'
            self.project['generation_status'] = 'inProgress'
            self.project['generation_error'] = None
            self.store.write(self.project)
            self._update(phase='running', error=None,turn_id=turn,generation_verified=False,
                         preview_error=None,preview_validation='none',candidate_preview_url=None)
            self._arm_watchdog(turn)
        return {'accepted': True, 'mode': 'started', 'turn_id': turn,
                'project_id': self.project['id']}

    def _arm_watchdog(self, turn):
        if self.watchdog:
            self.watchdog.cancel()
        self.watchdog = asyncio.create_task(self._turn_limit(turn))

    async def _turn_limit(self, turn):
        await asyncio.sleep(self.turn_timeout)
        async with self.operation_lock:
            if self.active_turn == turn:
                self._activity('Time limit reached', 'Requesting interruption', 'running')
                await self._cancel()

    async def _cancel(self):
        if not self.active_turn or not self.client:
            return {'accepted': True, 'mode': 'idle'}
        turn = self.active_turn
        await self.client.request('turn/interrupt', {'threadId': self.project['thread_id'], 'turnId': turn})
        self._activity('Cancellation requested', 'Waiting for interrupted completion')
        self._job(self._cancel_deadline(turn))
        return {'accepted': True, 'mode': 'cancelling', 'turn_id': turn}

    async def _cancel_deadline(self, turn):
        await asyncio.sleep(min(self.timeout, 10))
        if self.active_turn == turn and self.client:
            await self.client.close()
            self.client = None
            self.active_turn = None
            self._update(phase='error', transport='stopped', connection='unavailable',
                         error='Interrupt was not confirmed; owned App Server terminated')

    def _event(self, method, params):
        if method == 'forge/disconnected':
            self.active_turn = None
            self._update(phase='error', transport='stopped', connection='unavailable', authenticated=False,
                         error=params.get('message'))
            return
        if method == 'account/login/completed':
            if params.get('loginId') == self.login_id and params.get('success'):
                self._job(self._account())
            elif params.get('loginId') == self.login_id:
                self._update(connection='auth_required', error=public_text(params.get('error', 'Login failed')))
            return
        if method == 'account/updated':
            self._job(self._account())
            return
        if method == 'forge/requestDenied':
            self._activity('Permission request denied', params.get('method'), 'failed')
            return
        if not self.project or params.get('threadId') != self.project['thread_id']:
            return
        if method == 'error':
            error=params.get('error') or {}
            self._update(error=public_error(error.get('message','Falha no motor Codex.') if isinstance(error,dict) else error))
        elif method == 'turn/completed':
            turn = params.get('turn', {})
            identifier = turn.get('id')
            if not identifier or identifier in self.finished_turns:
                return
            self.finished_turns.append(identifier)
            if self.active_turn == identifier:
                self.active_turn = None
                if self.watchdog:
                    self.watchdog.cancel()
            self._job(self._complete(self.project['id'], turn))
        elif method in ('item/started', 'item/completed'):
            item = params.get('item', {})
            kind = item.get('type')
            if kind in ('reasoning', 'userMessage'):
                return
            if kind == 'agentMessage':
                detail = item.get('text', '')
                title = 'Agent message'
            elif kind == 'commandExecution':
                title = 'Command execution'
                detail = str(item.get('command', '')) + ' | exit=' + str(item.get('exitCode'))
            elif kind == 'fileChange':
                title = 'File changes'
                detail = ', '.join(str(c.get('path', '')) for c in item.get('changes', []))
            else:
                title, detail = kind or 'Item', ''
            self._activity(title, detail, item.get('status', 'completed' if method.endswith('completed') else 'running'),
                           item.get('id'))
        elif method == 'item/agentMessage/delta':
            self._activity('Agent message', params.get('delta', ''), 'streaming', params.get('itemId'))

    async def _complete(self, project_id, turn):
        async with self.operation_lock:
            try:
                if self.project and self.project['id'] == project_id and self.active_turn:
                    self._activity('Previous turn completed', turn.get('status'), turn.get('status', 'failed'))
                    return
                project = self.store.load(project_id)
                self.store.checkpoint(project)
                project['state'] = 'idle' if turn.get('status') == 'completed' else 'error'
                project['generation_status'] = turn.get('status')
                project['generation_error'] = None if turn.get('status') == 'completed' else public_error(
                    (turn.get('error') or {}).get('message') or self.snapshot().get('error') or
                    ('Trabalho cancelado.' if turn.get('status') == 'interrupted' else 'O motor Codex nao concluiu a etapa.'))
                self.store.write(project)
                if not self.project or self.project['id'] != project_id:
                    return
                self.project = project
                if self.active_turn:
                    self._project_state()
                    return
                self._update(phase='idle' if turn.get('status') == 'completed' else 'error',
                             generation_verified=turn.get('status') == 'completed',
                             error=project['generation_error'])
                self._activity('Turn completed', turn.get('status'), turn.get('status', 'failed'))
                await self._prepare_preview()
                self._project_state()
            except (ValueError, OSError, KeyError) as error:
                self._update(phase='error', error=public_text(error))

    async def _prepare_preview(self, entrypoint=None):
        revision = self.project['revision']
        files = self.store.verified_revision(self.project, revision)
        stable=self.project.get('stable_revision')
        if stable and stable!=revision and not self.snapshot()['preview_url']:
            previous=self.store.verified_revision(self.project,stable)
            previous_entry=self.project.get('stable_entrypoint') or self.project.get('entrypoint')
            if previous_entry not in previous:previous_entry='index.html' if 'index.html' in previous else next((name for name in previous if name.endswith('.html')),None)
            if previous_entry:
                self.preview=self.preview or PreviewServer()
                stable_url=self.preview.publish(self.store.revision_path(self.project,stable),hashes(previous),previous_entry)
                self._update(preview_url=stable_url)
        entrypoint = entrypoint or self.project.get('entrypoint') or ('index.html' if 'index.html' in files else None)
        if not entrypoint:
            self._update(candidate_preview_url=None,preview_validation='none')
            return
        relative(entrypoint)
        if entrypoint not in files or not entrypoint.endswith('.html'):
            raise ValueError('Preview entrypoint is missing')
        self.preview = self.preview or PreviewServer()
        url = self.preview.publish(self.store.revision_path(self.project, revision), hashes(files), entrypoint,
                                   keep_url=self.snapshot()['preview_url'])
        self.project['entrypoint'] = entrypoint
        self.store.write(self.project)
        # A file-integrity check is not a render test. Keep the last stable URL until host attests rendering.
        self._update(candidate_preview_url=url, candidate_revision=revision,preview_validation='pending',preview_error=None,
                     project={key:self.project.get(key) for key in
                              ('id','name','revision','thread_id','state','entrypoint','validation')})
        if self.project['stable_revision'] == revision:
            unresolved = self.project.get('generation_status') == 'inProgress' and not self.active_turn
            phase = ('running' if self.active_turn else 'error' if self.project['state'] == 'error'
                     else 'recovering' if unresolved else 'ready')
            self._update(preview_url=url, phase=phase,preview_validation='passed')

    def _validate_preview(self, options):
        expected=(self.project['id'],self.project['revision'],self.snapshot()['candidate_preview_url'])
        supplied=(options.get('project_id'),options.get('revision'),options.get('candidate_url'))
        if supplied!=expected:
            return {'accepted':False,'stale':True,'error':'Verificacao de uma previa antiga ignorada. O projeto atual foi mantido.'}
        evidence = options.get('evidence', {})
        unresolved = self.project.get('generation_status') == 'inProgress' and not self.active_turn
        required = ('syntax', 'assets', 'initialized', 'nonblank', 'framing')
        if not all(evidence.get(k) is True for k in required) or evidence.get('console_errors') != []:
            labels={'syntax':'codigo','assets':'arquivos e recursos','initialized':'inicializacao',
                    'nonblank':'conteudo visivel','framing':'enquadramento'}
            failed=[label for key,label in labels.items() if evidence.get(key) is not True]
            if evidence.get('console_errors')!=[]:failed.append('erros de renderizacao')
            message='A previa precisa de correcao em: '+', '.join(failed)+'. O projeto foi preservado; nao reiniciei a criacao.'
            phase = ('error' if self.project['state'] == 'error' else 'recovering' if unresolved
                     else 'ready' if self.snapshot()['preview_url'] else 'idle')
            self._update(preview_error=message,preview_validation='failed',phase=phase)
            self._activity('Preview validation',message,'failed')
            return {'accepted':False,'validation_failed':True,'error':message}
        if not self.snapshot()['candidate_preview_url']:
            raise ValueError('No preview candidate')
        self.store.verified_revision(self.project, self.project['revision'])
        self.project['stable_revision'] = self.project['revision']
        self.project['stable_entrypoint']=self.project['entrypoint']
        self.project['validation'] = {k: evidence[k] for k in (*required, 'console_errors')}
        generation_failed = self.project['state'] == 'error'
        if not generation_failed and not unresolved:
            self.project['state'] = 'ready'
        self.store.write(self.project)
        self._update(preview_url=self.snapshot()['candidate_preview_url'],
                     phase='error' if generation_failed else 'recovering' if unresolved else 'ready',preview_validation='passed',preview_error=None,
                     error=self.snapshot()['error'] if generation_failed else None)
        self._project_state()
        return {'accepted': True, 'preview_url': self.snapshot()['preview_url']}

    def _project_state(self, persist=True):
        if persist:
            session=check_chain(self.root/'session.json')
            if self._session_recovery and session.exists():
                backup=check_chain(self.root/('session.recovery-'+str(time.time_ns())+'.json'))
                atomic_write(backup,read_file(self.root,'session.json'))
            atomic_write(session,json.dumps({'project_id':self.project['id']}).encode())
            self._session_recovery=False
        self._update(project={k: self.project.get(k) for k in
                              ('id', 'name', 'revision', 'thread_id', 'state', 'entrypoint', 'validation')})
        self._refresh_projects()

    def _refresh_projects(self):
        projects = []
        with self.gate:
            for base in (self.store.root / 'projects').iterdir():
                try:
                    manifest = self.store.load(base.name)
                    projects.append({k: manifest.get(k) for k in ('id', 'name', 'revision', 'state')})
                except (ValueError, OSError, KeyError, TypeError, AttributeError):
                    continue
        self._update(projects=projects)

    def _job(self, coroutine):
        task = asyncio.create_task(coroutine)
        self.jobs.add(task)
        def finished(job):
            self.jobs.discard(job)
            if not job.cancelled() and job.exception():
                self._update(phase='error', error='Background operation failed: ' + type(job.exception()).__name__)
        task.add_done_callback(finished)

    async def _shutdown(self):
        # Closing the screen alone must not call this. close() ends the owned process.
        if self.client:
            if self.active_turn and self.project:
                try:
                    await asyncio.wait_for(self._cancel(), min(self.timeout, 3))
                except (OSError, RuntimeError, asyncio.TimeoutError):
                    pass
            await self.client.close()
        for task in list(self.jobs):
            if not task.done():
                task.cancel()
        if self.jobs:
            await asyncio.gather(*self.jobs, return_exceptions=True)
        if self.watchdog:
            self.watchdog.cancel()
        if self.project and self.store:
            try:
                self.store.checkpoint(self.project)
                if self.project['state'] != 'error':
                    self.project['state'] = 'idle'
                self.store.write(self.project)
            except (ValueError, OSError):
                pass
        if self.preview:
            self.preview.close()
        self._update(transport='stopped', connection='closed', phase='idle')

    def close(self):
        with self.gate:
            if self.closed:
                return
            self.closed = True
        future = asyncio.run_coroutine_threadsafe(self._shutdown(), self.loop)
        try:
            future.result(timeout=self.timeout + 10)
        finally:
            self.loop.call_soon_threadsafe(self.loop.stop)
            self.thread.join(timeout=5)
        if self.thread.is_alive():
            raise RuntimeError('FORJA worker shutdown timed out')


Runtime = ForgeRuntime
