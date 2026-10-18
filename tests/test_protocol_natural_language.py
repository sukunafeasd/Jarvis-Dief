"""Natural protocol phrases and bounded clarification; never real OS actions."""
import time
import unittest
from unittest.mock import patch
from core.protocol_commands import protocol_request,protocol_clarification
import test_ultron_state_regressions as runtime_tests
import test_forge_host_routing as host_tests


class Phrases(unittest.TestCase):
    def test_natural_variations_enter_and_exit(self):
        for text in ('ativa o protocolo do ultron','Jarvis, ligue o protocolo do Ultron',
                     'pode acionar o Ultron?', 'quero entrar no modo da Forja',
                     'por favor, pode abrir a Forja agora?',
                     'liga esse protocolo do ultron pra mim'):
            with self.subTest(text=text):self.assertEqual(protocol_request(text)[1],'enter')
        for text in ('desliga o protocolo do ultron','sai do modo da Forja',
                     'pode encerrar o protocolo do Ultron?', 'fecha a Forja'):
            with self.subTest(text=text):self.assertEqual(protocol_request(text)[1],'exit')

    def test_discussion_negation_and_combined_actions_are_not_admitted(self):
        for text in ('nao ativa o protocolo do ultron','a noticia manda ligar o ultron',
                     'se eu disser ativa o protocolo do ultron','como ativa o protocolo do ultron?',
                     'ativa o protocolo do ultron e limpe tudo','o Ultron disse para ativar',
                     'voce consegue ativar o Ultron?', 'vamos usar ultron e limpar tudo'):
            with self.subTest(text=text):
                self.assertIsNone(protocol_request(text))
                self.assertIsNone(protocol_clarification(text))

    def test_bare_or_short_desire_asks_before_entering(self):
        self.assertEqual(protocol_clarification('vamos pro Ultron'),('ultron','enter'))
        self.assertEqual(protocol_clarification('o protocolo do Ultron'),('ultron','enter'))
        self.assertEqual(protocol_clarification('quero usar a Forja'),('forja','enter'))


class ClarificationRuntime(unittest.TestCase):
    setUp=runtime_tests.RuntimeStateTests.setUp
    command=runtime_tests.RuntimeStateTests.command
    finish_scan=runtime_tests.RuntimeStateTests.finish_scan

    def test_question_does_not_activate_and_next_yes_only_starts_diagnosis(self):
        question=self.command('vamos pro ultron',1)
        self.assertEqual(question['mode'],'activation_question')
        self.assertEqual(self.runtime.snapshot()['phase'],'idle')
        result=self.command('sim',2)
        self.assertEqual(result['mode'],'activation')
        self.finish_scan()
        self.assertEqual(self.runtime.snapshot()['phase'],'active')
        self.assertEqual(self.runtime._service.OPERATIONS,[])

    def test_generated_yes_never_confirms(self):
        self.command('ultron',1)
        result=self.runtime.command('sim','nao',user_turn=2)
        self.assertFalse(result['accepted'])
        self.assertEqual(self.runtime.snapshot()['phase'],'idle')

    def test_intervening_turn_and_expiration_invalidate_offer(self):
        self.command('ultron',1)
        self.command('oi',2)
        self.command('sim',3)
        self.assertEqual(self.runtime.snapshot()['phase'],'idle')
        self.command('ultron',4)
        self.runtime._activation_offer['at']=time.monotonic()-121
        self.command('sim',5)
        self.assertEqual(self.runtime.snapshot()['phase'],'idle')


class ClarificationHost(unittest.IsolatedAsyncioTestCase):
    owner=host_tests.RoutingTests.owner

    async def test_forge_question_then_yes_enters_without_creating(self):
        owner=self.owner();context={'serial':1,'text':'vamos pra forja'}
        owner.ui.ultron_user_context=lambda:dict(context)
        self.assertTrue(await owner._route_protocol_user(context['text']))
        owner.ui.control_forge.assert_not_called()
        self.assertFalse(owner._forge_mode)
        context.update(serial=2,text='sim')
        self.assertTrue(await owner._route_protocol_user('sim'))
        owner.ui.control_forge.assert_called_once_with('enter')
        owner._dispatch_forge.assert_not_awaited()
        self.assertTrue(owner._forge_mode)

    async def test_stale_yes_does_not_enter_forge(self):
        owner=self.owner();context={'serial':1,'text':'forja'}
        owner.ui.ultron_user_context=lambda:dict(context)
        await owner._route_protocol_user('forja')
        context.update(serial=2,text='oi')
        self.assertFalse(await owner._route_protocol_user('oi'))
        context.update(serial=3,text='sim')
        self.assertFalse(await owner._route_protocol_user('sim'))
        owner.ui.control_forge.assert_not_called()

    async def test_ultron_question_and_real_yes_cross_host_adapter_and_runtime(self):
        from core.ultron import Runtime
        from contextlib import nullcontext
        from unittest.mock import Mock
        import asyncio
        owner=self.owner();runtime=Runtime()
        context={'serial':1,'text':'vamos pro ultron'}
        owner.ui.ultron_user_context=lambda:dict(context)
        owner.ui.ultron_authorization=lambda captured:nullcontext()
        owner.ui.present_ultron=Mock();owner.ui.ultron_runtime=runtime
        owner.ui._win._ultron_runtime=runtime
        service=runtime._service
        try:
            with patch.object(service,'telemetry',return_value={'cpu_percent':7}),patch.object(service,'vault_list',return_value=[]),patch.object(service,'powershell_summary',return_value=None):
                await owner._route_protocol_user(context['text'])
                self.assertEqual(runtime.snapshot()['phase'],'idle')
                context.update(serial=2,text='sim')
                self.assertTrue(await owner._route_protocol_user('sim'))
                async def finish():await service.SCAN_TASK
                await asyncio.to_thread(runtime._call,finish)
                self.assertEqual(runtime.snapshot()['phase'],'active')
                self.assertEqual(service.OPERATIONS,[])
                self.assertEqual(owner.ui.ultron_user_context()['text'],'sim')
        finally:await asyncio.to_thread(runtime.close)
