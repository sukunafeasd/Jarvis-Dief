"""Interrupted receive packets and local-day boundaries, without real providers."""
import asyncio
from datetime import datetime
import time
import unittest
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, Mock, patch

from tests.test_voice_interrupt import assistant_fixture, content, response


class ReceiveEpochTests(unittest.IsolatedAsyncioTestCase):
    async def test_interrupted_memory_discards_remaining_stream_and_acknowledges_tools(self):
        await self.exercise_interrupted_stream()

    async def test_interrupted_routing_discards_remaining_stream_and_acknowledges_tools(self):
        await self.exercise_interrupted_stream(during_routing=True)

    async def exercise_interrupted_stream(self,during_routing=False):
        owner=assistant_fixture();owner._is_speaking=False;owner._server_turn_open=False
        owner._route_protocol_user=AsyncMock(return_value=False)
        owner._remember_assistant_turn=AsyncMock();owner._execute_tool=AsyncMock()
        owner._flush_pending_vision=AsyncMock()
        voice=Mock(pending=False);voice.close=AsyncMock()
        async def remember(*args):owner.interrupt();await asyncio.sleep(0)
        owner._remember_user_turn=AsyncMock(side_effect=None if during_routing else remember)
        if during_routing:owner._route_protocol_user=AsyncMock(side_effect=remember)
        async def stream():
            yield response(server_content=content(input_transcription=NS(text='Pedido antigo',finished=True),
                output_transcription=NS(text='Inicio cancelado.')),
                tool_call=NS(function_calls=[NS(id='old-current',name='native_operation',args={})]))
            yield response(server_content=content(output_transcription=NS(text='Resto cancelado.')),
                tool_call=NS(function_calls=[NS(id='old-later',name='native_operation',args={})]))
            yield response(server_content=content(turn_complete=True),
                tool_call=NS(function_calls=[NS(id='old',name='native_operation',args={})]))
            self.assertFalse(owner._interrupted)
            yield response(server_content=content(output_transcription=NS(text='Nova resposta valida.'),turn_complete=True))
            raise asyncio.CancelledError()
        owner.session=Mock();owner.session.receive=stream;owner.session.send_tool_response=AsyncMock()
        with patch('core.fish_audio.enabled',return_value=True),patch('core.fish_audio.FishVoiceSession',return_value=voice):
            with self.assertRaises(asyncio.CancelledError):await owner._receive_audio()
        owner._execute_tool.assert_not_awaited()
        owner._flush_pending_vision.assert_not_awaited()
        results=[result for call in owner.session.send_tool_response.call_args_list
                 for result in call.kwargs['function_responses']]
        self.assertEqual([result.id for result in results],['old-current','old-later','old'])
        self.assertTrue(all(result.response['result']['cancelled'] for result in results))
        spoken=[call.args[0] for call in voice.feed.call_args_list if call.kwargs.get('incremental')]
        self.assertEqual(spoken,['Nova resposta valida.'])

    async def test_interruption_during_memory_cannot_revive_output_or_run_tools(self):
        owner=assistant_fixture();owner._is_speaking=False;owner._server_turn_open=False
        owner._route_protocol_user=AsyncMock(return_value=False)
        owner._remember_assistant_turn=AsyncMock()
        owner._execute_tool=AsyncMock()
        voice=Mock(pending=False);voice.close=AsyncMock()
        async def remember(*args):
            owner.interrupt()
            await asyncio.sleep(0)
        owner._remember_user_turn=AsyncMock(side_effect=remember)
        async def stream():
            yield response(server_content=content(input_transcription=NS(text='Pedido antigo',finished=True),
                output_transcription=NS(text='Resposta cancelada.'),turn_complete=True),
                tool_call=NS(function_calls=[NS(id='old',name='native_operation',args={})]))
            owner._route_protocol_user.assert_not_awaited()
            owner._execute_tool.assert_not_awaited()
            voice.feed.assert_not_called()
            owner._remember_user_turn=AsyncMock()
            yield response(server_content=content(output_transcription=NS(text='Nova resposta valida.'),turn_complete=True))
            raise asyncio.CancelledError()
        owner.session=Mock();owner.session.receive=stream;owner.session.send_tool_response=AsyncMock()
        with patch('core.fish_audio.enabled',return_value=True),patch('core.fish_audio.FishVoiceSession',return_value=voice):
            with self.assertRaises(asyncio.CancelledError):await owner._receive_audio()
        self.assertTrue(any('Nova resposta valida.' in str(call) for call in voice.feed.call_args_list))
        self.assertFalse(any('cancelada' in str(call) for call in voice.feed.call_args_list))


class MidnightBriefingTests(unittest.IsolatedAsyncioTestCase):
    async def run_briefing(self, rollover_at):
        from main import JarvisLive
        current=[datetime(2026,10,16,23,59,59)]
        class Clock:
            @classmethod
            def now(cls):return current[0]
        owner=JarvisLive.__new__(JarvisLive)
        owner._response_epoch=0
        owner.ui=Mock();owner.session=Mock();owner.session.send_client_content=AsyncMock()
        owner._awake=True;owner._manual_rest=False;owner._is_speaking=False
        owner._played_audio_seconds=0.;owner._tail_active=lambda:False
        owner.audio_in_queue=asyncio.Queue();owner._refresh_summary=True
        owner._daily_collection_day='2026-10-16';owner._daily_collection_started_at=time.monotonic()
        def package(title):
            return {'data':{'tasks':{'kind':'tasks','items':[{'title':title}]}},'unavailable':[]}
        old=package('Tarefa de ontem');fresh=package('Tarefa de hoje')
        cached=asyncio.get_running_loop().create_future();cached.set_result(old)
        owner._daily_collection_task=cached
        spoken=[]
        def feed(text,**kwargs):
            spoken.append(text);owner._played_audio_seconds+=1
            if len(spoken)==rollover_at:current[0]=datetime(2026,10,17,0,0,1)
        owner._fish_voice=Mock(pending=False,_failed=False);owner._fish_voice.feed.side_effect=feed
        with patch('main.datetime',Clock),patch('core.session_refresh.collect_updates',AsyncMock(return_value=fresh)) as collect,patch('core.daily_briefing.mark_delivered') as mark:
            await owner._send_startup_briefing()
        return spoken,collect,mark,owner

    async def test_midnight_during_greeting_recollects_before_narrating(self):
        spoken,collect,mark,owner=await self.run_briefing(1)
        collect.assert_awaited_once()
        self.assertFalse(any('Tarefa de ontem' in text for text in spoken))
        self.assertTrue(any('Tarefa de hoje' in text for text in spoken))
        self.assertEqual(mark.call_args.kwargs['delivery_day'],'2026-10-17')
        self.assertEqual(owner._day_context['data']['tasks']['items'][0]['title'],'Tarefa de hoje')

    async def test_midnight_during_narration_does_not_mark_next_day_delivered(self):
        _,collect,mark,_=await self.run_briefing(2)
        collect.assert_not_awaited()
        self.assertEqual(mark.call_args.kwargs['delivery_day'],'2026-10-16')
