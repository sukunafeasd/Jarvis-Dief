import json
import unittest
from datetime import datetime
from unittest.mock import Mock,patch,AsyncMock
from types import SimpleNamespace
from core.application_context import ApplicationContext
from core.action_outcome import assess
from core.task_execution import ExecutionLedger
from actions.system_knowledge import system_knowledge


class ContextOutcomes(unittest.TestCase):
    def test_failed_postcondition_counts_as_failure_despite_ok_flag(self):
        context=ApplicationContext();arguments={'action':'move'}
        for _ in range(2):
            context.record_tool_result('interface_control',arguments,{'ok':True,'verification':{'postcondition_verified':False}})
        self.assertTrue(context.tool_retry_check('interface_control',arguments))
        context.record_tool_result('interface_control',arguments,{'ok':True,'state':'running'})
        self.assertTrue(context.tool_retry_check('interface_control',arguments))
        context.record_tool_result('interface_control',arguments,{'ok':True,'verification':{'postcondition_verified':True}})
        self.assertFalse(context.tool_retry_check('interface_control',arguments))

    def test_selection_age_starts_when_selected_and_snapshot_expires_it(self):
        clock=Mock(return_value=0)
        context=ApplicationContext(clock)
        context.record_collection('tasks',[{'id':'one','title':'Primeira'}])
        clock.return_value=590
        context.resolve_record('tasks',1)
        clock.return_value=610
        self.assertEqual(context.selection('tasks')['id'],'one')
        self.assertIn('tasks',context.snapshot()['selections'])
        clock.return_value=1191
        with self.assertRaises(ValueError):context.selection('tasks')
        self.assertNotIn('tasks',context.snapshot()['selections'])
        self.assertTrue(context.snapshot()['collections']['tasks']['expired'])

    def test_new_collection_invalidates_old_selection(self):
        context=ApplicationContext()
        context.record_collection('tasks',[{'id':'one'}]);context.resolve_record('tasks',1)
        context.record_collection('tasks',[{'id':'two'}])
        self.assertNotIn('tasks',context.snapshot()['selections'])

    def test_runtime_reports_current_timezone_aware_clock_each_call(self):
        player=Mock();player.control_interface.return_value={'ok':True}
        for instant in ('2026-10-17T23:59:59-03:00','2026-10-18T00:00:01-03:00'):
            with patch('actions.system_knowledge.datetime') as clock:
                clock.now.return_value.astimezone.return_value=datetime.fromisoformat(instant)
                result=json.loads(system_knowledge({'action':'runtime'},player=player))
            self.assertEqual(result['observed_at'],instant)
            self.assertEqual(result['clock_source'],'system_local')

    def test_ledger_and_assessment_agree_on_unfinished_or_failed_results(self):
        cases=[({'ok':True,'state':'running'},'pending'),
               ({'ok':True,'state':'queued'},'pending'),
               ({'ok':True,'verification':{'postcondition_verified':None}},'unverified'),
               ({'ok':True,'verification':{'postcondition_verified':None,'layout_animating':True}},'pending'),
               ({'ok':True,'verification':{'postcondition_verified':False}},'failed'),
               ({'ok':True,'stage':'uncertain'},'uncertain'),
               ({'ok':True,'verification':{'postcondition_verified':True}},'tool_reported'),
               ('Concluido.','unverified')]
        ledger=ExecutionLedger()
        for result,expected in cases:
            with self.subTest(result=result):
                self.assertEqual(assess(result)['state'],expected)
                ledger.record('test',result)
                self.assertEqual(ledger.run({'action':'history'})['events'][-1]['evidence'],expected)


class HostOutcomes(unittest.IsolatedAsyncioTestCase):
    async def test_model_receives_assessment_and_history_agrees(self):
        from main import JarvisLive
        cases=[({'ok':True,'state':'running'},'pending','pending'),
               ({'ok':True,'verification':{'postcondition_verified':None}},'unverified','finished'),
               ({'ok':True,'verification':{'postcondition_verified':False}},'failed','failed'),
               ("Tool 'test' failed: unavailable",'failed','failed'),
               ('Concluido.','unverified','finished')]
        for raw,expected,event in cases:
            with self.subTest(raw=raw):
                owner=JarvisLive.__new__(JarvisLive)
                owner.ui=SimpleNamespace(operation_event=Mock())
                owner._application_context=ApplicationContext()
                owner._sync_activity_state=Mock()
                owner._execute_tool_body=AsyncMock(return_value=SimpleNamespace(response={'result':raw}))
                call=SimpleNamespace(name='test',id='round8',args={})
                # An unverified string must not erase earlier failure evidence.
                owner._application_context.record_tool_result('test',{}, {'ok':False})
                owner._application_context.record_tool_result('test',{}, {'ok':False})
                owner._application_context.tool_retry_check=Mock(return_value='')
                ledger=ExecutionLedger()
                with patch('core.task_execution.LEDGER',ledger):
                    response=await owner._execute_tool(call)
                self.assertEqual(response.response['execution_assessment']['state'],expected)
                self.assertEqual(ledger.events[-1]['evidence'],expected)
                owner.ui.operation_event.assert_any_call('test',event)
                self.assertEqual(owner._tools_inflight,0)
                self.assertTrue(owner._application_context._tool_failures)


if __name__=='__main__':unittest.main()
