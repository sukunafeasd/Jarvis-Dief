import json
import subprocess
import sys
import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch
from memory import memory_manager as mm
from actions.memory_control import memory_control
from actions.system_knowledge import system_knowledge
from core.system_knowledge import component_outline,system_catalog,SETTINGS_PAGES
from core.action_loader import _call_handler
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')


class PersistentMemoryTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory()
        self.path=Path(self.folder.name)/'memory.json'
        self.patcher=patch.object(mm,'MEMORY_PATH',self.path);self.patcher.start()

    def tearDown(self):
        self.patcher.stop();self.folder.cleanup()

    def test_accented_question_retrieves_older_fact(self):
        mm.remember('materia','Matemática e ciências','preferences')
        result=json.loads(memory_control({'action':'list','query':'Voce lembra minha matematica?'}))
        self.assertTrue(result['ok']);self.assertEqual(result['items'][0]['id'],'preferences/materia')
        self.assertIn('Matemática',mm.search_memory('matematica'))

    def test_portuguese_identity_query_matches_legacy_english_key(self):
        mm.remember('name','Pessoa de teste','identity')
        self.assertIn('Pessoa de teste',mm.search_memory('Qual meu nome?'))
        self.assertIn('Pessoa de teste',mm.search_memory('O que voce lembra sobre mim?'))

    def test_read_id_ignores_unrelated_filter(self):
        mm.remember('teste','Fato de teste')
        result=json.loads(memory_control({'action':'read','id':'notes/teste','query':'outro assunto'}))
        self.assertTrue(result['ok']);self.assertEqual(result['items'][0]['detail'],'Fato de teste')

    def test_capacity_never_erases_old_facts(self):
        mm.remember('antigo','Preservar')
        before=self.path.read_bytes()
        with patch.object(mm,'MEMORY_MAX_CHARS',30),self.assertRaises(ValueError):
            mm.remember('novo','Nao cabe')
        self.assertEqual(before,self.path.read_bytes())

    def test_concurrent_fact_and_summary_updates(self):
        def write(index):
            mm.remember('item_'+str(index),'Fato '+str(index))
            mm.save_session_summary('Resumo '+str(index))
        with ThreadPoolExecutor(max_workers=5) as pool:list(pool.map(write,range(20)))
        stored=mm.load_memory(strict=True)
        self.assertEqual(len(stored['notes']),20);self.assertEqual(len(stored['sessions']),12)
        self.assertEqual(list(self.path.parent.glob('*.tmp')),[])

    def test_presenting_summary_preserves_history(self):
        mm.save_session_summary('Resumo de teste')
        mm.save_session_summary('Resumo de teste')
        self.assertEqual(mm.pop_last_session()['summary'],'Resumo de teste')
        self.assertIsNone(mm.pop_last_session())
        self.assertEqual(len(mm.load_memory()['sessions']),1)

    def test_corrupt_store_not_overwritten_by_summary_or_forget(self):
        self.path.write_text('{"notes": [], "sessions": []}',encoding='utf-8')
        before=self.path.read_bytes()
        for operation in (lambda:mm.save_session_summary('Teste'),lambda:mm.forget('teste')):
            with self.assertRaises(ValueError):operation()
        self.assertEqual(before,self.path.read_bytes())

    def test_secret_and_invalid_schema_are_rejected(self):
        for key,value in [('api_key','segredo'),('teste','sk-'+ 'a'*24),('../arquivo','teste')]:
            with self.assertRaises(ValueError):mm.remember(key,value)
        with self.assertRaises(ValueError):mm.save_session_summary('sk-'+ 'a'*24)
        self.assertFalse(self.path.exists())

    def test_new_process_can_recall_without_provider_credentials(self):
        mm.remember('projeto','Projeto de teste duravel','projects')
        script="from pathlib import Path;import sys;from memory import memory_manager as m;m.MEMORY_PATH=Path(sys.argv[1]);assert 'Projeto de teste duravel' in m.search_memory('projeto')"
        for _ in range(2):
            result=subprocess.run([sys.executable,'-c',script,str(self.path)],cwd=str(Path(__file__).resolve().parents[1]),capture_output=True,timeout=10)
            self.assertEqual(result.returncode,0,result.stderr.decode(errors='replace'))


class SystemKnowledgeTests(unittest.TestCase):
    def test_failed_actions_stop_repeating_until_new_user_request(self):
        from core.application_context import ApplicationContext
        context=ApplicationContext()
        arguments={'action':'invoke','control_id':'real-control'}
        context.record_tool_result('app_control',arguments,{'ok':False})
        self.assertEqual(context.tool_retry_check('app_control',arguments),'')
        context.record_tool_result('app_control',arguments,{'ok':False})
        self.assertTrue(context.tool_retry_check('app_control',arguments))
        self.assertEqual(context.tool_retry_check('app_control',{'action':'inspect'}),'')
        context.observe_user('Tente novamente depois de abrir o aplicativo')
        self.assertEqual(context.tool_retry_check('app_control',arguments),'')

    def test_uncertain_action_blocks_retry_immediately(self):
        from core.application_context import ApplicationContext
        context=ApplicationContext()
        context.record_tool_result('teste',{}, {'ok':False,'uncertain':True})
        self.assertTrue(context.tool_retry_check('teste',{}))
    def test_catalog_distinguishes_availability_from_connection(self):
        result=system_catalog([{'name':'gmail_control','parameters':{}}])
        self.assertTrue(result['panel']['domains']['gmail']['tool_available'])
        self.assertFalse(result['panel']['domains']['whatsapp']['tool_available'])
        self.assertIsNone(system_catalog()['panel']['domains']['gmail']['tool_available'])
        self.assertEqual(SETTINGS_PAGES['profile']['title'],'Perfil')

    def test_tool_schema_and_registry_context(self):
        declaration={'name':'teste','parameters':{'type':'OBJECT'}}
        result=json.loads(_call_handler(system_knowledge,{'action':'tool','target':'teste'},{'available_tools':[declaration]}))
        self.assertTrue(result['ok']);self.assertFalse(result['result']['connection_verified'])
        self.assertEqual(result['result']['declaration'],declaration)

    def test_component_is_real_paginated_and_allowlisted(self):
        result=component_outline('memory',limit=2)
        self.assertEqual(len(result['symbols']),2);self.assertEqual(result['next_offset'],2)
        self.assertIn('get_base_dir',[item['name'] for item in result['symbols']])
        for target in ('../../config/api_keys.json','config','unknown'):
            with self.assertRaises(ValueError):component_outline(target)

    def test_runtime_uses_actual_interface_and_preserves_failure(self):
        from unittest.mock import Mock
        ui=Mock();ui.control_interface.return_value={'ok':False,'error':'Expirado'}
        result=json.loads(system_knowledge({'action':'runtime'},player=ui))
        self.assertFalse(result['ok']);ui.control_interface.assert_called_once_with('inspect','','')


class ConversationIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_dispatcher_does_not_execute_third_identical_failure(self):
        from unittest.mock import AsyncMock,Mock
        from types import SimpleNamespace
        from core.application_context import ApplicationContext
        import main
        runner=main.JarvisLive.__new__(main.JarvisLive)
        runner.ui=Mock();runner._application_context=ApplicationContext()
        response=main.types.FunctionResponse(id='1',name='teste',response={'result':{'ok':False,'error':'Sem controle'}})
        runner._execute_tool_body=AsyncMock(return_value=response)
        call=SimpleNamespace(id='1',name='teste',args={'action':'invoke'})
        await runner._execute_tool(call);await runner._execute_tool(call)
        blocked=await runner._execute_tool(call)
        self.assertTrue(blocked.response['result']['retry_blocked'])
        self.assertEqual(runner._execute_tool_body.await_count,2)

    async def test_failed_summary_restores_conversation_log(self):
        import main
        runner=main.JarvisLive.__new__(main.JarvisLive)
        runner._session_log=['user:teste','assistant:teste','user:continuar']
        before=list(runner._session_log)
        with patch('core.gemini.text',return_value=None):
            await runner._save_session_summary()
        self.assertEqual(runner._session_log,before)
