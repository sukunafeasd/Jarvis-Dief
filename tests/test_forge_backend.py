"""FORJA tests use no model calls or real account credentials."""
import asyncio
import json
import os
from pathlib import Path
import sys
import subprocess
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.forge import Runtime
from core.forge.files import ProjectStore, hashes, inventory, pinned, relative
from core.forge.preview import PreviewServer
from core.forge.transport import AppServer, RpcError, isolated_environment


EVIDENCE = {'syntax': True, 'assets': True, 'initialized': True, 'nonblank': True,
            'framing': True, 'console_errors': []}


class FakeServer:
    instances = []

    def __init__(self, executable, home, on_event, timeout):
        self.home = home
        self.event = on_event
        self.calls = []
        self.account = None
        self.race = False
        self.complete_early = False
        self.closed = False
        self.counter = 0
        self.cwd = None
        self.thread_id = 'thread-project'
        self.active = None
        self.instances.append(self)

    async def start(self):
        return {'userAgent': 'mock/verified-schema'}

    async def request(self, method, params):
        self.calls.append((method, dict(params)))
        if method == 'windowsSandbox/readiness':
            return {'status': 'ready'}
        if method == 'account/read':
            return {'account': self.account}
        if method == 'model/list':
            return {'data': [{'id': 'available-model', 'displayName': 'Available'}]}
        if method == 'account/login/start':
            if params['type'] == 'chatgpt':
                return {'type': 'chatgpt', 'loginId': 'login-test', 'authUrl': 'https://auth.openai.com/test'}
            self.account = {'type': 'apiKey'}
            return {'type': 'apiKey'}
        if method in ('thread/start', 'thread/resume'):
            self.cwd = Path(params['cwd'])
            return {'thread': {'id': self.thread_id, 'turns': []}}
        if method == 'turn/start':
            self.counter += 1
            self.active = 'turn-' + str(self.counter)
            turn = self.active
            if self.complete_early:
                self.finish()
            return {'turn': {'id': turn, 'status': 'inProgress'}}
        if method == 'turn/steer':
            if self.race:
                self.finish()
                raise RpcError({'code': -32600, 'message': 'No active turn'})
            return {'turnId': self.active}
        if method == 'turn/interrupt':
            self.finish('interrupted')
            return {}
        if method == 'account/login/cancel':
            return {}
        raise AssertionError(method)

    def finish(self, status='completed'):
        turn = self.active
        self.active = None
        self.event('turn/completed', {'threadId': self.thread_id, 'turn': {'id': turn, 'status': status}})

    async def close(self):
        self.closed = True


class BackendTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(prefix='forge-test-')
        self.root = Path(self.folder.name)
        self.exports = self.root / 'exports'
        self.exports.mkdir()
        self.runtime = Runtime(data_root=self.root / 'data', export_roots=[self.exports],
                               transport_factory=FakeServer, request_timeout=1, turn_timeout=3)

    def tearDown(self):
        self.runtime.close()
        self.folder.cleanup()

    def create(self):
        self.assertTrue(self.runtime.connect('apiKey', key='test-protected-key')['accepted'])
        result = self.runtime.command('create', prompt='Build a local page', name='Planet')
        self.assertTrue(result['accepted'], result)
        return FakeServer.instances[-1]

    def complete(self, fake, content=b'<!doctype html><title>Planet</title>'):
        (fake.cwd / 'index.html').write_bytes(content)
        self.runtime.loop.call_soon_threadsafe(fake.finish)
        deadline = time.monotonic() + 3
        while not self.runtime.snapshot()['candidate_preview_url'] and time.monotonic() < deadline:
            time.sleep(.01)
        self.assertIsNotNone(self.runtime.snapshot()['candidate_preview_url'])

    def validate(self):
        state = self.runtime.snapshot()
        result = self.runtime.command('validate_preview', project_id=state['project']['id'],revision=state['project']['revision'],candidate_url=state['candidate_preview_url'],evidence=EVIDENCE)
        self.assertTrue(result['accepted'], result)

    def test_contract_status_detached_and_no_qt(self):
        state = self.runtime.status()
        state['activities'].append('mutated')
        self.assertEqual(self.runtime.snapshot()['activities'], [])
        self.assertEqual(self.runtime.status()['phase'], 'idle')
        self.assertEqual(self.runtime.status()['request'], None)

    def test_failed_turn_preserves_actionable_quota_error(self):
        fake=self.create()
        self.runtime.loop.call_soon_threadsafe(fake.event,'turn/completed',{
            'threadId':fake.thread_id,'turn':{'id':'turn-1','status':'failed',
            'error':{'message':"You've hit your usage limit."}}})
        deadline=time.monotonic()+3
        while self.runtime.snapshot()['phase']=='running' and time.monotonic()<deadline:time.sleep(.01)
        state=self.runtime.snapshot()
        self.assertEqual(state['phase'],'error')
        self.assertIn('limite de uso',state['error'])
        self.assertTrue(state['authenticated'])
        self.assertFalse(state['generation_verified'])

    def test_no_auth_handshake_is_not_verified_generation(self):
        state = self.runtime.connect()
        self.assertTrue(state['accepted'])
        self.assertEqual(state['connection'], 'auth_required')
        self.assertFalse(state['generation_verified'])
        self.assertFalse(self.runtime.command('create', prompt='Build')['accepted'])

    def test_login_url_not_persisted_as_token(self):
        result = self.runtime.connect('chatgpt')
        self.assertEqual(result['auth_url'], 'https://auth.openai.com/test')
        self.assertFalse(result['authenticated'])
        self.assertFalse(any(p.name == 'auth.json' for p in self.root.rglob('*')))

    def test_turn_returns_before_completion_and_same_project_steer(self):
        fake = self.create()
        state = self.runtime.snapshot()
        self.assertEqual(state['phase'], 'running')
        result = self.runtime.command('steer', prompt='Reduce rings')
        self.assertEqual(result['mode'], 'steered')
        self.assertEqual(self.runtime.snapshot()['project']['id'], state['project']['id'])
        params = next(p for m, p in fake.calls if m == 'turn/steer')
        self.assertEqual(params['expectedTurnId'], 'turn-1')

    def test_steer_completion_race_starts_once_on_same_thread(self):
        fake = self.create()
        project = self.runtime.snapshot()['project']['id']
        fake.race = True
        result = self.runtime.command('steer', prompt='Reduce rings')
        self.assertEqual(result['mode'], 'started')
        self.assertEqual(result['project_id'], project)
        starts = [p for m, p in fake.calls if m == 'turn/start']
        self.assertEqual(len(starts), 2)
        self.assertEqual(starts[0]['threadId'], starts[1]['threadId'])
        self.assertEqual(starts[1]['input'][0]['text'], 'Reduce rings')

    def test_ambiguous_steer_timeout_does_not_duplicate(self):
        fake = self.create()
        original = fake.request
        async def request(method, params):
            if method == 'turn/steer':
                raise TimeoutError('ambiguous delivery')
            return await original(method, params)
        fake.request = request
        self.assertFalse(self.runtime.command('steer', prompt='Change')['accepted'])
        self.assertEqual(len([m for m, _ in fake.calls if m == 'turn/start']), 1)

    def test_completed_before_start_response_not_resurrected(self):
        self.runtime.connect('apiKey', key='test')
        fake = FakeServer.instances[-1]
        fake.complete_early = True
        result = self.runtime.command('create', prompt='Build')
        self.assertTrue(result['accepted'])
        self.runtime.command('list')
        self.assertNotEqual(self.runtime.snapshot()['phase'], 'running')

    def test_cancel_confirmation_and_close(self):
        fake = self.create()
        self.assertEqual(self.runtime.command('cancel')['mode'], 'cancelling')
        self.runtime.command('list')
        self.assertEqual(self.runtime.snapshot()['phase'], 'error')
        self.runtime.close()
        self.assertTrue(fake.closed)
        self.assertFalse(self.runtime.thread.is_alive())
        self.runtime.close()

    def test_windows_sandbox_gate_and_policy(self):
        fake = self.create()
        params = next(p for m, p in fake.calls if m == 'turn/start')
        self.assertEqual(params['approvalPolicy'], 'never')
        self.assertFalse(params['sandboxPolicy']['networkAccess'])
        self.assertEqual(params['sandboxPolicy']['writableRoots'], [str(fake.cwd)])

    def test_unready_windows_sandbox_refuses_turn(self):
        self.runtime.connect('apiKey', key='test')
        self.runtime._update(sandbox={'readiness': 'notConfigured'})
        with patch('core.forge.runtime.os.name', 'nt'):
            self.assertFalse(self.runtime.command('create', prompt='Build')['accepted'])
        fake = FakeServer.instances[-1]
        self.assertFalse(any(m == 'turn/start' for m, _ in fake.calls))

    def test_turn_watchdog_requests_actual_interruption(self):
        self.runtime.turn_timeout = .03
        fake = self.create()
        deadline = time.monotonic() + 2
        while self.runtime.snapshot()['phase'] == 'running' and time.monotonic() < deadline:
            time.sleep(.01)
        self.assertTrue(any(m == 'turn/interrupt' for m, _ in fake.calls))
        self.assertEqual(self.runtime.snapshot()['phase'], 'error')

    def test_unconfirmed_cancel_terminates_owned_server(self):
        fake = self.create()
        original = fake.request
        async def request(method, params):
            if method == 'turn/interrupt':
                return {}
            return await original(method, params)
        fake.request = request
        self.runtime.command('cancel')
        deadline = time.monotonic() + 3
        while not fake.closed and time.monotonic() < deadline:
            time.sleep(.01)
        self.assertTrue(fake.closed)
        self.assertEqual(self.runtime.snapshot()['transport'], 'stopped')

    def test_auth_error_cannot_echo_submitted_key(self):
        self.runtime.connect()
        fake = FakeServer.instances[-1]
        original = fake.request
        async def request(method, params):
            if method == 'account/login/start':
                raise RpcError({'message': params['apiKey']})
            return await original(method, params)
        fake.request = request
        result = self.runtime.connect('apiKey', key='sensitive-literal')
        self.assertFalse(result['accepted'])
        self.assertNotIn('sensitive-literal', json.dumps(result))
        self.assertNotIn('sensitive-literal', json.dumps(self.runtime.snapshot()))

    def test_save_library_requires_actual_renderer_evidence(self):
        fake = self.create()
        self.complete(fake)
        self.assertIsNone(self.runtime.snapshot()['preview_url'])
        self.assertFalse(self.runtime.command('save_library', name='Planet')['accepted'])
        self.validate()
        result = self.runtime.command('save_library', name='Planet')
        self.assertTrue(result['accepted'], result)
        artifacts = self.runtime.command('list')['library']
        self.assertEqual(artifacts[0]['name'], 'Planet')
        path = self.root / 'data/library' / result['artifact']['id'] / 'files/index.html'
        self.assertTrue(path.is_file())

    def test_stale_validation_rejected_and_stable_preview_survives_candidates(self):
        fake = self.create()
        self.complete(fake)
        self.validate()
        stable = self.runtime.snapshot()['preview_url']
        old = self.runtime.snapshot()['project']['revision']
        for index in range(3):
            (fake.cwd / 'index.html').write_text('<title>Revision %s</title>' % index)
            self.assertTrue(self.runtime.command('save')['accepted'])
        self.assertFalse(self.runtime.command('validate_preview', revision=old, evidence=EVIDENCE)['accepted'])
        with urlopen(stable, timeout=2) as response:
            self.assertIn(b'Planet', response.read())

    def test_failed_preview_does_not_restart_completed_generation(self):
        fake=self.create();self.complete(fake)
        state=self.runtime.snapshot()
        result=self.runtime.command('validate_preview',project_id=state['project']['id'],revision=state['project']['revision'],candidate_url=state['candidate_preview_url'],evidence={**EVIDENCE,'nonblank':False})
        self.assertFalse(result['accepted'])
        state=self.runtime.snapshot()
        self.assertEqual(state['phase'],'idle')
        self.assertTrue(state['generation_verified'])
        self.assertEqual(state['preview_validation'],'failed')
        self.assertIn('conteudo visivel',state['preview_error'])
        self.assertEqual(len([m for m,p in fake.calls if m=='turn/start']),1)

    def test_relaunch_restores_last_project_without_creating_another(self):
        fake=self.create();self.complete(fake)
        identifier=self.runtime.snapshot()['project']['id']
        self.runtime.close()
        self.runtime=Runtime(data_root=self.root/'data',transport_factory=FakeServer,request_timeout=1)
        self.assertEqual(self.runtime.snapshot()['project']['id'],identifier)
        self.assertEqual(len(list((self.root/'data/projects').iterdir())),1)

    def test_other_entrypoint_same_revision_cannot_use_old_validation(self):
        fake=self.create();(fake.cwd/'other.html').write_text('<title>Other</title>')
        self.complete(fake);old=self.runtime.snapshot()
        self.runtime.command('save',entrypoint='other.html')
        current=self.runtime.snapshot()
        self.assertEqual(old['candidate_revision'],current['candidate_revision'])
        self.assertNotEqual(old['candidate_preview_url'],current['candidate_preview_url'])
        result=self.runtime.command('validate_preview',project_id=old['project']['id'],revision=old['candidate_revision'],candidate_url=old['candidate_preview_url'],evidence=EVIDENCE)
        self.assertTrue(result['stale']);self.assertIsNone(self.runtime.snapshot()['preview_url'])
        self.validate()

    def test_new_project_clears_previous_preview(self):
        fake=self.create();self.complete(fake);self.validate()
        self.assertTrue(self.runtime.snapshot()['preview_url'])
        self.assertTrue(self.runtime.command('create',prompt='Another project')['accepted'])
        self.assertIsNone(self.runtime.snapshot()['preview_url'])

    def test_relaunch_retains_last_stable_preview_with_invalid_candidate(self):
        fake=self.create();self.complete(fake);self.validate()
        identifier=self.runtime.snapshot()['project']['id']
        (fake.cwd/'index.html').write_text('<title>Not validated</title>')
        self.runtime.command('save');self.runtime.close()
        self.runtime=Runtime(data_root=self.root/'data',transport_factory=FakeServer,request_timeout=1)
        self.runtime.command('open',project_id=identifier)
        state=self.runtime.snapshot()
        self.assertIsNotNone(state['preview_url']);self.assertIsNotNone(state['candidate_preview_url'])
        with urlopen(state['preview_url']) as response:self.assertIn(b'Planet',response.read())

    def test_active_turn_validation_is_retryable_without_poisoning_state(self):
        fake=self.create();self.complete(fake);self.validate()
        self.runtime.command('steer',prompt='Adjust')
        result=self.runtime.command('validate_preview',revision=self.runtime.snapshot()['project']['revision'],evidence=EVIDENCE)
        self.assertTrue(result['retryable']);self.assertEqual(self.runtime.snapshot()['phase'],'running')
        self.runtime.loop.call_soon_threadsafe(fake.finish)

    def test_old_thread_restore_failure_keeps_account_connection(self):
        self.create();self.runtime.command('cancel');self.runtime.close()
        class BrokenThread(FakeServer):
            def __init__(self,*args):
                super().__init__(*args);self.account={'type':'apiKey'}
            async def request(self,method,params):
                if method=='thread/resume':raise RpcError({'code':-1,'message':'old thread unavailable'})
                return await super().request(method,params)
        self.runtime=Runtime(data_root=self.root/'data',transport_factory=BrokenThread,request_timeout=1)
        state=self.runtime.connect()
        self.assertTrue(state['connected']);self.assertEqual(state['transport'],'ready')
        self.assertTrue(state['project_error'])

    def test_stable_preview_does_not_hide_resumed_active_turn(self):
        fake=self.create();self.complete(fake);self.validate();self.runtime.close()
        class ActiveThread(FakeServer):
            def __init__(self,*args):
                super().__init__(*args);self.account={'type':'apiKey'}
            async def request(self,method,params):
                if method=='thread/resume':return {'thread':{'turns':[{'id':'resumed-turn','status':'inProgress'}]}}
                return await super().request(method,params)
        self.runtime=Runtime(data_root=self.root/'data',transport_factory=ActiveThread,request_timeout=1)
        state=self.runtime.connect()
        self.assertEqual(state['phase'],'running');self.assertTrue(state['preview_url'])

    def test_restart_open_preserves_thread_files_revisions(self):
        fake = self.create()
        self.complete(fake)
        self.validate()
        project_id = self.runtime.snapshot()['project']['id']
        self.runtime.close()
        self.runtime = Runtime(data_root=self.root / 'data', transport_factory=FakeServer)
        self.assertTrue(self.runtime.command('open', project_id=project_id)['accepted'])
        self.assertEqual(self.runtime.snapshot()['project']['thread_id'], fake.thread_id)
        self.assertEqual(self.runtime.snapshot()['phase'], 'ready')
        self.assertTrue(self.runtime.connect('apiKey', key='test')['accepted'])
        self.assertTrue(self.runtime.command('steer', prompt='Continue')['accepted'])

    def test_export_no_overwrite_and_explicit_roots(self):
        fake = self.create()
        self.complete(fake)
        destination = self.exports / 'Planet'
        result = self.runtime.command('export', destination=str(destination))
        self.assertTrue(result['accepted'], result)
        self.assertTrue((destination / 'index.html').is_file())
        self.assertFalse(self.runtime.command('export', destination=str(destination))['accepted'])
        self.assertFalse(self.runtime.command('export', destination=str(self.root / 'outside'))['accepted'])
        self.assertFalse(self.runtime.command('export', destination='../escape')['accepted'])

    def test_undo_conflicts_with_manual_edits(self):
        fake = self.create()
        self.complete(fake)
        (fake.cwd / 'index.html').write_text('manual change')
        self.assertFalse(self.runtime.command('undo')['accepted'])
        self.assertEqual((fake.cwd / 'index.html').read_text(), 'manual change')
        self.assertTrue(self.runtime.command('save')['accepted'])
        self.assertTrue(self.runtime.command('undo')['accepted'])
        self.assertIn('Planet', (fake.cwd / 'index.html').read_text())

    def test_events_public_only_and_no_fictitious_progress(self):
        fake = self.create()
        thread_id = fake.thread_id
        async def emit():
            fake.event('item/started', {'threadId': thread_id, 'item': {'type': 'reasoning', 'text': 'private'}})
            fake.event('item/completed', {'threadId': thread_id, 'item': {
                'id': 'cmd', 'type': 'commandExecution', 'command': 'test', 'exitCode': 0}})
            fake.event('item/completed', {'threadId': thread_id, 'item': {
                'id': 'files', 'type': 'fileChange', 'changes': [{'path': 'index.html'}]}})
            fake.event('item/agentMessage/delta', {'threadId': thread_id, 'delta': 'api_key=hidden'})
        asyncio.run_coroutine_threadsafe(emit(), self.runtime.loop).result(2)
        text = json.dumps(self.runtime.snapshot())
        self.assertNotIn('private', text)
        self.assertNotIn('hidden', text)
        self.assertIn('Command execution', text)
        self.assertIn('File changes', text)
        self.assertNotIn('percentage', text)

    def test_approvals_fail_closed(self):
        self.assertFalse(self.runtime.command('approve', request_id='agent-request')['accepted'])


class FilesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='forge-files-')
        self.root = Path(self.temp.name)
        self.store = ProjectStore(self.root / 'data')
        self.project = self.store.create('Page')
        self.workspace = self.store.workspace(self.project)

    def tearDown(self):
        self.temp.cleanup()

    def test_paths(self):
        for name in ('../a', '/a', 'a\\b', 'C:/a', 'a:b', 'con.txt', 'a/./b', 'a//b', 'a.'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                relative(name)

    def test_secrets_and_dependencies_not_packaged(self):
        for name in ('index.html', '.env', 'auth.json', 'api_keys.json', 'secret.txt'):
            (self.workspace / name).write_text('data')
        (self.workspace / 'node_modules').mkdir()
        (self.workspace / 'node_modules/dep.js').write_text('ignored')
        self.assertEqual(set(inventory(self.workspace)), {'index.html'})

    def test_hard_links_rejected(self):
        external = self.root / 'private.txt'
        external.write_text('private')
        os.link(external, self.workspace / 'leak.txt')
        with self.assertRaises(ValueError):
            inventory(self.workspace)

    @unittest.skipUnless(os.name == 'nt', 'Windows junction test')
    def test_junction_rejected_without_admin(self):
        outside = self.root / 'outside'
        outside.mkdir()
        link = self.workspace / 'junction'
        result = subprocess.run(['cmd', '/c', 'mklink', '/J', str(link), str(outside)],
                                capture_output=True, timeout=5, creationflags=0x08000000)
        self.assertEqual(result.returncode, 0)
        try:
            with self.assertRaises(ValueError):
                inventory(self.workspace)
        finally:
            os.rmdir(link)

    @unittest.skipUnless(os.name == 'nt', 'Windows handle pin test')
    def test_pinned_ancestors_block_replacement(self):
        with pinned(self.workspace), self.assertRaises(OSError):
            self.workspace.rename(self.workspace.with_name('substituted'))

    def test_undo_after_branch_uses_parent_revision(self):
        path = self.workspace / 'index.html'
        for value in ('A', 'B', 'C'):
            path.write_text(value)
            self.store.checkpoint(self.project)
        self.store.undo(self.project)
        self.assertEqual(path.read_text(), 'B')
        path.write_text('D')
        self.store.checkpoint(self.project)
        self.store.undo(self.project)
        self.assertEqual(path.read_text(), 'B')

    def test_link_directory_rejected(self):
        external = self.root / 'outside'
        external.mkdir()
        try:
            (self.workspace / 'link').symlink_to(external, target_is_directory=True)
        except OSError:
            self.skipTest('Symlink creation unavailable to this Windows user')
        with self.assertRaises(ValueError):
            inventory(self.workspace)

    def test_revision_tamper_rejected(self):
        (self.workspace / 'index.html').write_text('valid')
        revision = self.store.checkpoint(self.project)
        (self.store.revision_path(self.project, revision['id']) / 'index.html').write_text('tampered')
        with self.assertRaises(ValueError):
            self.store.verified_revision(self.project, revision['id'])

    def test_preview_host_methods_traversal_and_integrity(self):
        (self.workspace / 'index.html').write_text('<title>Preview</title>')
        files = inventory(self.workspace)
        server = PreviewServer()
        try:
            url = server.publish(self.workspace, hashes(files), 'index.html')
            with urlopen(url, timeout=2) as response:
                self.assertIn('sandbox allow-scripts', response.headers['Content-Security-Policy'])
            for request in (Request(url, method='POST'), Request(url, headers={'Host': 'evil.example'}),
                            Request(url.rsplit('/', 1)[0] + '/%2e%2e/private.txt'),
                            Request(url.rsplit('/', 1)[0] + '/C:%5cprivate.txt')):
                with self.assertRaises(HTTPError):
                    urlopen(request, timeout=2)
            (self.workspace / 'index.html').write_text('tampered')
            with self.assertRaises(HTTPError):
                urlopen(url, timeout=2)
        finally:
            server.close()
        self.assertFalse(server.thread.is_alive())


class TransportTests(unittest.IsolatedAsyncioTestCase):
    async def test_jsonrpc_handshake_notifications_requests_and_timeout(self):
        with tempfile.TemporaryDirectory(prefix='forge-rpc-') as folder:
            events = []
            original = asyncio.create_subprocess_exec
            async def spawn(*args, **kwargs):
                return await original(sys.executable, '-u', __file__, '--fake-server', **kwargs)
            async def windows_spawn(argv,cwd,env):
                return await original(sys.executable,'-u',__file__,'--fake-server',cwd=str(cwd),env=env,
                    stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
            server = AppServer(sys.executable, folder, lambda m, p: events.append((m, p)), timeout=3)
            with patch('core.forge.transport.elevated', return_value=False), \
                    patch('core.forge.transport.launch_windows',side_effect=windows_spawn), \
                    patch('core.forge.transport.asyncio.create_subprocess_exec', side_effect=spawn):
                try:
                    self.assertEqual(await server.start(), {'ready': True})
                    result = await server.request('echo', {'value': 'ok'})
                    self.assertEqual(result['value'], 'ok')
                    await server.request('approval', {})
                    self.assertEqual(await server.request('echo', {}), {})
                    self.assertTrue(any(m == 'forge/requestDenied' for m, _ in events))
                    server.timeout = .1
                    with self.assertRaises(asyncio.TimeoutError):
                        await server.request('hang', {})
                    self.assertEqual(server.pending, {})
                    with self.assertRaises(RpcError):
                        await server.request('error', {})
                finally:
                    await server.close()
                self.assertIsNotNone(server.process.returncode)
                self.assertTrue(all(t.done() for t in server.tasks))

    async def test_elevated_host_is_refused(self):
        server = AppServer('unused', Path('.'), lambda *_: None)
        with patch('core.forge.transport.elevated', return_value=True), self.assertRaises(PermissionError):
            await server.start()
        self.assertIsNone(server.process)

    async def test_environment_does_not_copy_keys_or_desktop_tokens(self):
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'private', 'CODEX_HOME': 'desktop',
                                     'CODEX_THREAD_ID': 'desktop-thread', 'PYTHONPATH': 'injection'}):
            env = isolated_environment(Path('/isolated'))
        for name in ('OPENAI_API_KEY', 'CODEX_THREAD_ID', 'PYTHONPATH'):
            self.assertNotIn(name, env)
        self.assertNotEqual(env['CODEX_HOME'], 'desktop')


def fake_stdio_server():
    for line in sys.stdin:
        message = json.loads(line)
        method = message.get('method')
        if 'id' not in message or method == 'hang':
            continue
        if method == 'approval':
            print(json.dumps({'id': 'approval-1', 'method': 'item/commandExecution/requestApproval', 'params': {}}), flush=True)
        if method == 'error':
            result = {'id': message['id'], 'error': {'code': -32600, 'message': 'test error'}}
        elif method:
            result = {'id': message['id'], 'result': {'ready': True} if method == 'initialize' else message.get('params', {})}
        else:
            continue
        print(json.dumps(result), flush=True)


if __name__ == '__main__':
    if '--fake-server' in sys.argv:
        fake_stdio_server()
    else:
        unittest.main()
