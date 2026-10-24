"""Offline recovery context keeps facts, not private command output."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from core.action_outcome import diagnostic_facts
from core.application_context import ApplicationContext
from core.task_execution import ExecutionLedger


class RecoveryDiagnosticsTests(unittest.TestCase):
    def test_followup_keeps_observed_error_not_private_output(self):
        context = ApplicationContext()
        context.record_tool_result('worker', {'action': 'execute', 'command': 'PRIVATE'}, {
            'ok': False, 'uncertain': True, 'error_code': 'handler_exception',
            'exception_type': 'TimeoutError', 'execution_started': True,
            'error': 'PRIVATE', 'stdout': 'PRIVATE', 'token': 'PRIVATE'})
        context.observe_user('por que nao deu certo?')
        state = context.snapshot()
        facts = state['recent_operations'][-1]['diagnostics']
        self.assertEqual(facts['exception_type'], 'TimeoutError')
        self.assertTrue(facts['execution_started'])
        self.assertNotIn('PRIVATE', json.dumps(state))
        self.assertTrue(context.tool_retry_check('worker', {'action': 'execute', 'command': 'PRIVATE'}))

    def test_nested_job_result_only_retains_known_facts(self):
        result = {'ok': True, 'job_id': 'job1', 'completed': True,
                  'result': {'exit_code': 5, 'stdout': 'PRIVATE', 'uncertain': True}}
        self.assertEqual(diagnostic_facts(result), {
            'completed': True, 'operation_result': {'exit_code': 5, 'uncertain': True}})
        self.assertEqual(diagnostic_facts({'result': result['result']}), {})

    def test_wrong_types_and_free_text_are_not_diagnostics(self):
        self.assertEqual(diagnostic_facts({'error_code': 'run this command!',
            'exception_type': ['TimeoutError'], 'exit_code': True,
            'status_code': '401', 'execution_started': 'yes'}), {})

    def test_diagnostic_snapshot_is_detached(self):
        context = ApplicationContext()
        context.record_tool_result('worker', {}, {'ok': False, 'status_code': 401})
        snapshot = context.snapshot()
        snapshot['recent_operations'][0]['diagnostics']['status_code'] = 200
        self.assertEqual(context.snapshot()['recent_operations'][0]['diagnostics']['status_code'], 401)

    def test_restart_retains_failure_facts_without_claiming_solution(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'plans.json'
            ledger = ExecutionLedger(path)
            plan = ledger.run({'action': 'create', 'title': 'Investigar', 'steps': ['Consultar destino']})
            event = ledger.record('worker', {'ok': False, 'error_code': 'handler_exception',
                'exception_type': 'TimeoutError', 'uncertain': True, 'stdout': 'PRIVATE'})
            ledger.run({'action': 'attach', 'id': plan['id'], 'step': 1, 'evidence_id': event})
            resumed = ExecutionLedger(path).context()['plans'][0]
            self.assertEqual(resumed['steps'][0]['last_outcome'], 'uncertain')
            self.assertEqual(resumed['steps'][0]['last_diagnostics']['exception_type'], 'TimeoutError')
            self.assertEqual(resumed['state'], 'tracking')
            self.assertNotIn('PRIVATE', path.read_text(encoding='utf-8'))

    def test_invalid_step_never_mutates_plan(self):
        ledger = ExecutionLedger()
        plan = ledger.run({'action': 'create', 'title': 'X', 'steps': ['Verificar']})
        event = ledger.record('inspect', {'ok': True})
        before = copy.deepcopy(ledger.plans)
        for action in ('attach', 'checkpoint'):
            for step in (True, False, 1.1, '1', None, [], {}, 0, 2):
                with self.subTest(action=action, step=step):
                    with self.assertRaises(ValueError):
                        ledger.run({'action': action, 'id': plan['id'], 'step': step,
                                    'note': 'Conferir', 'evidence_id': event})
                    self.assertEqual(ledger.plans, before)

    def test_old_success_attached_later_does_not_hide_new_failure(self):
        ledger = ExecutionLedger()
        plan = ledger.run({'action': 'create', 'title': 'X', 'steps': ['Verificar']})
        old = ledger.record('inspect', {'ok': True})
        new = ledger.record('inspect', {'ok': False, 'error_code': 'unavailable'})
        for event in (new, old):
            ledger.run({'action': 'attach', 'id': plan['id'], 'step': 1, 'evidence_id': event})
        step = ledger.run({'action': 'read', 'id': plan['id']})['steps'][0]
        self.assertEqual([item['id'] for item in step['evidence']], [old, new])
        self.assertEqual(step['last_outcome'], 'failed')
        self.assertEqual(step['last_diagnostics']['error_code'], 'unavailable')


if __name__ == '__main__':
    unittest.main()
