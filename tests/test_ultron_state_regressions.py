"""Offline regressions: no Qt, accounts, OS probes, cleanup or repairs."""
import ast
import copy
from pathlib import Path
from types import SimpleNamespace
import threading
import time
import unittest
from unittest.mock import Mock, patch

from core.presentation_clock import PresentationClock
from core.ultron import Runtime
from core.ultron_presentation import projection


class RuntimeStateTests(unittest.TestCase):
    def setUp(self):
        self.processes = patch('subprocess.run', side_effect=AssertionError('OS execution forbidden'))
        self.processes.start()
        self.addCleanup(self.processes.stop)
        self.runtime = Runtime()
        self.addCleanup(self.runtime.close)
        service = self.runtime._service
        self.probes = []
        for name, value in [('telemetry', {'cpu_percent': 7}), ('powershell_summary', None),
                            ('vault_list', [])]:
            guard = patch.object(service, name, return_value=value)
            self.probes.append(guard.start())
            self.addCleanup(guard.stop)

    def command(self, text, turn):
        return self.runtime.command(text, text, user_turn=turn)

    def finish_scan(self):
        # Queue a worker-side barrier behind the asynchronous diagnostic task.
        async def wait():
            await self.runtime._service.SCAN_TASK
        self.runtime._call(wait)

    def test_refresh_runs_new_queries_but_status_only_reads(self):
        self.command('ativar protocolo ultron', 1)
        self.finish_scan()
        probes = self.probes[1]
        count = probes.call_count
        self.assertEqual(self.command('status', 2)['mode'], 'diagnostic')
        self.assertEqual(probes.call_count, count)
        self.assertEqual(self.command('atualize o diagnostico', 3)['mode'], 'scan_wait')
        self.finish_scan()
        self.assertEqual(probes.call_count, count * 2)
        self.assertEqual(len(self.runtime.snapshot()['findings']), count)

    def test_generated_refresh_cannot_start_scan(self):
        self.command('ativar protocolo ultron', 1)
        self.finish_scan()
        count = self.probes[1].call_count
        self.runtime.command('atualize o diagnostico', 'oi', user_turn=2)
        self.assertEqual(self.probes[1].call_count, count)

    def test_generated_status_during_scan_is_partial_not_completed(self):
        self.runtime._service.STATE['scan']['running']=True
        result=self.runtime.command('status','como esta indo',user_turn=1)
        self.assertEqual(result['mode'],'scan_wait')
        self.assertIn('parciais',result['speech'])

    def test_tool_adapter_does_not_mark_partial_status_completed(self):
        import json
        from contextlib import nullcontext
        from actions.ultron_protocol import ultron_protocol
        self.runtime._service.STATE['scan']['running']=True
        player=SimpleNamespace(ultron_runtime=self.runtime,present_ultron=Mock(),
            ultron_user_context=lambda:{'text':'como esta indo','serial':1},
            ultron_authorization=lambda context:nullcontext())
        result=json.loads(ultron_protocol({'command':'status'},player))
        self.assertEqual(result['mode'],'scan_wait')
        self.assertFalse(result['completed'])

    def test_cancel_discards_question_and_later_yes_cannot_execute(self):
        self.command('ativar protocolo ultron', 1)
        self.finish_scan()
        service = self.runtime._service
        prepared = {'details': {'scope': 'offline fixture'}, 'args': None, 'fingerprint': None}
        with patch('core.ultron.ultron_tools.prepare', return_value=prepared), \
                patch.object(service, 'confirm_action', side_effect=AssertionError('Execution forbidden')):
            question = self.command('reparar windows', 2)
            self.assertEqual(question['mode'], 'question')
            self.assertIn('Deseja executar esse reparo', question['speech'])
            self.assertEqual(self.command('cancelar', 3)['mode'], 'cancelled')
            self.assertEqual(service.PENDING, {})
            self.command('sim', 4)
        self.assertFalse(self.runtime.snapshot()['confirmation']['pending'])

    def test_projection_keeps_snapshot_order(self):
        first = projection(self.runtime.snapshot())
        second = projection(self.runtime.snapshot())
        self.assertGreater(second['snapshot_serial'], first['snapshot_serial'])

    def test_projection_keeps_latest_running_operations(self):
        records = [{'id': i, 'state': 'completed'} for i in range(8)]
        records.append({'id': 8, 'state': 'running'})
        self.assertEqual(projection({'operations': records})['operations'][-1], records[-1])


class UiStateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(__file__).resolve().parents[1] / 'ui.py'
        tree = ast.parse(path.read_text(encoding='utf-8'))
        window = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'MainWindow')
        methods = [n for n in window.body if isinstance(n, ast.FunctionDef)
                   and n.name in ('_show_ultron', '_poll_ultron', '_ultron_visual_failed')]
        cls.namespace = {'time': time, 'threading': threading}
        exec(compile(ast.Module(body=methods, type_ignores=[]), str(path), 'exec'), cls.namespace)

    def window(self):
        window = SimpleNamespace(
            _ultron_payload=None, _ultron_polling=False, _ultron_announced=None,
            _ultron_alerted_at=0, _ultron_clock=PresentationClock(), _ultron_timer=Mock(),
            _presentation_clock=PresentationClock(), _settle_timer=Mock(), _terminal=Mock(),
            _presentation={'narration_active': True, 'dismissal': 'old'}, _visual_scene=Mock(),
            _forge_controller=None, _space_view=Mock(failed=False), _center_split=Mock(),
            _pin_previews={}, _overlay=None, _ready=True, _content_panel=Mock(), _execution=Mock(),
            _environment=SimpleNamespace(operation_name='', operation_event=Mock()),
            hud=SimpleNamespace(speaking=False, state='LISTENING'),
            on_ultron_ready=Mock(), on_ultron_alert=Mock(return_value=True),
            _layout_scene=Mock(), _sync_environment=Mock(), _log=Mock())
        return window

    def show(self, window, phase='active', serial=1, result=None, **state):
        self.namespace['_show_ultron'](window, {'state': {
            'phase': phase, 'snapshot_serial': serial, 'scan': {}, **state}, 'result': result})

    def test_old_poll_cannot_reactivate_after_deactivation(self):
        window = self.window()
        self.show(window, serial=1)
        self.show(window, phase='idle', serial=3, result={'mode': 'deactivation'})
        payload = window._ultron_payload
        self.show(window, serial=2, scan={'finished_at': 'old'})
        self.assertIs(window._ultron_payload, payload)
        self.assertTrue(window._ultron_clock.cancelled)
        window.on_ultron_ready.assert_not_called()

    def test_token_bearing_poll_crosses_real_webengine_serializer_and_completes(self):
        from core.spatial_view import SpatialCoreView
        import json
        window=self.window()
        page=Mock()
        view=SimpleNamespace(failed=False,_loaded=True,_alive=lambda:True,page=lambda:page)
        view.sync_ultron=lambda payload:SpatialCoreView.sync_ultron(view,payload)
        view.advance_ultron=Mock()
        window._space_view=view
        self.show(window,phase='scanning',scan={'running':True,'stage':'defender','progress':14.3})
        token=object();window._ultron_polling=token
        self.namespace['_show_ultron'](window,{'poll_token':token,'forge_generation':0,
            'state':{'phase':'active','snapshot_serial':2,'scan':{'running':False,'stage':'complete','progress':100,'finished_at':'done'}},'result':None})
        script=page.runJavaScript.call_args.args[0]
        data=json.loads(script.split('window.updateUltron(',1)[1][:-1])
        self.assertEqual(data['state']['scan']['progress'],100)
        self.assertNotIn('poll_token',data)
        self.assertNotIn('forge_generation',data)
        self.assertFalse(window._ultron_polling)
        window.on_ultron_ready.assert_called_once()

    def test_entry_stops_old_presentation_and_hides_terminal_and_visuals(self):
        window = self.window()
        self.show(window)
        self.assertNotIn('dismissal', window._presentation)
        self.assertFalse(window._presentation['narration_active'])
        window._settle_timer.stop.assert_called_once()
        window._terminal.hide.assert_called_once()
        window._visual_scene.cancel.assert_called_once()
        window._visual_scene.clear_all.assert_called_once_with(preserve_pinned=True)
        window._visual_scene.layer.hide.assert_called_once()
        self.assertTrue(window._presentation_clock.cancelled)

    def test_command_does_not_release_inflight_poll_or_duplicate_diagnosis(self):
        window = self.window()
        token = object()
        window._ultron_polling = token
        self.show(window, result={'mode': 'diagnostic'}, scan={'finished_at': 'done'})
        self.assertIs(window._ultron_polling, token)
        self.show(window, serial=2, scan={'finished_at': 'done'})
        window.on_ultron_ready.assert_not_called()

    def test_newer_poll_does_not_drop_question_result_from_same_turn(self):
        window = self.window()
        self.show(window, serial=3, last_user_turn=2, confirmation_pending=True)
        self.show(window, serial=2, last_user_turn=2, result={'mode': 'question'},
                  confirmation_pending=False)
        self.assertEqual(window._ultron_payload['result']['mode'], 'question')
        self.assertTrue(window._ultron_payload['state']['confirmation_pending'])
        self.assertEqual(window._ultron_snapshot_serial, 3)

    def test_older_turn_result_cannot_replace_current_question(self):
        window = self.window()
        self.show(window, serial=3, last_user_turn=3, result={'mode': 'question'})
        payload = window._ultron_payload
        self.show(window, serial=2, last_user_turn=2, result={'mode': 'diagnostic'})
        self.assertIs(window._ultron_payload, payload)

    def test_cancel_prevents_delayed_completion_and_alert(self):
        window = self.window()
        self.show(window, result={'mode': 'cancelled'}, scan={'running': True})
        calls = window._space_view.method_calls
        self.assertLess(next(i for i, call in enumerate(calls) if call[0] == 'sync_ultron'),
                        next(i for i, call in enumerate(calls) if call[0] == 'advance_ultron'))
        self.show(window, serial=2, scan={'finished_at': 'done'},
                  monitor={'enabled': True, 'events': [{'kind': 'cpu_percent', 'threshold': 90}]},
                  telemetry={'cpu_percent': 99})
        window.on_ultron_ready.assert_not_called()
        window.on_ultron_alert.assert_not_called()

    def test_ready_and_monitor_alert_never_fire_together(self):
        window = self.window()
        self.show(window, scan={'finished_at': 'done'},
                  monitor={'enabled': True, 'events': [{'kind': 'cpu_percent', 'threshold': 90}]},
                  telemetry={'cpu_percent': 99})
        window.on_ultron_ready.assert_called_once()
        window.on_ultron_alert.assert_not_called()

    def test_thinking_and_running_operations_defer_callbacks(self):
        for thinking in (True, False):
            window = self.window()
            window.hud.state = 'THINKING' if thinking else 'LISTENING'
            self.show(window, scan={'finished_at': 'done'},
                      operations=[] if thinking else [{'state': 'running'}])
            window.on_ultron_ready.assert_not_called()

    def test_rejection_keeps_spoken_projection_and_clock(self):
        window = self.window()
        self.show(window, result={'mode': 'question'})
        window._ultron_clock.enqueue('Deseja executar esse reparo?')
        original = copy.deepcopy(list(window._ultron_clock.pending))
        self.show(window, serial=2, result={'mode': 'rejected', 'accepted': False})
        self.assertEqual(list(window._ultron_clock.pending), original)
        self.assertEqual(window._ultron_payload['result']['mode'], 'question')

    def test_forge_discards_payload_before_mutating_scene(self):
        window = self.window()
        window._forge_controller = SimpleNamespace(active=True, generation=2)
        self.show(window, scan={'finished_at': 'done'})
        self.assertIsNone(window._ultron_payload)
        window._space_view.sync_ultron.assert_not_called()
        window.on_ultron_ready.assert_not_called()

    def test_poll_from_previous_forge_generation_is_discarded(self):
        window = self.window()
        window._forge_controller = SimpleNamespace(active=False, generation=2)
        token = object()
        window._ultron_polling = token
        self.namespace['_show_ultron'](window, {'state': {'phase': 'active'},
            'poll_token': token, 'forge_generation': 0})
        self.assertIsNone(window._ultron_payload)
        window._space_view.sync_ultron.assert_not_called()

    def test_poll_error_is_delivered_and_released_on_ui_thread(self):
        window = self.window()
        window._ultron_runtime = Mock()
        window._ultron_runtime.snapshot.side_effect = RuntimeError('offline failure')
        window._ultron_sig = Mock()
        with patch.object(threading, 'Thread') as thread:
            self.namespace['_poll_ultron'](window)
            thread.call_args.kwargs['target']()
        self.assertTrue(window._ultron_polling)
        payload = window._ultron_sig.emit.call_args.args[0]
        self.assertTrue(payload['poll_error'])
        self.namespace['_show_ultron'](window, payload)
        self.assertFalse(window._ultron_polling)


if __name__ == '__main__':
    unittest.main()
