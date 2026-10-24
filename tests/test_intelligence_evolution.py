import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch, AsyncMock

from core.task_execution import ExecutionLedger
from core.intent_context import build


class DurableWork(unittest.TestCase):
    def test_context_preserves_original_step_numbers(self):
        ledger=ExecutionLedger()
        plan=ledger.run({'action':'create','title':'Investigacao','steps':[f'Etapa {i}' for i in range(1,9)]})
        ledger.run({'action':'checkpoint','id':plan['id'],'step':6,'note':'Conferir destino'})
        context=ledger.context()['plans'][0]
        self.assertEqual([step['step'] for step in context['steps']],[5,6,7,8])
        self.assertEqual(context['current_step'],6)
        self.assertTrue(context['partial'])

    def test_old_plan_resumed_is_in_recent_context_after_restart(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'work.json'
            ledger=ExecutionLedger(path)
            with patch('core.task_execution.time.time',side_effect=[1,2,3,4,5]):
                plans=[ledger.run({'action':'create','title':str(i),'steps':['Conferir']}) for i in range(4)]
                ledger.run({'action':'checkpoint','id':plans[0]['id'],'step':1,'note':'Retomado'})
            context=ExecutionLedger(path).context()['plans']
            self.assertEqual(context[-1]['id'],plans[0]['id'])
            self.assertEqual(len(context),3)

    def test_read_does_not_change_recency(self):
        ledger=ExecutionLedger()
        plan=ledger.run({'action':'create','title':'X','steps':['Conferir']})
        self.assertEqual(ledger.run({'action':'read','id':plan['id']})['updated_at'],plan['updated_at'])

    def test_invalid_persisted_timestamp_is_preserved(self):
        for stamp in ('yesterday',True,float('nan'),float('inf'),-1):
            with self.subTest(stamp=stamp), tempfile.TemporaryDirectory() as folder:
                path=Path(folder)/'work.json';ledger=ExecutionLedger(path)
                plan=ledger.run({'action':'create','title':'X','steps':['Conferir']})
                data=json.loads(path.read_text(encoding='utf-8'))
                data['plans'][plan['id']]['updated_at']=stamp
                content=json.dumps(data);path.write_text(content,encoding='utf-8')
                with self.assertRaises(ValueError):ExecutionLedger(path).context()
                self.assertEqual(path.read_text(encoding='utf-8'),content)

    def test_legacy_plans_without_dates_still_load(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'work.json';ledger=ExecutionLedger(path)
            plan=ledger.run({'action':'create','title':'X','steps':['Conferir']})
            data=json.loads(path.read_text(encoding='utf-8'))
            for field in ('created_at','updated_at'):data['plans'][plan['id']].pop(field)
            path.write_text(json.dumps(data),encoding='utf-8')
            self.assertEqual(ExecutionLedger(path).context()['plans'][0]['id'],plan['id'])

    def test_resume_checkpoint_without_reexecuting(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'work.json'
            first=ExecutionLedger(path)
            plan=first.run({'action':'create','title':'Projeto Forja','steps':['Verificar arquivo']})
            first.run({'action':'checkpoint','id':plan['id'],'step':1,'note':'Falta conferir o arquivo atual'})
            resumed=ExecutionLedger(path).context()['plans'][0]
            self.assertEqual(resumed['title'],'Projeto Forja')
            self.assertEqual(resumed['steps'][0]['last_outcome'],'unverified')
            self.assertEqual(resumed['steps'][0]['checkpoint'],'Falta conferir o arquivo atual')

    def test_reported_success_is_not_verified_completion(self):
        ledger=ExecutionLedger()
        plan=ledger.run({'action':'create','title':'Verificar','steps':['Inspecionar']})
        event=ledger.record('inspect',{'ok':True})
        ledger.run({'action':'attach','id':plan['id'],'step':1,'evidence_id':event})
        with self.assertRaises(ValueError):ledger.run({'action':'complete','id':plan['id']})

    def test_archiving_frees_capacity_without_claiming_success(self):
        ledger=ExecutionLedger()
        for n in range(20):
            plan=ledger.run({'action':'create','title':str(n),'steps':['Etapa']})
        archived=ledger.run({'action':'archive','id':plan['id']})
        self.assertEqual(archived['state'],'archived')
        self.assertEqual(ledger.run({'action':'create','title':'Novo','steps':['Etapa']})['state'],'planned')

    def test_corruption_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'work.json';path.write_text('{broken',encoding='utf-8')
            with self.assertRaises(ValueError):ExecutionLedger(path).run({'action':'create','title':'New','steps':['X']})
            self.assertEqual(path.read_text(),'{broken')

    def test_credentials_are_redacted_on_disk(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'work.json'
            ExecutionLedger(path).run({'action':'create','title':'senha: private-test-secret','steps':['Conferir']})
            self.assertNotIn('private-test-secret',path.read_text())
            self.assertEqual(len(ExecutionLedger(path).context()['plans']),1)

    def test_failed_write_does_not_leave_a_phantom_plan(self):
        ledger=ExecutionLedger(Path('unused-test-path.json'))
        with patch.object(ledger,'_save',side_effect=OSError('disk full')):
            with self.assertRaises(OSError):ledger.run({'action':'create','title':'Novo','steps':['Etapa']})
        self.assertEqual(ledger.plans,{})

    def test_malformed_plan_is_rejected_before_use(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'work.json'
            path.write_text(json.dumps({'version':1,'events':[],'plans':{'bad':{'id':'bad','title':'X','state':'planned','steps':[{}]}}}))
            with self.assertRaises(ValueError):ExecutionLedger(path).context()


class ContextContract(unittest.TestCase):
    def test_selection_result_does_not_mutate_cached_collection(self):
        from core.application_context import ApplicationContext
        context=ApplicationContext()
        context.record_collection('tasks',[{'id':'original','title':'Original'}])
        selected=context.resolve_record('tasks',1)
        selected['id']='wrong-target'
        self.assertEqual(context.collection('tasks')['items'][0]['id'],'original')
        self.assertEqual(context.selection('tasks')['id'],'original')

    def test_references_are_context_not_execution(self):
        for phrase in ('Sai um pouco dai.', 'Deixa como estava antes.', 'Resolve isso.', 'Faz igual aquele projeto.'):
            with self.subTest(phrase=phrase):
                result=build(phrase,mode='espectro')
                self.assertTrue(result['has_reference'])
                self.assertNotIn('tool_call',result)
                self.assertEqual(result['reasoning'],'contextual')

    def test_correction_overrides_complexity(self):
        result=build('Investigue o projeto, na verdade deixa como estava antes.')
        self.assertTrue(result['has_correction'])
        self.assertEqual(result['reasoning'],'contextual')

    def test_trivial_question_does_not_plan(self):
        self.assertEqual(build('Que horas sao?')['reasoning'],'direct')


class ModelBudget(unittest.TestCase):
    def test_fallback_receives_remaining_budget(self):
        from core import gemini
        clock=[100.0]
        response=SimpleNamespace(text='ok',usage_metadata=None)
        client=Mock()
        def generate(**kwargs):
            clock[0]+=.6
            if kwargs['model']=='first':raise RuntimeError('temporary')
            return response
        client.models.generate_content.side_effect=generate
        with patch.object(gemini,'_LADDERS',{'fast':('first','second','third')}), patch.object(gemini,'_cooling',return_value=False), patch.object(gemini.time,'monotonic',side_effect=lambda:clock[0]), patch.object(gemini,'client',return_value=client) as factory:
            self.assertIs(gemini.call('test',timeout_ms=1000,key='test'),response)
            self.assertLessEqual(factory.call_args.kwargs['timeout_ms'],400)

    def test_exhausted_budget_does_not_start_another_model(self):
        from core import gemini
        clock=[100.0];client=Mock()
        def generate(**kwargs):clock[0]+=2;raise TimeoutError('timeout')
        client.models.generate_content.side_effect=generate
        with patch.object(gemini,'_LADDERS',{'fast':('first','second')}), patch.object(gemini,'_cooling',return_value=False), patch.object(gemini.time,'monotonic',side_effect=lambda:clock[0]), patch.object(gemini,'client',return_value=client):
            self.assertIsNone(gemini.call('test',timeout_ms=1000,key='test'))
            self.assertEqual(client.models.generate_content.call_count,1)


class EvidenceStorageFailure(unittest.IsolatedAsyncioTestCase):
    async def test_context_is_sent_once_without_losing_observed_state(self):
        from main import JarvisLive
        from core.task_execution import LEDGER
        owner=JarvisLive.__new__(JarvisLive)
        observed={'ok':True,'app':'synthetic-editor','can_undo_presence':True}
        work={'plans':[{'id':'synthetic-plan','title':'Resume'}]}
        owner.ui=SimpleNamespace(_win=SimpleNamespace(_spectro_controller=SimpleNamespace(active=True)),
                                 control_interface=Mock(return_value=observed),write_log=Mock())
        owner.session=SimpleNamespace(send_client_content=AsyncMock())
        from core.application_context import ApplicationContext
        owner._application_context=ApplicationContext()
        owner._application_context.remember_selection('tasks',{'id':'selected-task','title':'Conferir arquivo'})
        owner._application_context.record_tool_result('worker',{'action':'execute'}, {'ok':False,'uncertain':True,'job_id':'pending-job'})
        owner._protocol_voice_context=Mock(return_value={})
        # End after sending context; no real command, account or UI is involved.
        owner._protocol_voice_valid=Mock(side_effect=[True,True,False])
        with patch.object(LEDGER,'context',return_value=work):
            self.assertTrue(await owner._route_protocol_user_once('O que acha disso?'))
        owner.session.send_client_content.assert_awaited_once()
        text=owner.session.send_client_content.call_args.kwargs['turns']['parts'][0]['text']
        payload=json.loads(text.splitlines()[1])
        self.assertEqual(set(payload),{'interpretation'})
        self.assertEqual(payload['interpretation']['application'],observed)
        self.assertEqual(payload['interpretation']['work'],work)
        self.assertEqual(text.count('synthetic-plan'),1)
        self.assertEqual(text.count('synthetic-editor'),1)
        state=payload['interpretation']['conversation_state']
        self.assertEqual(state['selections']['tasks']['id'],'selected-task')
        self.assertEqual(state['unresolved_operations'][0]['references']['job_id'],'pending-job')

    async def test_successful_action_is_returned_when_journal_write_fails(self):
        from test_forge_host_routing import RoutingTests
        from core.task_execution import LEDGER
        owner=RoutingTests.owner(self)
        owner.ui.operation_event=Mock();owner.ui.write_log=Mock()
        owner._application_context=SimpleNamespace(tool_retry_check=Mock(return_value=''),record_tool_result=Mock())
        owner._sync_activity_state=Mock()
        owner._execute_tool_body=AsyncMock(return_value=SimpleNamespace(response={'result':{'ok':True,'operation_id':'real-result'}}))
        with patch.object(LEDGER,'record',side_effect=OSError('disk full')):
            response=await owner._execute_tool(SimpleNamespace(name='system_knowledge',id='one',args={'action':'inspect'}))
        self.assertTrue(response.response['result']['ok'])
        self.assertEqual(response.response['result']['operation_id'],'real-result')
        self.assertFalse(response.response['evidence_storage']['available'])
        owner._execute_tool_body.assert_awaited_once()


if __name__=='__main__':unittest.main()
