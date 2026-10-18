import unittest
from unittest.mock import Mock
from core.neural_memory import retrieval_payload, notify


class NeuralMemoryTests(unittest.TestCase):
    def test_only_successful_actual_records(self):
        for result in (None, {}, {'ok':False,'items':[{'id':'x','detail':'not evidence'}]}):
            self.assertFalse(retrieval_payload(result,'a')['active'])
        for items in (None,7,'text',{'id':'not a list'}):
            self.assertFalse(retrieval_payload({'ok':True,'items':items},'a')['active'])

    def test_redacts_and_bounds_records(self):
        result=retrieval_payload({'ok':True,'items':[{'id':str(i),'title':'Record','detail':'sk-'+('a'*30)+' '+'x'*600} for i in range(10)]},'a')
        self.assertEqual(len(result['items']),3)
        self.assertEqual(result['depth'],'deep')
        self.assertNotIn('sk-',result['items'][0]['detail'])
        self.assertLessEqual(len(result['items'][0]['detail']),400)

    def test_semantic_shape_retains_original_source(self):
        result=retrieval_payload({'ok':True,'items':[{'category':'projects','key':'forja','record':{'value':'Plano salvo','updated':'2026-10-16'}}]},'b')
        self.assertEqual(result['items'][0]['id'],'projects/forja')
        self.assertEqual(result['items'][0]['detail'],'Plano salvo')
        self.assertEqual(result['depth'],'quick')

    def test_completed_empty_and_failed_searches_do_not_cancel_the_transformation(self):
        for result,outcome in (({'ok':True,'items':[]},'empty'),({'ok':False},'unavailable')):
            payload=retrieval_payload(result,'done',completed=True)
            self.assertTrue(payload['active']);self.assertEqual(payload['outcome'],outcome);self.assertEqual(payload['items'],[])
        self.assertFalse(retrieval_payload({'ok':False},'cancel')['active'])

    def test_duplicate_and_invalid_records_are_not_invented(self):
        data={'ok':True,'items':[{},None,{'id':'a','detail':'one'},{'id':'a','detail':'two'}]}
        self.assertEqual(len(retrieval_payload(data,'x')['items']),1)

    def test_visual_failure_does_not_break_retrieval(self):
        ui=Mock();ui.show_neural_memory.side_effect=RuntimeError('renderer unavailable')
        notify(ui,{'active':False})

    def test_previous_assistant_claim_keeps_role(self):
        result=retrieval_payload({'ok':True,'items':[{'id':'conversation:1','detail':'Vamos implementar uma biblioteca local para preservar todos os projetos da Forja.','role':'assistant','at':'2020-01-01T00:00:00+00:00'}]},'x')
        self.assertEqual(result['items'][0]['role'],'assistant')

class NeuralDispatcherTests(unittest.IsolatedAsyncioTestCase):
    def runner(self):
        import main
        from core.application_context import ApplicationContext
        runner=main.JarvisLive.__new__(main.JarvisLive)
        runner.ui=Mock();runner.ui.muted=False
        runner._application_context=ApplicationContext();runner._manual_rest=False;runner._is_speaking=False
        return runner

    async def test_dispatcher_forwards_actual_result_and_does_not_wait_for_animation(self):
        import main
        from types import SimpleNamespace
        from unittest.mock import AsyncMock
        runner=self.runner()
        result={'ok':True,'items':[{'id':'notes/test','detail':'Fato persistido'}]}
        response=main.types.FunctionResponse(id='neural',name='memory_control',response={'result':__import__('json').dumps(result)})
        runner._execute_tool_body=AsyncMock(return_value=response)
        returned=await runner._execute_tool(SimpleNamespace(id='neural',name='memory_control',args={'action':'list','query':'persistido'}))
        payloads=[call.args[0] for call in runner.ui.show_neural_memory.call_args_list]
        self.assertIs(returned,response);self.assertEqual(len(payloads),2)
        self.assertTrue(payloads[0]['pending']);self.assertEqual(payloads[1]['items'][0]['detail'],'Fato persistido')
        self.assertEqual(payloads[0]['requestId'],payloads[1]['requestId'])

    async def test_cancelled_tool_closes_pending_visual(self):
        import asyncio
        from types import SimpleNamespace
        from unittest.mock import AsyncMock
        runner=self.runner();runner._execute_tool_body=AsyncMock(side_effect=asyncio.CancelledError)
        with self.assertRaises(asyncio.CancelledError):await runner._execute_tool(SimpleNamespace(id='cancel',name='recall_memory',args={}))
        self.assertFalse(runner.ui.show_neural_memory.call_args.args[0]['active'])
        self.assertEqual(runner._tools_inflight,0)

    async def test_model_and_projection_receive_the_same_filtered_evidence(self):
        import main,json
        from types import SimpleNamespace
        from unittest.mock import AsyncMock
        runner=self.runner();runner._application_context.observe_user('Busque nas lembrancas sobre Atlas')
        data={'ok':True,'items':[{'id':'atlas','detail':'Atlas deve usar SQLite.'},{'id':'orion','detail':'Orion deve tocar musica.'}]}
        response=main.types.FunctionResponse(id='same',name='recall_memory',response={'result':json.dumps(data)})
        runner._execute_tool_body=AsyncMock(return_value=response)
        returned=await runner._execute_tool(SimpleNamespace(id='same',name='recall_memory',args={'query':'Atlas'}))
        self.assertEqual([item['id'] for item in json.loads(returned.response['result'])['items']],['atlas'])
        self.assertEqual([item['id'] for item in runner.ui.show_neural_memory.call_args.args[0]['items']],['atlas'])

    async def test_late_retrieval_cannot_cross_a_new_session(self):
        import main
        from types import SimpleNamespace
        runner=self.runner();runner.session=object()
        async def body(_):
            runner.session=object()
            return main.types.FunctionResponse(id='old',name='recall_memory',response={'result':{'ok':True,'items':[{'id':'old','detail':'Atlas deve usar SQLite.'}]}})
        runner._execute_tool_body=body
        returned=await runner._execute_tool(SimpleNamespace(id='old',name='recall_memory',args={'query':'Atlas'}))
        self.assertTrue(returned.response['result']['cancelled'])
        self.assertFalse(runner.ui.show_neural_memory.call_args.args[0]['active'])


if __name__=='__main__':unittest.main()
