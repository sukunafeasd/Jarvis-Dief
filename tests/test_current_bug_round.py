import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import Mock,AsyncMock
from core.presentation_clock import PresentationClock
from main import JarvisLive
import test_scene


class TimelineTests(unittest.TestCase):
    def test_due_pcm_anchor_supersedes_older_estimate_without_late_topic(self):
        clock=PresentationClock()
        clock.enqueue('Introducao com muitas palavras para durar varios segundos')
        clock.advance(.1)
        clock.enqueue('Assunto antigo estimado')
        clock.enqueue('Assunto novo realmente falado',at=1,duration=.3)
        self.assertEqual(clock.advance(.9)['cues'],['Assunto novo realmente falado'])
        self.assertEqual(clock.advance(10)['cues'],[])


class HostNoticeTests(unittest.IsolatedAsyncioTestCase):
    async def test_finished_silent_tool_reconciles_only_after_counter_decrements(self):
        owner=JarvisLive.__new__(JarvisLive)
        owner.ui=Mock();owner.ui.muted=False
        owner._manual_rest=False;owner._is_speaking=False
        owner._application_context=Mock();owner._application_context.tool_retry_check.return_value=None
        owner._execute_tool_body=AsyncMock(return_value=SimpleNamespace(response={'result':{'ok':True}}))
        await owner._execute_tool(SimpleNamespace(name='task_execution',id='tool',args={}))
        self.assertEqual(owner._tools_inflight,0)
        self.assertEqual(owner.ui.set_state.call_args.args[0],'LISTENING')
        owner._is_speaking=True
        await owner._execute_tool(SimpleNamespace(name='task_execution',id='another',args={}))
        self.assertEqual(owner.ui.set_state.call_args.args[0],'SPEAKING')

    async def test_explicit_host_request_reopens_only_after_local_turn(self):
        owner=JarvisLive.__new__(JarvisLive)
        owner.session=SimpleNamespace(send_client_content=AsyncMock())
        owner._manual_rest=False;owner._protocol_input_consumed=True
        owner._turn_done_event=asyncio.Event();owner._turn_done_event.set()
        owner._response_busy=Mock(return_value=False)
        await owner._send_host_notice(owner.session,'Informe o diagnostico concluido')
        self.assertFalse(owner._protocol_input_consumed)
        self.assertTrue(owner._server_turn_open)
        owner.session.send_client_content.assert_awaited_once()

    async def test_notice_does_not_enter_replacement_session(self):
        owner=JarvisLive.__new__(JarvisLive)
        owner.session=SimpleNamespace(send_client_content=AsyncMock())
        owner._manual_rest=False
        await owner._send_host_notice(object(),'Aviso antigo')
        owner.session.send_client_content.assert_not_awaited()


class NativeStateTests(unittest.TestCase):
    setUpClass=classmethod(test_scene.SceneTests.setUpClass.__func__)
    setUp=test_scene.SceneTests.setUp
    tearDown=test_scene.SceneTests.tearDown
    command=test_scene.SceneTests.command

    def test_minimized_window_keeps_available_content_without_claiming_visibility(self):
        self.window._show_manifestation({'kind':'weather','city':'Recife','temperature':25})
        self.window.showMinimized();self.app.processEvents()
        snapshot=self.window.interface_snapshot()
        self.assertFalse(snapshot['observation']['has_visible_content'])
        self.assertFalse(snapshot['observation']['window_visible'])

    def test_updating_one_symbol_preserves_other_symbol_cue(self):
        from core.visual_scene import VisualSceneController
        scene=VisualSceneController(self.window)
        scene.apply({'action':'compose','elements':[{'id':'a','text':'Primeiro','cue':'primeiro'},
                                                   {'id':'b','text':'Segundo','cue':'segundo'}]})
        scene.clock.elapsed=1.
        scene.pending_cues=[{'id':'b','at':2.}]
        scene.apply({'action':'update','id':'a','text':'Primeiro atualizado'})
        self.assertEqual(scene.pending_cues,[{'id':'b','at':2.}])
        self.assertEqual(scene.clock.elapsed,1.)
        scene.clear_all();scene.layer.deleteLater()

    def test_live_pin_refresh_does_not_replace_active_speech_or_recreate_pin(self):
        from core.live_pins import specification
        self.window._show_manifestation({'kind':'system','cpu_percent':10,'ram_percent':20})
        self.command('pin')
        pin=self.window._pin_previews['system'];widget=pin['widget']
        self.window._show_manifestation({'kind':'tasks','items':[{'id':1,'title':'Teste'}],'count':1})
        presentation=self.window._presentation
        identity=(pin['live_token'],'fixture')
        self.window._live_pins.pending['system']=(identity,specification(pin['data']),0.)
        self.window._apply_live_pin({'key':'system','identity':identity,'model':{'kind':'system','cpu_percent':62,'ram_percent':25},
                                     'error':None,'updated_at':'2026-10-14T12:00:00Z'})
        self.assertIs(self.window._presentation,presentation)
        self.assertIs(self.window._pin_previews['system']['widget'],widget)
        self.assertEqual(pin['data']['cpu_percent'],62)

    def test_new_city_query_does_not_change_existing_weather_pin(self):
        self.window._show_manifestation({'kind':'weather','city':'Recife','temperature':25})
        self.command('pin')
        self.window._show_manifestation({'kind':'weather','city':'Manaus','temperature':30})
        self.assertEqual(self.window._pin_previews['weather']['data']['city'],'Recife')
        self.assertEqual(self.window._presentation['model']['city'],'Manaus')
