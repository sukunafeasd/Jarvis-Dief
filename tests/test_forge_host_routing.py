import asyncio,unittest,tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,AsyncMock,patch
from core.forge_commands import command_for
from core.pinned_scene_store import PinnedSceneStore

class CommandTests(unittest.TestCase):
    def test_conversation_and_hypotheticals_do_not_create_or_change_work(self):
        for text in ('bom dia Jarvis','obrigado','voce esta me ouvindo?',
                     'o que voce acha dessa ideia?', 'voce consegue criar um jogo?',
                     'como funciona para salvar na biblioteca?', 'consegue salvar um site?',
                     'e se a gente criar outro projeto?', 'nao crie nada agora',
                     'me explique como alterar o planeta', 'como esta sua voz?',
                     'estou pensando em criar outro projeto', 'preciso conversar com voce',
                     'quero uma opiniao','quero um conselho','mude sua voz','aumente o volume'):
            with self.subTest(text=text):self.assertIsNone(command_for(text))

    def test_explicit_requests_and_status_remain_available(self):
        for text in ('crie um jogo','pode criar um site por favor',
                     'quero criar um planeta','quero um simulador','ajuste as cores'):
            with self.subTest(text=text):self.assertEqual(command_for(text)['action'],'steer')
        for text in ('como esta o projeto?', 'o que voce esta fazendo?', 'qual o progresso?'):
            self.assertEqual(command_for(text)['action'],'status')
    def test_adjustment_stays_in_same_project(self):
        self.assertEqual(command_for('diminua os aneis 30%')['action'],'steer')
        self.assertEqual(command_for('para')['action'],'stop_speech')
        self.assertEqual(command_for('cancele essa criacao')['action'],'cancel')
        self.assertEqual(command_for('salve na biblioteca como Reator')['name'],'Reator')
        self.assertEqual(command_for('crie outro projeto chamado Reator')['action'],'create')
        self.assertEqual(command_for('crie outro projeto chamado Reator')['name'],'Reator')

    def test_saved_artifact_identity_is_checked(self):
        store=PinnedSceneStore(Path(tempfile.gettempdir()))
        item={'key':'forge:'+'a'*32,'data':{'kind':'forge_artifact','artifact_id':'a'*32},'slot':1}
        self.assertEqual(store.validate([item]),[item])
        item['data']['artifact_id']='../host'
        with self.assertRaises(ValueError):store.validate([item])

class RoutingTests(unittest.IsolatedAsyncioTestCase):
    async def test_native_protocol_voice_waits_for_original_turn(self):
        from main import JarvisLive
        owner=JarvisLive.__new__(JarvisLive)
        owner.ui=SimpleNamespace(write_log=Mock());owner._fish_voice=None
        owner.session=SimpleNamespace(send_client_content=AsyncMock())
        owner._routing_protocol_input=True;owner._server_turn_open=False
        with patch('core.fish_audio.selected',return_value=False):
            await owner._speak_protocol('Modo Forja ativo, senhor.')
        owner.session.send_client_content.assert_not_awaited()
        owner._protocol_input_consumed=True;owner._routing_protocol_input=False
        with patch('core.fish_audio.selected',return_value=False):await owner._flush_protocol_voice()
        self.assertFalse(owner._protocol_input_consumed)
        owner.session.send_client_content.assert_awaited_once()
        self.assertEqual(owner._native_protocol_messages,[])

    async def test_clean_voice_selection_never_uses_native_protocol_fallback(self):
        from main import JarvisLive
        owner=JarvisLive.__new__(JarvisLive);owner.ui=SimpleNamespace(write_log=Mock())
        owner._fish_voice=None;owner.session=SimpleNamespace(send_client_content=AsyncMock())
        with patch('core.fish_audio.selected',return_value=True):await owner._speak_protocol('Teste')
        owner.session.send_client_content.assert_not_awaited()

    def owner(self):
        from main import JarvisLive
        owner=JarvisLive.__new__(JarvisLive);owner._forge_mode=False
        owner._speak_protocol=AsyncMock();owner._dispatch_forge=AsyncMock()
        owner.ui=SimpleNamespace(_win=SimpleNamespace(_forge_runtime=None,_ultron_runtime=None),control_forge=Mock(return_value={'ok':True}),write_log=Mock(),forge_runtime=Mock())
        owner.ui.forge_runtime.status.return_value={'connected':False}
        return owner

    async def test_ready_scene_is_required_before_welcome(self):
        owner=self.owner()
        self.assertTrue(await owner._route_protocol_user('ativar modo Forja'))
        owner.ui.control_forge.assert_called_once_with('enter')
        owner._speak_protocol.assert_awaited_once_with('Modo Forja ativo, senhor. O que deseja criar?')
        self.assertTrue(owner._forge_mode)

    async def test_failed_scene_restores_routing(self):
        owner=self.owner();owner.ui.control_forge.return_value={'ok':False,'error':'synthetic failure'}
        await owner._route_protocol_user('entrar na Forja')
        self.assertFalse(owner._forge_mode)
        owner._speak_protocol.assert_awaited_once_with('synthetic failure')

    async def test_ultron_activation_uses_actual_host_text(self):
        owner=self.owner()
        with patch('actions.ultron_protocol.ultron_protocol',return_value='{"speech":"Iniciado","accepted":true}') as call:
            await owner._route_protocol_user('Jarvis, pode ativar o protocolo ultron?')
        self.assertEqual(call.call_args.args[0]['command'],'Jarvis, pode ativar o protocolo ultron?')

    async def test_adjustment_goes_to_forge_not_native_tools(self):
        owner=self.owner();owner._forge_mode=True
        self.assertTrue(await owner._route_protocol_user('diminua os aneis 30%'))
        owner._dispatch_forge.assert_awaited_once_with({'action':'steer','prompt':'diminua os aneis 30%'})

    async def test_conversation_in_forge_returns_to_normal_jarvis(self):
        owner=self.owner();owner._forge_mode=True
        for text in ('voce esta me ouvindo?', 'voce consegue criar um jogo?', 'nao crie nada ainda'):
            self.assertFalse(await owner._route_protocol_user(text))
        owner._dispatch_forge.assert_not_awaited()
        self.assertTrue(owner._forge_mode)

    async def test_negated_and_explanatory_open_do_not_change_project(self):
        owner=self.owner();owner._forge_mode=True
        owner.ui.forge_runtime.command.return_value={'projects':[{'id':'saved-project','name':'Reator'}]}
        for text in ('nao abra o projeto Reator','como faco para abrir o projeto Reator?'):
            self.assertFalse(await owner._route_protocol_user(text))
        owner._dispatch_forge.assert_not_awaited()
        owner.ui.forge_runtime.command.assert_not_called()
        self.assertTrue(await owner._route_protocol_user('Jarvis, abra o projeto Reator'))
        owner._dispatch_forge.assert_awaited_once_with({'action':'open','project_id':'saved-project'})

    async def test_yes_without_pending_approval_is_conversation(self):
        owner=self.owner();owner._forge_mode=True
        owner.ui.forge_runtime.snapshot.return_value={'request':None,'project':{'id':'existing'}}
        self.assertFalse(await owner._route_protocol_user('sim'))
        owner._dispatch_forge.assert_not_awaited()
        owner.ui.forge_runtime.snapshot.return_value={'request':{'id':'pending'}}
        self.assertTrue(await owner._route_protocol_user('sim'))
        owner._dispatch_forge.assert_awaited_once_with({'action':'approve','decision':True})

    async def test_same_recorded_turn_cannot_restart_work(self):
        owner=self.owner();owner._forge_mode=True
        owner.ui.ultron_user_context=lambda:{'serial':7,'text':'crie um planeta'}
        await owner._route_protocol_user('crie um planeta')
        await owner._route_protocol_user('crie um planeta')
        owner._dispatch_forge.assert_awaited_once()
        owner.ui.ultron_user_context=lambda:{'serial':8,'text':'crie um planeta'}
        await owner._route_protocol_user('crie um planeta')
        self.assertEqual(owner._dispatch_forge.await_count,2)

    async def test_route_failure_does_not_reconnect_voice_or_retry(self):
        owner=self.owner();owner._forge_mode=True
        owner._dispatch_forge.side_effect=TimeoutError('delivery unclear')
        self.assertTrue(await owner._route_protocol_user('ajuste o planeta'))
        owner._speak_protocol.assert_awaited_once()

    async def test_running_project_cancelled_before_scene_exit(self):
        owner=self.owner();owner._forge_mode=True
        runtime=Mock();runtime.snapshot.return_value={'phase':'running','project':{'id':'x'}}
        runtime.command.return_value={'accepted':True};owner.ui._win._forge_runtime=runtime
        await owner._route_protocol_user('sair da Forja')
        runtime.command.assert_called_once_with('cancel')
        self.assertFalse(owner._forge_mode)
