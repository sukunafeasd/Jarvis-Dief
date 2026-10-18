import unittest
from unittest.mock import patch,Mock
from core.application_context import ApplicationContext
from core.action_outcome import assess
from core import powershell_service as service


class OperationFollowup(unittest.TestCase):
    def test_timeout_remains_uncertain_when_read_from_history(self):
        stored={'state':'failed','result':{'ok':False,'uncertain':True,'error':'timeout'}}
        with patch.dict(service._jobs,{'test-job':stored},clear=True),patch.object(service,'run_script') as execute:
            for _ in range(3):
                observed=service.result('test-job')
                self.assertTrue(observed['ok'])
                self.assertTrue(observed['uncertain'])
                self.assertEqual(assess(observed)['state'],'uncertain')
            observed['result']['uncertain']=False
            self.assertTrue(service.result('test-job')['result']['uncertain'])
            execute.assert_not_called()

    def test_running_failed_and_successful_queries_keep_their_meaning(self):
        for state,result,expected in (('running',None,'pending'),
                                      ('failed',{'ok':False},'failed'),
                                      ('finished',{'ok':True},'tool_reported')):
            with self.subTest(state=state),patch.dict(service._jobs,{'test':{'state':state,'result':result}},clear=True):
                self.assertEqual(assess(service.result('test'))['state'],expected)

    def test_followup_keeps_real_reference_without_payload_or_mutable_alias(self):
        clock=Mock(return_value=0);context=ApplicationContext(clock)
        context.record_tool_result('powershell_control',{'action':'execute','command':'PRIVATE'},
                                   {'ok':True,'job_id':'job-123','state':'running','stdout':'PRIVATE'})
        context.observe_user('como esta indo?')
        observed=context.snapshot()['recent_operations']
        self.assertEqual(observed[0]['references'],{'job_id':'job-123'})
        observed[0]['references']['job_id']='wrong'
        self.assertEqual(context.snapshot()['recent_operations'][0]['references']['job_id'],'job-123')
        self.assertNotIn('PRIVATE',str(context.snapshot()))
        clock.return_value=601
        self.assertEqual(context.snapshot()['recent_operations'],[])

    def test_only_bounded_identifiers_are_retained(self):
        context=ApplicationContext()
        for value in ('../private','x'*129,{},None):
            context.record_tool_result('test',{}, {'ok':True,'job_id':value})
            self.assertNotIn('references',context.snapshot()['recent_operations'][-1])


if __name__=='__main__':unittest.main()
