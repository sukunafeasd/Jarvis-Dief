import concurrent.futures
from contextlib import contextmanager
import importlib
import json
import os
from pathlib import Path
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from actions.ultron_protocol import ultron_protocol
from core.ultron import Runtime
from core.ultron import ultron_tools


class UltronIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.env = patch.dict(os.environ, {
            'LOCALAPPDATA': self.temp.name, 'ULTRON_DATA_DIR': str(Path(self.temp.name) / 'lab')})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.addCleanup(patch.stopall)
        patch.object(ultron_tools, 'administrator', return_value=False).start()
        self.runtimes = []
        self.runtime = self.make_runtime()

    def make_runtime(self):
        runtime = Runtime()
        self.runtimes.append(runtime)
        self.addCleanup(runtime.close)
        service = runtime._service
        patch.object(service, 'telemetry', return_value={
            'cpu_percent': 1, 'memory_percent': 2, 'disk_percent': 3, 'unavailable': []}).start()
        patch.object(service, 'powershell_summary', return_value=None).start()
        patch.object(service, 'launch_defender', side_effect=AssertionError('Real Windows call')).start()
        patch.object(ultron_tools, 'launch', side_effect=AssertionError('Real Windows call')).start()
        patch.object(ultron_tools, 'cleanup', side_effect=AssertionError('Real cleanup')).start()
        return runtime

    def command(self, text, serial, runtime=None):
        return (runtime or self.runtime).command(text, text, user_turn=serial)

    def make_player(self, text, serial):
        player = SimpleNamespace(ultron_runtime=self.runtime,
                                 context={'text': text, 'serial': serial},
                                 context_lock=threading.RLock(),
                                 authorized=threading.Event(),
                                 guard_threads=[], present_ultron=Mock())

        def context():
            with player.context_lock:
                return dict(player.context)

        @contextmanager
        def authorization(captured):
            with player.context_lock:
                player.guard_threads.append(threading.current_thread())
                if player.context != captured:
                    raise ValueError('Stale host context')
                player.authorized.set()
                try:
                    yield
                finally:
                    player.authorized.clear()

        player.ultron_user_context = context
        player.ultron_authorization = authorization
        return player

    def activate(self):
        result = self.command('Jarvis, ativar protocolo ultron', 1)
        self.assertEqual(result['mode'], 'activation')
        deadline = time.monotonic() + 3
        while self.runtime.snapshot()['scan']['running'] and time.monotonic() < deadline:
            time.sleep(.01)
        self.assertEqual(self.runtime.snapshot()['phase'], 'active')

    def prepare_backup(self, serial=2):
        source = Path(self.temp.name) / 'source'
        source.mkdir(exist_ok=True)
        (source / 'example.txt').write_text('isolated fixture', encoding='utf-8')
        result = self.command('backup da pasta ' + str(source), serial)
        self.assertEqual(result['mode'], 'question')
        return source, result

    def test_activation_requires_exact_real_utterance_and_serial(self):
        for utterance in ('oi', 'nao pode ativar protocolo ultron',
                          'jarvisativar protocolo ultron', 'sim'):
            result = self.runtime.command('ativar protocolo ultron', utterance, user_turn=1)
            self.assertFalse(result['accepted'])
        self.assertFalse(self.runtime.command('ativar protocolo ultron',
                                             'ativar protocolo ultron')['accepted'])
        self.assertEqual(self.runtime.snapshot()['phase'], 'idle')
        self.activate()

    def test_confirmation_is_bound_once_per_real_turn(self):
        self.activate()
        _, question = self.prepare_backup()
        confirm = Mock(return_value={'file_count': 1})
        with patch.object(self.runtime._service, 'confirm_action', confirm):
            self.assertFalse(self.runtime.command('sim', 'backup da pasta X', user_turn=2)['accepted'])
            self.assertFalse(self.command('sim', 2)['accepted'])
            self.assertTrue(self.runtime.command('status', 'sim', user_turn=3)['accepted'])
            self.assertTrue(self.runtime.snapshot()['confirmation']['pending'])
            self.assertEqual(self.command('sim', 3)['mode'], 'vault')
            self.assertFalse(self.command('sim', 3)['accepted'])
            self.command('sim', 4)
        confirm.assert_called_once_with(question['confirmation_id'])

    def test_same_yes_cannot_confirm_a_later_question(self):
        self.activate()
        self.prepare_backup()
        confirm = Mock(return_value={'file_count': 1})
        with patch.object(self.runtime._service, 'confirm_action', confirm):
            self.command('sim', 3)
            self.prepare_backup(serial=4)
            self.assertFalse(self.command('sim', 3)['accepted'])
            self.command('sim', 5)
        self.assertEqual(confirm.call_count, 2)

    def test_cancel_and_new_real_message_invalidate_confirmation(self):
        self.activate()
        self.prepare_backup()
        self.command('status', 3)
        with patch.object(self.runtime._service, 'confirm_action') as confirm:
            self.command('sim', 4)
            confirm.assert_not_called()
        self.prepare_backup(5)
        self.command('nao', 6)
        self.assertFalse(self.runtime.snapshot()['confirmation']['pending'])
        self.assertEqual(self.runtime._service.PENDING, {})

    def test_expired_confirmation_cannot_execute(self):
        self.activate()
        _, question = self.prepare_backup()
        self.runtime._service.PENDING[question['confirmation_id']]['expires'] = 0
        self.assertFalse(self.runtime.snapshot()['confirmation']['pending'])
        result = self.command('sim', 3)
        self.assertEqual(result['mode'], 'info')
        self.assertEqual(self.runtime.snapshot()['vault'], [])

    def test_intervening_unrouted_user_turn_invalidates_question(self):
        self.activate()
        self.prepare_backup()
        with patch.object(self.runtime._service, 'confirm_action') as confirm:
            self.command('sim', 4)
            confirm.assert_not_called()
        self.assertFalse(self.runtime.snapshot()['confirmation']['pending'])

    def test_backup_rechecks_prepared_file_snapshot(self):
        self.activate()
        source, _ = self.prepare_backup()
        (source / 'example.txt').write_text('changed fixture', encoding='utf-8')
        self.command('sim', 3)
        self.assertEqual(self.runtime.snapshot()['vault'], [])

    def test_backup_and_restore_use_independent_integrated_data(self):
        self.activate()
        self.prepare_backup()
        result = self.command('sim', 3)
        self.assertEqual(result['mode'], 'vault')
        data = Path(self.temp.name) / 'DIEF-JARVIS' / 'ultron'
        self.assertEqual(self.runtime._service.DATA, data.absolute())
        self.assertFalse((Path(self.temp.name) / 'lab').exists())
        self.assertEqual(len(self.runtime.snapshot()['vault']), 1)
        desktop = Path(self.temp.name) / 'desktop'
        desktop.mkdir()
        with patch.object(ultron_tools, 'desktop_path', return_value=desktop):
            self.assertEqual(self.command('recuperar ultimo backup', 4)['mode'], 'question')
            result = self.command('sim', 5)
        recovered = Path(result['result']['recovery_path'])
        self.assertEqual(recovered.parent, desktop)
        self.assertEqual((recovered / 'example.txt').read_text(), 'isolated fixture')

    def test_snapshots_detached_and_runtime_state_isolated(self):
        self.activate()
        other = self.make_runtime()
        snap = self.runtime.snapshot()
        snap['scan']['running'] = True
        snap['findings'].clear()
        self.assertFalse(self.runtime.snapshot()['scan']['running'])
        self.assertTrue(self.runtime.snapshot()['findings'])
        self.assertEqual(other.snapshot()['phase'], 'idle')
        self.prepare_backup()
        self.command('sim', 1, other)
        self.assertTrue(self.runtime.snapshot()['confirmation']['pending'])
        self.assertIsNot(self.runtime._service.CONVERSATIONS, other._service.CONVERSATIONS)

    def test_monitor_and_simulations_persist_across_sync_calls(self):
        self.activate()
        thread = self.runtime._thread
        self.assertEqual(self.command('monitorar', 2)['mode'], 'monitor')
        self.assertTrue(self.runtime.snapshot()['monitor']['enabled'])
        for serial, text in enumerate(('simular falha', 'simular disco', 'simular recuperacao'), 3):
            result = self.command(text, serial)
            self.assertTrue(result['result']['simulated'])
            self.assertFalse(result['result']['computer_effects'])
        self.assertEqual(len(self.runtime.snapshot()['simulations']), 3)
        self.assertIs(thread, self.runtime._thread)
        self.command('desativar protocolo ultron', 6)
        self.assertFalse(self.runtime.snapshot()['monitor']['enabled'])
        self.assertTrue(self.runtime._service.MONITOR_TASK.done())

    def test_windows_confirmation_uses_vetted_tool_once_mocked(self):
        self.activate()
        prepared = {'args': None, 'fingerprint': None,
                    'details': {'scope': 'mock scope', 'requires_administrator': True}}
        with patch.object(ultron_tools, 'prepare', return_value=prepared), \
                patch.object(ultron_tools, 'launch', return_value={
                    'operation_id': 'mock', 'state': 'running'}) as launch:
            self.assertEqual(self.command('reparar windows', 2)['mode'], 'question')
            self.assertFalse(self.runtime.command('sim', 'oi', user_turn=3)['accepted'])
            self.assertEqual(self.command('sim', 3)['mode'], 'operation')
            self.command('sim', 3)
            launch.assert_called_once_with(self.runtime._service, 'windows_repair')

    def test_tool_uses_only_host_context_and_presents_result(self):
        self.activate()
        self.prepare_backup()
        player = self.make_player('oi', 3)
        with patch.object(self.runtime._service, 'confirm_action') as confirm:
            result = json.loads(ultron_protocol({'command': 'sim', 'serial': 4, 'text': 'sim'}, player))
            self.assertFalse(result['accepted'])
            confirm.assert_not_called()
            self.assertTrue(self.runtime.snapshot()['confirmation']['pending'])
        player.present_ultron.assert_called_once()
        self.assertEqual(player.present_ultron.call_args.args[1], result)
        self.assertTrue(json.loads(ultron_protocol({'command': 'status'}, player))['accepted'])

    def test_tool_requires_host_guard_even_for_status(self):
        player = self.make_player('sim', 3)
        del player.ultron_authorization
        with patch.object(self.runtime, 'command') as command:
            result = json.loads(ultron_protocol({'command': 'status'}, player))
        self.assertFalse(result['accepted'])
        command.assert_not_called()
        player.present_ultron.assert_not_called()
        self.assertEqual(self.runtime.snapshot()['last_user_turn'], -1)

    def test_confirmation_revalidated_after_waiting_on_runtime_gate(self):
        self.activate()
        _, question = self.prepare_backup()
        for replacement in ({'text': 'nao', 'serial': 4},
                            {'text': 'nao', 'serial': 3},
                            {'text': 'sim', 'serial': 4}):
            with self.subTest(replacement=replacement):
                player = self.make_player('sim', 3)
                waiting = threading.Event()
                original_call = self.runtime._call

                def queued_call(function, *args):
                    waiting.set()
                    return original_call(function, *args)

                with patch.object(self.runtime, '_call', side_effect=queued_call), \
                        patch.object(self.runtime._service, 'confirm_action') as confirm, \
                        concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    with self.runtime._gate:
                        future = pool.submit(ultron_protocol, {'command': 'sim'}, player)
                        self.assertTrue(waiting.wait(2))
                        self.assertEqual(player.guard_threads, [])
                        with player.context_lock:
                            player.context = replacement
                    result = json.loads(future.result(timeout=3))
                self.assertFalse(result['accepted'])
                confirm.assert_not_called()
                self.assertEqual(player.guard_threads, [self.runtime._thread])
                snapshot = self.runtime.snapshot()
                self.assertEqual(snapshot['last_user_turn'], 2)
                self.assertTrue(snapshot['confirmation']['pending'])
                self.assertIn(question['confirmation_id'], self.runtime._service.PENDING)

    def test_guard_held_through_confirmation_but_not_snapshot(self):
        self.activate()
        _, question = self.prepare_backup()
        player = self.make_player('sim', 3)
        attempting = threading.Event()
        changed = threading.Event()

        def replace_context():
            attempting.set()
            with player.context_lock:
                player.context = {'text': 'nao', 'serial': 4}
                changed.set()

        def confirm_action(identifier):
            self.assertEqual(identifier, question['confirmation_id'])
            self.assertTrue(player.authorized.is_set())
            updater = threading.Thread(target=replace_context)
            updater.start()
            self.assertTrue(attempting.wait(2))
            self.assertFalse(changed.wait(.05))
            return {'file_count': 1}

        original_snapshot = self.runtime.snapshot

        def snapshot():
            self.assertFalse(player.authorized.is_set())
            self.assertTrue(changed.wait(2))
            return original_snapshot()

        with patch.object(self.runtime._service, 'confirm_action', side_effect=confirm_action) as confirm, \
                patch.object(self.runtime, 'snapshot', side_effect=snapshot):
            result = json.loads(ultron_protocol({'command': 'sim'}, player))
        self.assertTrue(result['accepted'])
        self.assertEqual(result['user_turn'], 3)
        confirm.assert_called_once()
        self.assertFalse(self.command('sim', 3)['accepted'])

    def test_guard_error_rejects_activation_without_consuming_turn(self):
        @contextmanager
        def stale():
            raise ValueError('Stale')
            yield

        result = self.runtime.command('ativar protocolo ultron', 'ativar protocolo ultron',
                                      user_turn=1, authorization=stale)
        self.assertFalse(result['accepted'])
        snapshot = self.runtime.snapshot()
        self.assertEqual(snapshot['phase'], 'idle')
        self.assertEqual(snapshot['last_user_turn'], -1)
        self.activate()

    def test_concurrent_confirmation_consumed_once(self):
        self.activate()
        self.prepare_backup()
        with patch.object(self.runtime._service, 'confirm_action', return_value={'file_count': 1}) as confirm:
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
                results = list(pool.map(lambda _: self.command('sim', 3), range(4)))
            self.assertEqual(sum(result['accepted'] for result in results), 1)
            confirm.assert_called_once()

    def test_import_has_no_http_app_and_close_is_idempotent(self):
        service = importlib.import_module('core.ultron.ultron_service')
        self.assertFalse(hasattr(service, 'app'))
        self.assertFalse(hasattr(service, 'voice'))
        self.runtime.close()
        self.runtime.close()
        self.assertFalse(self.runtime._thread.is_alive())
        with self.assertRaises(RuntimeError):
            self.runtime.snapshot()


if __name__ == '__main__':
    unittest.main()
