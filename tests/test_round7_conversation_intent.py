"""Keep ambiguous speech in conversation and avoid redundant style injection."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch,Mock,AsyncMock
from types import SimpleNamespace

from core import personality
from core.forge_commands import command_for
import test_forge_host_routing as host_tests


class ConversationIntent(unittest.TestCase):
    def test_explicit_refusals_still_deny_pending_approval(self):
        for text in ('nao','nao faca','nao execute'):
            self.assertEqual(command_for(text),{'action':'approve','decision':False})

    def test_self_knowledge_includes_actual_neural_and_ultron_sources(self):
        from core.system_knowledge import component_outline,system_catalog
        for name in ('ultron','neural_memory'):
            self.assertIn(name,system_catalog()['components'])
            self.assertTrue(component_outline(name)['symbols'])

    def test_questions_host_actions_and_corrections_do_not_dispatch_projects(self):
        examples=(
            'faca uma pergunta', 'pode fazer uma piada?', 'crie um backup da pasta C:\\Projetos',
            'faca uma varredura', 'salve isso na memoria', 'guarde minha preferencia',
            'crie um site, na verdade quero conversar primeiro',
            'mude a cor, pensando melhor deixe como esta',
            'crie um jogo, o que voce acha?', 'faca isso', 'remova aquilo',
            'salve isso por favor', 'crie um site mas nao execute agora',
        )
        for text in examples:
            with self.subTest(text=text):self.assertIsNone(command_for(text))

    def test_explicit_project_work_remains_direct(self):
        for text in ('crie um jogo de perguntas', 'adicione um botao de backup',
                     'crie um site com uma pagina de opiniao', 'mude a cor do planeta',
                     'salve na biblioteca como Orbita'):
            with self.subTest(text=text):self.assertIsNotNone(command_for(text))

    def test_profile_sync_only_when_style_changes_but_keeps_turn_history(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(personality,'path',return_value=Path(folder)/'personality.json'):
            self.assertFalse(personality.observe('Como esta o projeto?',1)['changed'])
            self.assertTrue(personality.observe('Prefiro respostas curtas.',2)['changed'])
            self.assertFalse(personality.observe('Prefiro respostas curtas.',3)['changed'])
            self.assertFalse(personality.observe('Obrigado.',4)['changed'])
            self.assertTrue(personality.observe('Me chame de Ana.',5)['changed'])
            self.assertFalse(personality.observe('Me chame de Ana.',6)['changed'])
            state=personality.snapshot()
            self.assertEqual(state['turns'],6)
            self.assertEqual(state['revision'],6)
            self.assertEqual(state['address'],'Ana')
            self.assertFalse(personality.observe('Seja mais formal.',6)['changed'])
            self.assertEqual(personality.snapshot()['turns'],6)


class HostConversation(unittest.IsolatedAsyncioTestCase):
    owner=host_tests.RoutingTests.owner

    async def test_forge_allows_self_knowledge_and_style_but_not_parallel_execution(self):
        owner=self.owner();owner._forge_mode=True
        owner.ui.operation_event=Mock()
        owner._application_context=SimpleNamespace(tool_retry_check=Mock(return_value=''),record_tool_result=Mock())
        owner._sync_activity_state=Mock()
        for name in ('system_knowledge','personality_control'):
            owner._execute_tool_body=AsyncMock(return_value=SimpleNamespace(response={'result':{'ok':True}}))
            call=SimpleNamespace(name=name,id='test-'+name,args={'action':'inspect'})
            result=await owner._execute_tool(call)
            self.assertTrue(result.response['result']['ok'])
            owner._execute_tool_body.assert_awaited_once_with(call)
        owner._execute_tool_body.reset_mock()
        result=await owner._execute_tool(SimpleNamespace(name='powershell_control',id='blocked',args={'action':'execute'}))
        self.assertFalse(result.response['result']['ok'])
        owner._execute_tool_body.assert_not_awaited()

    async def test_refusal_reaches_pending_forge_request(self):
        for text in ('nao faca','nao execute'):
            owner=self.owner();owner._forge_mode=True
            owner.ui.forge_runtime.snapshot.return_value={'request':{'id':'pending'}}
            self.assertTrue(await owner._route_protocol_user(text))
            owner._dispatch_forge.assert_awaited_once_with({'action':'approve','decision':False})

    async def test_forge_gives_ambiguous_turns_back_to_model(self):
        owner=self.owner();owner._forge_mode=True
        for text in ('faca uma pergunta','faca isso','salve isso na memoria',
                     'crie um jogo, na verdade quero sua opiniao primeiro'):
            with self.subTest(text=text):self.assertFalse(await owner._route_protocol_user(text))
        owner._dispatch_forge.assert_not_awaited()
        owner.ui.control_forge.assert_not_called()


if __name__=='__main__':unittest.main()
