"""Real adapters with synthetic jobs; no accounts or OS changes."""
import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, AsyncMock, patch
from core import resource_jobs as jobs
from core.application_context import ApplicationContext
from core.essential_plugins import respond


class IntegratedRecovery(unittest.TestCase):
    def test_presentation_evidence_is_separate_from_execution(self):
        from core.action_outcome import assess
        for ok,expected in ((False,'failed'),(True,'requested')):
            with self.subTest(ok=ok):
                result={'ok':True,'presentation':{'ok':ok},'event':{'id':'created-1'}}
                evidence=assess(result)
                self.assertEqual(evidence['state'],'tool_reported')
                self.assertEqual(evidence['presentation'],expected)
                context=ApplicationContext()
                context.record_tool_result('calendar',{'action':'create'},result)
                context.observe_user('nao apareceu')
                self.assertEqual(context.snapshot()['recent_operations'][-1]['presentation'],expected)

    def test_presentation_success_never_overrides_operation_failure(self):
        from core.action_outcome import assess
        result=assess({'ok':False,'presentation':{'ok':True}})
        self.assertEqual(result['state'],'failed')
        self.assertEqual(result['presentation'],'requested')

    def test_display_error_does_not_discard_confirmed_operation(self):
        callback=Mock(return_value={'ok':True,'event':{'id':'created-1','summary':'Synthetic'}})
        player=Mock();player.show_manifestation.side_effect=RuntimeError('private detail')
        result=json.loads(respond(callback,player,'calendar','Agenda'))
        self.assertTrue(result['ok'])
        self.assertEqual(result['event']['id'],'created-1')
        self.assertFalse(result['presentation']['ok'])
        self.assertNotIn('private detail',json.dumps(result))
        callback.assert_called_once()

    def test_failed_operation_does_not_replace_display_with_empty_success(self):
        player=Mock()
        result=json.loads(respond(lambda:{'ok':False,'error':'fixture'},player,'calendar','Agenda'))
        self.assertFalse(result['ok']);player.show_manifestation.assert_not_called()

    def test_provider_status_available_for_diagnosis(self):
        error=RuntimeError('private detail');error.http_status=429
        result=json.loads(respond(Mock(side_effect=error)))
        self.assertEqual(result['status_code'],429)
        self.assertEqual(result['exception_type'],'RuntimeError')
        self.assertNotIn('private detail',str(result))

    def test_resource_job_followup_settles_only_matching_operation(self):
        with patch.object(jobs,'JOBS',{}):
            callbacks=[]
            def gate(key,title,detail,run,on_resolve=None):
                callbacks.extend([run,on_resolve]);return '[CONFIRMATION_PENDING]'
            with patch.object(jobs.confirm,'request',side_effect=gate):
                result=jobs.request('Synthetic','Synthetic',lambda:{'ok':True})
            context=ApplicationContext();args={'action':'create','title':'Synthetic'}
            context.record_tool_result('office_resources',args,result)
            context.observe_user('ja terminou?')
            self.assertTrue(context.tool_retry_check('office_resources',args))
            callbacks[1](True);callbacks[0]()
            snapshot=jobs.snapshot(result['job_id'])
            self.assertEqual(snapshot['job_id'],result['job_id'])
            context.record_tool_result('task_execution',{'action':'result','job_id':'wrong'},snapshot)
            self.assertTrue(context.tool_retry_check('office_resources',args))
            context.record_tool_result('task_execution',{'action':'result','job_id':result['job_id']},snapshot)
            self.assertFalse(context.tool_retry_check('office_resources',args))

    def test_resource_uncertainty_survives_result_query(self):
        with patch.object(jobs,'JOBS',{'fixture':{'id':'fixture','state':'failed',
                'completed':False,'result':{'ok':False,'uncertain':True}}}):
            self.assertTrue(jobs.snapshot('fixture')['uncertain'])


class ContextInspectionFailure(unittest.IsolatedAsyncioTestCase):
    async def test_inspection_failure_preserves_conversation_and_plans(self):
        from main import JarvisLive
        from core.task_execution import LEDGER
        for observation in (RuntimeError('fixture'), None):
            owner=JarvisLive.__new__(JarvisLive)
            owner.ui=SimpleNamespace(_win=SimpleNamespace(_spectro_controller=SimpleNamespace(active=True)),
                control_interface=Mock(side_effect=observation) if isinstance(observation,Exception) else Mock(return_value=observation),write_log=Mock())
            owner.session=SimpleNamespace(send_client_content=AsyncMock())
            owner._application_context=ApplicationContext()
            owner._application_context.remember_selection('tasks',{'id':'known'})
            owner._protocol_voice_context=Mock(return_value={})
            owner._protocol_voice_valid=Mock(side_effect=[True,True,False])
            with patch.object(LEDGER,'context',return_value={'plans':[{'id':'existing'}]}):
                self.assertTrue(await owner._route_protocol_user_once('o que acha disso?'))
            message=owner.session.send_client_content.call_args.kwargs['turns']['parts'][0]['text']
            payload=json.loads(message.splitlines()[1])['interpretation']
            self.assertFalse(payload['application']['ok'])
            self.assertEqual(payload['work']['plans'][0]['id'],'existing')
            self.assertEqual(payload['conversation_state']['selections']['tasks']['id'],'known')


if __name__=='__main__':unittest.main()
