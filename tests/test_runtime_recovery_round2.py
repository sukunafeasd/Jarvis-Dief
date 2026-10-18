"""Runtime shutdown/recovery with temporary data and synthetic blocked queries."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch


class IsolatedRuntimeTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory(prefix='dief-runtime-recovery-')
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        environment = patch.dict(os.environ, {
            'QT_QPA_PLATFORM': 'offscreen', 'DIEF_JARVIS_DATA_DIR': folder.name})
        environment.start()
        self.addCleanup(environment.stop)
        processes = patch('subprocess.run', side_effect=AssertionError('Real OS process forbidden'))
        processes.start()
        self.addCleanup(processes.stop)

    def wait_until(self, condition, timeout=2):
        deadline = time.monotonic() + timeout
        while not condition():
            if time.monotonic() >= deadline:
                self.fail('Offline fixture did not reach its barrier')
            time.sleep(.002)


class UltronRecoveryTests(IsolatedRuntimeTests):
    def setUp(self):
        super().setUp()
        from core.ultron import Runtime
        self.runtime = Runtime()
        self.addCleanup(self.runtime.close)
        for name, value in (('telemetry', {'cpu_percent': 7}),
                            ('powershell_summary', None), ('vault_list', [])):
            guard = patch.object(self.runtime._service, name, return_value=value)
            guard.start()
            self.addCleanup(guard.stop)
        admin = patch('core.ultron.ultron_tools.administrator', return_value=False)
        admin.start()
        self.addCleanup(admin.stop)

    def call_thread(self, callback):
        done = threading.Event()
        result = []

        def run():
            try:
                result.append(callback())
            except BaseException as error:
                result.append(error)
            finally:
                done.set()

        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        return thread, done, result

    def assert_shutdown_while_blocked(self, release):
        thread, done, result = self.call_thread(self.runtime.close)
        try:
            self.assertTrue(done.wait(1), 'Shutdown waited for a blocked synchronous query')
            self.assertEqual(result, [None])
            self.assertFalse(self.runtime._thread.is_alive())
            self.assertNotIn(self.runtime._module_name, sys.modules)
        finally:
            release.set()
            thread.join(2)

    def test_close_cancels_scan_without_waiting_for_daemon_query(self):
        entered, release, finished = threading.Event(), threading.Event(), threading.Event()

        def telemetry():
            entered.set()
            try:
                if not release.wait(4):
                    raise TimeoutError('Offline fixture deadline')
                return {'cpu_percent': 99}
            finally:
                finished.set()

        self.runtime._service.telemetry.side_effect = telemetry
        try:
            result = self.runtime.command('ativar protocolo ultron',
                                          'ativar protocolo ultron', user_turn=1)
            self.assertTrue(result['accepted'])
            self.assertTrue(entered.wait(1))
            self.assert_shutdown_while_blocked(release)
            self.assertTrue(self.runtime._service.SCAN_TASK.done())
            self.assertTrue(finished.wait(1))
            self.assertNotEqual(self.runtime._service.STATE['telemetry'], {'cpu_percent': 99})
            self.assertTrue(all(thread.daemon for thread in self.runtime._executor.pool.threads))
            self.assertLessEqual(len(self.runtime._executor.pool.threads), 4)
            self.runtime.close()
            with self.assertRaisesRegex(RuntimeError, 'closed'):
                self.runtime.snapshot()
        finally:
            release.set()

    def test_close_releases_blocked_snapshot_and_queued_host_call(self):
        for provider in ('telemetry', 'vault_list'):
            with self.subTest(provider=provider):
                if self.runtime._closed:
                    from core.ultron import Runtime
                    self.runtime = Runtime()
                    self.addCleanup(self.runtime.close)
                    self.runtime._service.telemetry = Mock(return_value={'cpu_percent': 7})
                    self.runtime._service.vault_list = Mock(return_value=[])
                entered, release = threading.Event(), threading.Event()

                def stalled():
                    entered.set()
                    if not release.wait(4):
                        raise TimeoutError('Offline fixture deadline')
                    return [] if provider == 'vault_list' else {'cpu_percent': 7}

                with patch.object(self.runtime._service, provider, side_effect=stalled):
                    caller, done, result = self.call_thread(self.runtime.snapshot)
                    queued = None
                    try:
                        self.assertTrue(entered.wait(1))
                        queued = self.call_thread(lambda: self.runtime.command('status'))
                        self.wait_until(lambda: len(self.runtime._pending) == 2)
                        self.assert_shutdown_while_blocked(release)
                        self.assertTrue(done.wait(1))
                        self.assertIsInstance(result[0], RuntimeError)
                        self.assertTrue(queued[1].wait(1))
                        self.assertIsInstance(queued[2][0], RuntimeError)
                    finally:
                        release.set()
                        caller.join(2)
                        if queued:
                            queued[0].join(2)

    def test_concurrent_host_calls_stay_serialized(self):
        active, peak, completed = 0, 0, []

        async def operation(number):
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            try:
                await asyncio.sleep(.01)
                completed.append(number)
                return number
            finally:
                active -= 1

        with ThreadPoolExecutor(max_workers=4) as pool:
            values = list(pool.map(lambda number: self.runtime._call(operation, number), range(8)))
        self.assertEqual(values, list(range(8)))
        self.assertEqual(sorted(completed), values)
        self.assertEqual(peak, 1)


class ForgeRecoveryTests(IsolatedRuntimeTests):
    def runtime(self, root):
        from core.forge import Runtime
        factory = Mock(side_effect=AssertionError('Real Codex process forbidden'))
        runtime = Runtime(data_root=root, executable=self.root / 'unused-codex.exe',
                          transport_factory=factory, request_timeout=1)
        self.addCleanup(runtime.close)
        self.assertTrue(runtime.thread.is_alive())
        factory.assert_not_called()
        return runtime

    def test_invalid_session_variants_start_and_preserve_original_bytes(self):
        samples = ('[]', 'null', '"text"', '42', '{}', '{"project_id": []}',
                   '{"project_id": "../escape"}', '{broken')
        for index, raw in enumerate(samples):
            with self.subTest(raw=raw):
                root = self.root / str(index)
                root.mkdir()
                session = root / 'session.json'
                session.write_bytes(raw.encode())
                runtime = self.runtime(root)
                result = runtime.command('list')
                self.assertTrue(result['accepted'])
                self.assertEqual(result['projects'], [])
                self.assertIn('preservado', runtime.snapshot()['error'])
                runtime.close()
                self.assertEqual(session.read_bytes(), raw.encode())

    def test_recover_existing_project_without_rewriting_bad_session(self):
        from core.forge.files import ProjectStore
        root = self.root / 'recovery'
        store = ProjectStore(root)
        project = store.create('Keep my work')
        (store.workspace(project) / 'notes.md').write_bytes(b'Private offline fixture\n')
        store.checkpoint(project)
        workspace = (store.workspace(project) / 'notes.md').read_bytes()
        manifest = copy.deepcopy(store.load(project['id']))
        session = root / 'session.json'
        session.write_bytes(b'[]')
        # A newer malformed manifest must not prevent recovery of the valid one.
        corrupt = root / 'projects' / ('f' * 32)
        corrupt.mkdir()
        (corrupt / 'manifest.json').write_bytes(b'[]')
        runtime = self.runtime(root)
        self.assertEqual(runtime.snapshot()['project']['id'], project['id'])
        self.assertEqual(session.read_bytes(), b'[]')
        result = runtime.command('list')
        self.assertEqual([item['id'] for item in result['projects']], [project['id']])
        runtime.close()
        self.assertEqual(session.read_bytes(), b'[]')
        self.assertEqual(store.load(project['id']), manifest)
        self.assertEqual((store.workspace(project) / 'notes.md').read_bytes(), workspace)

    def test_explicit_open_keeps_recovery_copy_and_restarts_normally(self):
        from core.forge.files import ProjectStore
        root = self.root / 'explicit-open'
        store = ProjectStore(root)
        project = store.create('Recovered project')
        session = root / 'session.json'
        session.write_bytes(b'{malformed-original')
        runtime = self.runtime(root)
        result = runtime.command('open', project_id=project['id'])
        self.assertTrue(result['accepted'], result)
        self.assertEqual(json.loads(session.read_bytes()), {'project_id': project['id']})
        backups = list(root.glob('session.recovery-*.json'))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_bytes(), b'{malformed-original')
        runtime.close()
        reopened = self.runtime(root)
        self.assertEqual(reopened.snapshot()['project']['id'], project['id'])
        reopened.close()
        self.assertEqual(backups[0].read_bytes(), b'{malformed-original')

    def test_missing_project_reference_recovers_existing_project(self):
        from core.forge.files import ProjectStore
        root = self.root / 'missing-project'
        store = ProjectStore(root)
        project = store.create('Still here')
        session = root / 'session.json'
        original = json.dumps({'project_id': 'e' * 32}).encode()
        session.write_bytes(original)
        runtime = self.runtime(root)
        self.assertEqual(runtime.snapshot()['project']['id'], project['id'])
        runtime.close()
        self.assertEqual(session.read_bytes(), original)

    def test_failed_recovery_copy_preserves_session_and_allows_retry(self):
        from core.forge.files import ProjectStore
        from core.forge import runtime as backend
        root = self.root / 'failed-backup'
        store = ProjectStore(root)
        project = store.create('Preserve through disk failure')
        session = root / 'session.json'
        session.write_bytes(b'null')
        runtime = self.runtime(root)
        original_write = backend.atomic_write

        def fail_backup(path, data):
            if path.name.startswith('session.recovery-'):
                raise OSError('Synthetic recovery write failure')
            return original_write(path, data)

        with patch.object(backend, 'atomic_write', side_effect=fail_backup):
            self.assertFalse(runtime.command('open', project_id=project['id'])['accepted'])
        self.assertEqual(session.read_bytes(), b'null')
        self.assertTrue(runtime.command('open', project_id=project['id'])['accepted'])
        self.assertEqual([path.read_bytes() for path in root.glob('session.recovery-*.json')], [b'null'])
        runtime.close()


if __name__ == '__main__':
    unittest.main()
