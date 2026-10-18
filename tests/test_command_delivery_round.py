"""Typed and authenticated remote input share local routing; no providers."""
import ast
import asyncio
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock,Mock,patch

from main import JarvisLive


def owner():
    assistant=JarvisLive.__new__(JarvisLive)
    assistant.session=SimpleNamespace(send_client_content=AsyncMock())
    assistant.ui=SimpleNamespace(write_log=Mock(),record_ultron_user=Mock(),control_interface=Mock(return_value={'ok':True}))
    assistant.ui.muted=False;assistant.ui.set_state=Mock()
    assistant._response_epoch=0;assistant._server_activity_serial=0;assistant._server_turn_open=False
    recorded={'serial':0,'text':''}
    def record(text):recorded.update(serial=recorded['serial']+1,text=text)
    assistant.ui.record_ultron_user.side_effect=record
    assistant.ui.ultron_user_context=lambda:dict(recorded)
    assistant._application_context=SimpleNamespace(observe_user=Mock())
    assistant._wake_enabled=False;assistant._awake=True;assistant._manual_rest=False
    assistant._is_speaking=False;assistant._protocol_input_consumed=True
    assistant._turn_done_event=asyncio.Event();assistant._turn_done_event.set()
    assistant._route_protocol_user=AsyncMock(return_value=False)
    assistant._remember_user_turn=AsyncMock()
    assistant._flush_protocol_voice=AsyncMock();assistant._queue_daily_briefing=Mock(return_value=False)
    assistant.interrupt=Mock()
    return assistant


class CommandDeliveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_slow_old_command_cannot_follow_a_newer_turn(self):
        assistant=owner();started=asyncio.Event();release=asyncio.Event()
        async def route(text):
            if text=='pedido antigo':
                started.set();await release.wait()
            return False
        assistant._route_protocol_user.side_effect=route
        with patch('main.time',SimpleNamespace(monotonic=lambda:100.)):
            old=asyncio.create_task(assistant._handle_text_command('pedido antigo'))
            await started.wait()
            await assistant._handle_text_command('pedido novo',remote=True)
            release.set()
            self.assertFalse(await old)
        assistant.session.send_client_content.assert_awaited_once()
        sent=assistant.session.send_client_content.call_args.kwargs['turns']['parts'][0]['text']
        self.assertEqual(sent,'pedido novo')
        assistant._queue_daily_briefing.assert_called_once_with(wait_for_turn=True)

    async def test_remote_protocol_command_never_falls_through_to_model(self):
        assistant=owner();assistant._route_protocol_user.return_value=True
        self.assertTrue(await assistant._handle_text_command('ativar protocolo ultron',remote=True))
        assistant.ui.record_ultron_user.assert_called_once_with('ativar protocolo ultron')
        assistant._route_protocol_user.assert_awaited_once_with('ativar protocolo ultron')
        assistant.session.send_client_content.assert_not_awaited()

    async def test_ordinary_remote_input_records_contact_and_resets_consumed_turn(self):
        assistant=owner();assistant._last_user_speech=0
        self.assertTrue(await assistant._handle_text_command('Como esta o dia?',remote=True))
        self.assertGreater(assistant._last_user_speech,0)
        self.assertFalse(assistant._protocol_input_consumed)
        self.assertFalse(assistant._turn_done_event.is_set())
        assistant._application_context.observe_user.assert_called_once_with('Como esta o dia?')
        assistant.session.send_client_content.assert_awaited_once()

    async def test_remote_refresh_respects_daily_transaction(self):
        assistant=owner();assistant._route_protocol_user.return_value=True
        await assistant._handle_text_command('atualize-se sobre o dia',remote=True)
        assistant._route_protocol_user.assert_awaited_once()
        assistant.session.send_client_content.assert_not_awaited()

    async def test_remote_new_request_can_interrupt_daily_summary_and_stop_is_local(self):
        assistant=owner();assistant._daily_briefing_task=SimpleNamespace(done=lambda:False)
        self.assertTrue(await assistant._handle_text_command('mostre o clima',remote=True))
        assistant._route_protocol_user.assert_awaited_once_with('mostre o clima')
        assistant.interrupt.assert_called_once()
        assistant.session.send_client_content.reset_mock()
        assistant._route_protocol_user.reset_mock()
        await assistant._handle_text_command('Jarvis, para!',remote=True)
        self.assertEqual(assistant.interrupt.call_count,2)
        assistant._route_protocol_user.assert_not_awaited()
        assistant.session.send_client_content.assert_not_awaited()

    async def test_stop_does_not_wake_sleeping_assistant_or_send_a_new_request(self):
        assistant=owner();assistant._wake_enabled=True;assistant._awake=False;assistant.wake=Mock()
        self.assertTrue(await assistant._handle_text_command('Jarvis, para!',remote=True))
        assistant.wake.assert_not_called();assistant.interrupt.assert_called_once()
        assistant._remember_user_turn.assert_not_awaited()
        assistant.session.send_client_content.assert_not_awaited()

    async def test_stop_invalidates_a_command_waiting_in_local_routing(self):
        assistant=owner();started=asyncio.Event();release=asyncio.Event()
        async def route(_):started.set();await release.wait();return False
        assistant._route_protocol_user.side_effect=route
        with patch('main.time',SimpleNamespace(monotonic=lambda:100.)):
            old=asyncio.create_task(assistant._handle_text_command('pedido antigo'))
            await started.wait()
            await assistant._handle_text_command('Jarvis, para!',remote=True)
            release.set();self.assertFalse(await old)
        assistant.session.send_client_content.assert_not_awaited()
        self.assertTrue(assistant._drop_prior_input)

    async def test_command_does_not_replay_into_replacement_session(self):
        assistant=owner();old=assistant.session
        async def route(_):
            assistant.session=SimpleNamespace(send_client_content=AsyncMock())
            return False
        assistant._route_protocol_user.side_effect=route
        self.assertFalse(await assistant._handle_text_command('pergunta sintetica'))
        old.send_client_content.assert_not_awaited()
        assistant.session.send_client_content.assert_not_awaited()

    async def test_remote_wakes_before_routing_but_desktop_respects_sleep_gate(self):
        assistant=owner();assistant._wake_enabled=True;assistant._awake=False
        def wake(**_):assistant._awake=True
        assistant.wake=Mock(side_effect=wake)
        self.assertFalse(await assistant._handle_text_command('teste'))
        assistant.wake.assert_not_called()
        self.assertTrue(await assistant._handle_text_command('teste',remote=True))
        assistant.wake.assert_called_once_with(reason='remote command')

    async def test_dashboard_delegates_to_same_handler(self):
        assistant=owner();queue=asyncio.Queue();await queue.put('ativar modo forja')
        assistant._dashboard=SimpleNamespace(_command_queue=queue)
        assistant._handle_text_command=AsyncMock(side_effect=asyncio.CancelledError())
        with self.assertRaises(asyncio.CancelledError):await assistant._process_dashboard_commands()
        assistant._handle_text_command.assert_awaited_once_with('ativar modo forja',remote=True)


class NetworkRetryTests(unittest.TestCase):
    def test_network_retry_delay_has_floor_cap_and_grows(self):
        tree=ast.parse((Path(__file__).resolve().parents[1]/'main.py').read_text(encoding='utf-8-sig'))
        assignments=[node for node in ast.walk(tree) if isinstance(node,ast.Assign)
            and any(isinstance(target,ast.Name) and target.id=='_conn_backoff' for target in node.targets)
            and isinstance(node.value,ast.Call) and isinstance(node.value.func,ast.Name) and node.value.func.id=='min']
        self.assertEqual(len(assignments),1)
        expression=compile(ast.Expression(assignments[0].value),'retry-delay','eval')
        for old,expected in ((0,3),(3,6),(6,12),(30,60),(60,60)):
            self.assertEqual(eval(expression,{'self':SimpleNamespace(_conn_backoff=old)}),expected)
