"""Background results must not interrupt a newer foreground activity."""
import asyncio
import time
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock,Mock,patch
from main import JarvisLive


def owner():
    assistant=JarvisLive.__new__(JarvisLive)
    assistant.session=SimpleNamespace(send_client_content=AsyncMock())
    assistant.ui=Mock();assistant.ui.muted=False
    assistant._awake=True;assistant._manual_rest=False
    assistant._last_user_speech=0.
    assistant._response_busy=Mock(return_value=False)
    assistant._send_host_notice=AsyncMock(return_value=True)
    return assistant


def ticks(count=1):
    calls=0
    async def sleep(_):
        nonlocal calls
        calls+=1
        if calls>count:raise asyncio.CancelledError()
    return sleep


class BackgroundModeTests(unittest.IsolatedAsyncioTestCase):
    async def test_scheduled_background_notice_rechecks_mode_at_delivery(self):
        for mode in ('phone','mute','ultron','contact','session'):
            with self.subTest(mode=mode):
                assistant=owner();session=assistant.session
                self.assertTrue(assistant._background_ready())
                delivery=JarvisLive._send_host_notice(assistant,session,'Aviso sintetico',background=(20,0.))
                if mode=='phone':assistant._phone_active=True
                elif mode=='mute':assistant.ui.muted=True
                elif mode=='ultron':assistant.ui._win._ultron_payload={'state':{'phase':'scanning'}}
                elif mode=='contact':assistant._last_user_speech=time.monotonic()
                else:assistant.session=object()
                self.assertIsNone(await delivery)
                session.send_client_content.assert_not_awaited()

    async def test_explicit_protocol_notice_is_not_blocked_by_background_policy(self):
        assistant=owner();assistant._turn_done_event=None
        assistant.ui._win._ultron_payload={'state':{'phase':'scanning'}}
        result=await JarvisLive._send_host_notice(assistant,assistant.session,'Resultado do protocolo')
        self.assertTrue(result)
        assistant.session.send_client_content.assert_awaited_once()

    async def test_guard_respects_voice_generation_modes_and_session(self):
        assistant=owner()
        self.assertTrue(assistant._background_ready())
        for attribute in ('_forge_mode','_refresh_in_progress','_phone_active','_manual_rest'):
            setattr(assistant,attribute,True)
            self.assertFalse(assistant._background_ready(),attribute)
            setattr(assistant,attribute,False)
        assistant._response_busy.return_value=True
        self.assertFalse(assistant._background_ready())
        assistant._response_busy.return_value=False
        self.assertFalse(assistant._background_ready(session=object()))
        assistant.ui._win._ultron_payload={'state':{'phase':'scanning'}}
        self.assertFalse(assistant._background_ready())

    async def test_system_sample_error_does_not_take_down_session(self):
        assistant=owner();assistant._sys_monitor=Mock()
        assistant._sys_monitor.check.side_effect=OSError('Synthetic unavailable sensor')
        session=assistant.session
        with patch('main.asyncio.sleep',side_effect=ticks(2)):
            with self.assertRaises(asyncio.CancelledError):await assistant._run_system_monitor()
        self.assertEqual(assistant._sys_monitor.check.call_count,2)
        self.assertIs(assistant.session,session)
        assistant._send_host_notice.assert_not_awaited()

    async def test_system_alert_is_discarded_if_user_starts_new_request(self):
        assistant=owner();assistant._sys_monitor=Mock()
        def check():assistant._last_user_speech=time.monotonic();return 'CPU alta'
        assistant._sys_monitor.check.side_effect=check
        with patch('main.asyncio.sleep',side_effect=ticks()):
            with self.assertRaises(asyncio.CancelledError):await assistant._run_system_monitor()
        assistant._send_host_notice.assert_not_awaited()

    async def test_system_does_not_poll_while_forge_is_active(self):
        assistant=owner();assistant._forge_mode=True;assistant._sys_monitor=Mock()
        with patch('main.asyncio.sleep',side_effect=ticks()):
            with self.assertRaises(asyncio.CancelledError):await assistant._run_system_monitor()
        assistant._sys_monitor.check.assert_not_called()

    async def test_topic_monitor_never_sends_result_into_replacement_session(self):
        assistant=owner()
        def check():assistant.session=SimpleNamespace(send_client_content=AsyncMock());return ['Aviso antigo']
        with patch('main.monitor_check_all',side_effect=check),patch('main.asyncio.sleep',side_effect=ticks()):
            with self.assertRaises(asyncio.CancelledError):await assistant._run_background_monitor()
        assistant._send_host_notice.assert_not_awaited()

    async def test_proactive_cooldown_only_after_accepted_notice(self):
        assistant=owner();assistant._proactive=Mock();assistant._session_log=[]
        assistant._proactive.build_prompt.return_value='Prompt sintetico'
        assistant._send_host_notice.return_value=None
        with patch('main.asyncio.sleep',side_effect=ticks()),patch('main.load_memory',return_value={}),patch('main.list_monitors',return_value=[]):
            with self.assertRaises(asyncio.CancelledError):await assistant._run_proactive_mode()
        assistant._proactive.mark_triggered.assert_not_called()

    async def test_routine_result_disabled_during_query_is_not_projected(self):
        assistant=owner()
        with patch('main.asyncio.sleep',side_effect=ticks()),patch('memory.config_manager.get_plugin_enabled',side_effect=[True,False]),patch('core.personal_routines.poll',return_value={'title':'Rotina sintetica'}):
            with self.assertRaises(asyncio.CancelledError):await assistant._run_personal_routines()
        assistant.ui.show_manifestation.assert_not_called()
