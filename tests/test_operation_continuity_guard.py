import unittest
from unittest.mock import Mock, AsyncMock, patch
from types import SimpleNamespace
from core.application_context import ApplicationContext


class OperationContinuity(unittest.TestCase):
    def setUp(self):
        self.context=ApplicationContext()
        self.args={'action':'execute','command':'synthetic-task'}

    def pending(self):
        self.context.record_tool_result('worker',self.args,{'ok':True,'state':'running','job_id':'job-1'})

    def test_followup_does_not_restart_running_operation(self):
        self.pending()
        for text in ('e ai?', 'como esta?', 'continua'):
            self.context.observe_user(text)
            self.assertTrue(self.context.tool_retry_check('worker',self.args))
            query={'action':'result','job_id':'job-1'}
            self.assertEqual(self.context.tool_retry_check('worker',query),'')
            self.context.record_tool_result('worker',query,{'ok':True,'state':'running','job_id':'job-1'})
            self.assertEqual(self.context.tool_retry_check('worker',query),'')

    def test_matching_terminal_query_releases_original_call(self):
        for state,ok in (('finished',True),('failed',False)):
            with self.subTest(state=state):
                self.pending()
                self.context.record_tool_result('worker',{'action':'result','job_id':'job-1'},
                                                {'ok':ok,'state':state,'job_id':'job-1'})
                self.assertEqual(self.context.tool_retry_check('worker',self.args),'')

    def test_wrong_job_tool_or_unrequested_reference_cannot_release(self):
        cases=[('other',{'action':'result','job_id':'job-1'},'job-1'),
               ('worker',{'action':'result','job_id':'job-2'},'job-2'),
               ('worker',{'action':'status'},'job-1')]
        for tool,args,identifier in cases:
            with self.subTest(tool=tool,args=args):
                self.pending()
                self.context.record_tool_result(tool,args,{'ok':True,'state':'finished','job_id':identifier})
                self.assertTrue(self.context.tool_retry_check('worker',self.args))

    def test_uncertain_query_does_not_claim_completion(self):
        self.pending()
        self.context.record_tool_result('worker',{'action':'result','job_id':'job-1'},
                                        {'ok':False,'uncertain':True,'job_id':'job-1'})
        self.context.observe_user('e agora?')
        self.assertTrue(self.context.tool_retry_check('worker',self.args))
        self.assertEqual(self.context.tool_retry_check('worker',{'action':'result','job_id':'job-1'}),'')

    def test_query_error_without_terminal_state_does_not_release_job(self):
        self.pending()
        self.context.record_tool_result('worker',{'action':'result','job_id':'job-1'},
                                        {'ok':False,'error':'Connection unavailable','job_id':'job-1'})
        self.assertTrue(self.context.tool_retry_check('worker',self.args))

    def test_uncertain_original_survives_followup_until_observed(self):
        self.context.record_tool_result('worker',self.args,{'ok':False,'uncertain':True,'job_id':'job-1'})
        self.context.observe_user('como esta?')
        self.assertTrue(self.context.tool_retry_check('worker',self.args))
        self.context.record_tool_result('worker',{'action':'result','job_id':'job-1'},
                                        {'ok':True,'state':'finished','job_id':'job-1'})
        self.assertEqual(self.context.tool_retry_check('worker',self.args),'')

    def test_unidentified_pending_does_not_lock_queries_or_guess_identity(self):
        self.context.record_tool_result('worker',self.args,{'ok':True,'state':'running'})
        self.assertEqual(self.context.tool_retry_check('worker',self.args),'')

    def test_uncertain_status_allows_one_retry_without_restarting_work(self):
        self.pending()
        query={'action':'result','job_id':'job-1'}
        for attempt in range(2):
            self.context.record_tool_result('worker',query,{'ok':False,'uncertain':True,'job_id':'job-1'})
            self.assertEqual(bool(self.context.tool_retry_check('worker',query)),attempt==1)
            self.assertTrue(self.context.tool_retry_check('worker',self.args))

    def test_shared_turn_does_not_settle_different_job(self):
        self.context.record_tool_result('worker',self.args,
                                        {'ok':True,'state':'running','job_id':'job-1','turn_id':'turn-1'})
        self.context.record_tool_result('worker',{'action':'result','job_id':'job-2','turn_id':'turn-1'},
                                        {'ok':True,'state':'finished','job_id':'job-2','turn_id':'turn-1'})
        self.assertTrue(self.context.tool_retry_check('worker',self.args))

    def test_response_with_mismatched_request_identity_cannot_settle(self):
        self.pending()
        self.context.record_tool_result('worker',{'action':'result','job_id':'job-1','turn_id':'turn-2'},
                                        {'ok':True,'state':'finished','job_id':'job-1','turn_id':'turn-1'})
        self.assertTrue(self.context.tool_retry_check('worker',self.args))

    def test_turn_only_observation_cannot_settle_or_reclassify_job(self):
        for state in ('finished','running'):
            with self.subTest(state=state):
                self.context.record_tool_result('worker',self.args,
                    {'ok':False,'uncertain':True,'job_id':'job-1','turn_id':'turn-1'})
                self.context.record_tool_result('worker',{'action':'result','turn_id':'turn-1'},
                    {'ok':True,'state':state,'turn_id':'turn-1'})
                self.assertTrue(self.context.tool_retry_check('worker',self.args))
                self.assertEqual(self.context.snapshot()['unresolved_operations'][0]['last_observed_outcome'],'uncertain')

    def test_turn_cannot_settle_specific_operation_without_operation_id(self):
        self.context.record_tool_result('worker',self.args,
            {'ok':True,'state':'running','operation_id':'op-1','turn_id':'turn-1'})
        self.context.record_tool_result('worker',{'action':'result','turn_id':'turn-1'},
            {'ok':True,'state':'finished','turn_id':'turn-1'})
        self.assertTrue(self.context.tool_retry_check('worker',self.args))

    def test_turn_is_sufficient_when_no_more_specific_identity_exists(self):
        self.context.record_tool_result('worker',self.args,{'ok':True,'state':'running','turn_id':'turn-1'})
        self.context.record_tool_result('worker',{'action':'result','turn_id':'turn-1'},
            {'ok':True,'state':'finished','turn_id':'turn-1'})
        self.assertFalse(self.context.tool_retry_check('worker',self.args))

    def test_poll_refines_identity_before_another_job_finishes(self):
        self.context.record_tool_result('worker',self.args,{'ok':True,'state':'running','turn_id':'turn-1'})
        self.context.record_tool_result('worker',{'action':'result','turn_id':'turn-1'},
            {'ok':True,'state':'running','turn_id':'turn-1','job_id':'job-1'})
        self.context.record_tool_result('worker',{'action':'result','turn_id':'turn-1','job_id':'job-2'},
            {'ok':True,'state':'finished','turn_id':'turn-1','job_id':'job-2'})
        self.assertTrue(self.context.tool_retry_check('worker',self.args))
        self.assertEqual(self.context.snapshot()['unresolved_operations'][0]['references']['job_id'],'job-1')

    def test_request_conflict_cannot_be_hidden_by_sparse_response(self):
        self.context.record_tool_result('worker',self.args,
            {'ok':True,'state':'running','job_id':'job-1','turn_id':'turn-1'})
        self.context.record_tool_result('worker',{'action':'result','job_id':'job-1','turn_id':'turn-2'},
            {'ok':True,'state':'finished','job_id':'job-1'})
        self.assertTrue(self.context.tool_retry_check('worker',self.args))

    def test_job_query_need_not_repeat_optional_turn_metadata(self):
        self.context.record_tool_result('worker',self.args,
            {'ok':True,'state':'running','job_id':'job-1','turn_id':'turn-1'})
        self.context.record_tool_result('worker',{'action':'result','job_id':'job-1'},
            {'ok':True,'state':'finished','job_id':'job-1'})
        self.assertFalse(self.context.tool_retry_check('worker',self.args))

    def test_snapshot_selection_is_isolated_and_operation_alias_retained(self):
        self.context.remember_selection('contacts',{'id':'person-1','contact':{'name':'Synthetic'}})
        snapshot=self.context.snapshot()
        snapshot['selections']['contacts']['contact']['name']='Changed'
        self.assertEqual(self.context.selection('contacts')['contact']['name'],'Synthetic')
        self.context.record_tool_result('worker',{'operation':'inspect'},{'ok':True})
        self.assertEqual(self.context.snapshot()['recent_operations'][-1]['action'],'inspect')

    def test_current_pending_observation_supersedes_prior_uncertainty(self):
        self.context.record_tool_result('worker',self.args,{'ok':False,'uncertain':True,'job_id':'job-1'})
        self.context.record_tool_result('worker',{'action':'result','job_id':'job-1'},
                                        {'ok':True,'state':'running','job_id':'job-1'})
        observed=self.context.snapshot()['unresolved_operations'][0]
        self.assertEqual(observed['last_observed_outcome'],'pending')
        self.assertTrue(self.context.tool_retry_check('worker',self.args))

    def test_successful_pending_poll_resets_transient_query_failure_count(self):
        self.pending()
        query={'action':'result','job_id':'job-1'}
        failure={'ok':False,'error':'Temporary unavailable','job_id':'job-1'}
        self.context.record_tool_result('worker',query,failure)
        self.context.record_tool_result('worker',query,{'ok':True,'state':'running','job_id':'job-1'})
        self.context.record_tool_result('worker',query,failure)
        self.assertEqual(self.context.tool_retry_check('worker',query),'')
        self.assertTrue(self.context.tool_retry_check('worker',self.args))

    def test_unresolved_reference_survives_recent_history_expiry(self):
        clock=Mock(return_value=0)
        self.context=ApplicationContext(clock)
        self.pending()
        for _ in range(20):self.context.record_tool_result('reader',{'action':'read'},{'ok':True})
        clock.return_value=1000
        state=self.context.snapshot()
        self.assertEqual(state['recent_operations'],[])
        self.assertEqual(state['unresolved_operations'][0]['references'],{'job_id':'job-1'})
        self.assertTrue(state['unresolved_operations'][0]['needs_current_observation'])
        self.assertNotIn('synthetic-task',str(state))
        state['unresolved_operations'][0]['references']['job_id']='changed'
        self.assertIn('job-1',self.context.tool_retry_check('worker',self.args))
        self.assertEqual(self.context.snapshot()['unresolved_operations'][0]['references']['job_id'],'job-1')


class HostContinuity(unittest.IsolatedAsyncioTestCase):
    async def test_followup_blocks_duplicate_but_allows_result_query(self):
        from main import JarvisLive
        from core.task_execution import ExecutionLedger
        runner=JarvisLive.__new__(JarvisLive)
        runner.ui=Mock();runner._application_context=ApplicationContext()
        runner._sync_activity_state=Mock()
        args={'action':'execute','command':'synthetic-task'}
        runner._execute_tool_body=AsyncMock(side_effect=[
            SimpleNamespace(response={'result':{'ok':True,'state':'running','job_id':'job-1'}}),
            SimpleNamespace(response={'result':{'ok':True,'state':'finished','job_id':'job-1'}})])
        with patch('core.task_execution.LEDGER',ExecutionLedger()):
            await runner._execute_tool(SimpleNamespace(id='1',name='worker',args=args))
            runner._application_context.observe_user('e ai?')
            blocked=await runner._execute_tool(SimpleNamespace(id='2',name='worker',args=args))
            self.assertTrue(blocked.response['result']['retry_blocked'])
            result=await runner._execute_tool(SimpleNamespace(id='3',name='worker',args={'action':'result','job_id':'job-1'}))
        self.assertEqual(runner._execute_tool_body.await_count,2)
        self.assertEqual(result.response['execution_assessment']['state'],'tool_reported')
        self.assertEqual(runner._application_context.snapshot()['unresolved_operations'],[])
        self.assertEqual(runner._tools_inflight,0)


if __name__=='__main__':unittest.main()
