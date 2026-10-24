"""Offline voice regressions. Synthetic PCM and mocked network/device only."""
import asyncio
import threading
import unittest
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, Mock, patch

from core import fish_audio as fish
from tests.test_voice_interrupt import assistant_fixture, content, response, session_for
import main

PCM = bytes(range(256)) * 18 + bytes(range(192))


class SelectionTests(unittest.TestCase):
    def test_fish_requires_selection_and_credential(self):
        for config, expected in (({}, True), ({'speech_provider': 'fish_audio'}, True),
                                 ({'speech_provider': 'unknown'}, False),
                                 ({'speech_provider': 'gemini'}, False)):
            with patch('memory.config_manager.load_api_keys', return_value=config), patch.object(fish.integration_tokens,'read',return_value={'token':'synthetic'}):
                self.assertEqual(fish.selected(), expected)
        with patch('memory.config_manager.load_api_keys',return_value={'speech_provider':'fish_audio'}), patch.object(fish.integration_tokens,'read',return_value={}):
            self.assertFalse(fish.selected())

    def test_unreadable_settings_do_not_select_unavailable_fish(self):
        with patch('memory.config_manager.load_api_keys', side_effect=ValueError('offline')):
            self.assertFalse(fish.selected())


class ReceiverTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.owner = assistant_fixture()
        self.owner._is_speaking = False
        # Any accidental synthesis is an offline failure, never a paid request.
        self.network = patch.object(fish.httpx, 'AsyncClient', side_effect=AssertionError('network forbidden'))
        self.network.start()

    async def asyncTearDown(self):
        self.network.stop()

    async def receive(self, packets, selected=True, available=False, voice=None):
        self.owner.session = session_for(packets)
        with patch.object(fish, 'selected', return_value=selected), \
             patch.object(fish, 'enabled', return_value=available), \
             patch.object(fish, 'FishVoiceSession', return_value=voice):
            with self.assertRaises(asyncio.CancelledError):
                await self.owner._receive_audio()

    async def test_unavailable_fish_uses_native_and_reports_limitation(self):
        await self.receive([response(data=PCM, server_content=content(
            output_transcription=NS(text='Resposta disponivel em texto.'), turn_complete=True))])
        audio=b''.join(self.owner.audio_in_queue.get_nowait() for _ in range(self.owner.audio_in_queue.qsize()))
        self.assertEqual(audio,PCM)
        self.assertTrue(any('Voz Fish indisponivel' in call.args[0]
                            for call in self.owner.ui.write_log.call_args_list))
        self.assertIn('DIEF JARVIS: Resposta disponivel em texto.', self.owner._session_log)

    async def test_explicit_native_selection_preserves_pcm(self):
        await self.receive([response(data=PCM)], selected=False)
        result = b''.join(self.owner.audio_in_queue.get_nowait()
                          for _ in range(self.owner.audio_in_queue.qsize()))
        self.assertEqual(result, PCM)

    async def test_live_pcm_is_discarded_and_fish_closed_on_session_cancel(self):
        voice = Mock(); voice.close = AsyncMock()
        await self.receive([response(data=PCM, server_content=content(
            output_transcription=NS(text='Uma unica voz configurada.'), turn_complete=True))],
            available=True, voice=voice)
        voice.feed.assert_any_call('Uma unica voz configurada.', incremental=True)
        voice.close.assert_awaited_once()
        self.assertIsNone(self.owner._fish_voice)
        self.assertTrue(self.owner.audio_in_queue.empty())

    async def test_incremental_fragments_preserve_whitespace_and_repeated_digits(self):
        voice=Mock();voice.close=AsyncMock()
        fragments=['Confi','guracao',' ','verificada. A senha e ','1','1','2','.']
        packets=[response(server_content=content(output_transcription=NS(text=text))) for text in fragments]
        packets.append(response(server_content=content(turn_complete=True)))
        await self.receive(packets,available=True,voice=voice)
        forwarded=[call.args[0] for call in voice.feed.call_args_list if call.kwargs.get('incremental')]
        self.assertEqual(forwarded,fragments)
        self.assertTrue(self.owner.audio_in_queue.empty())

    async def test_tool_turn_boundary_does_not_speak_replayed_tail(self):
        voice = Mock(); voice.close = AsyncMock()
        text = 'Esta resposta ja foi falada antes.'
        await self.receive([response(server_content=content(
            output_transcription=NS(text=text), turn_complete=True)),
            response(server_content=content(output_transcription=NS(text=text), turn_complete=True))],
            available=True, voice=voice)
        self.assertEqual(sum(call.args == (text,) for call in voice.feed.call_args_list), 1)

    async def test_new_user_can_request_same_answer_again(self):
        voice = Mock(); voice.close = AsyncMock()
        text = 'Esta resposta pode ser repetida.'
        await self.receive([response(server_content=content(
            output_transcription=NS(text=text), turn_complete=True)),
            response(server_content=content(input_transcription=NS(text='Repita a resposta', finished=True))),
            response(server_content=content(output_transcription=NS(text=text), turn_complete=True))],
            available=True, voice=voice)
        self.assertEqual(sum(call.args == (text,) for call in voice.feed.call_args_list), 2)

    async def test_new_typed_request_can_repeat_same_answer(self):
        voice = Mock(); voice.close = AsyncMock()
        text = 'Esta resposta pode ser repetida.'
        async def stream():
            yield response(server_content=content(output_transcription=NS(text=text), turn_complete=True))
            # _on_text_command clears this event before sending a new request.
            self.owner._turn_done_event.clear()
            yield response(server_content=content(output_transcription=NS(text=text), turn_complete=True))
            raise asyncio.CancelledError()
        self.owner.session = Mock(); self.owner.session.receive = stream
        with patch.object(fish, 'selected', return_value=True), \
             patch.object(fish, 'enabled', return_value=True), \
             patch.object(fish, 'FishVoiceSession', return_value=voice):
            with self.assertRaises(asyncio.CancelledError): await self.owner._receive_audio()
        self.assertEqual(sum(call.args == (text,) for call in voice.feed.call_args_list), 2)

    async def test_receiver_reuses_voice_initialized_before_connection_notice(self):
        voice = Mock(); voice.close = AsyncMock()
        self.owner.session = session_for([response(data=PCM, server_content=content(
            output_transcription=NS(text='Resposta da mesma sessao.'), turn_complete=True))])
        with patch.object(fish, 'selected', return_value=True), \
             patch.object(fish, 'enabled', return_value=True), \
             patch.object(fish, 'FishVoiceSession', return_value=voice) as create:
            self.owner._initialize_voice()
            self.assertIs(self.owner._fish_session, self.owner.session)
            self.assertIs(self.owner._fish_voice, voice)
            with self.assertRaises(asyncio.CancelledError): await self.owner._receive_audio()
        create.assert_called_once_with(self.owner)
        voice.feed.assert_any_call('Resposta da mesma sessao.', incremental=True)
        voice.close.assert_awaited_once()
        self.assertIsNone(self.owner._fish_session)
        self.assertTrue(self.owner.audio_in_queue.empty())

    async def test_ultron_completion_injection_returns_text_only_to_fish(self):
        voice = Mock(); voice.pending = False; voice.close = AsyncMock()
        self.owner._fish_voice = voice
        self.owner._server_turn_open = False
        self.owner._loop = asyncio.get_running_loop()
        sent = asyncio.Event()
        self.owner.session = Mock()
        async def send(**kwargs): sent.set()
        self.owner.session.send_client_content = AsyncMock(side_effect=send)
        self.owner._ultron_completed({})
        await asyncio.wait_for(sent.wait(), 1)
        self.owner.session.send_client_content.assert_awaited_once()
        text = 'Diagnostico concluido com dados reais.'
        async def stream():
            yield response(data=PCM, server_content=content(
                output_transcription=NS(text=text), turn_complete=True))
            raise asyncio.CancelledError()
        self.owner.session.receive = stream
        with patch.object(fish, 'selected', return_value=True), \
             patch.object(fish, 'enabled', return_value=True), \
             patch.object(fish, 'FishVoiceSession', return_value=voice):
            with self.assertRaises(asyncio.CancelledError): await self.owner._receive_audio()
        voice.feed.assert_any_call(text, incremental=True)
        self.assertTrue(self.owner.audio_in_queue.empty())


class LifetimeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.owner = NS(_response_epoch=0, _manual_rest=False, ui=Mock(), audio_in_queue=asyncio.Queue())
        self.voice = fish.FishVoiceSession(self.owner)

    async def asyncTearDown(self):
        await self.voice.close()

    async def test_cancel_same_epoch_rejects_late_source_that_swallows_cancel(self):
        started = asyncio.Event()
        closed = asyncio.Event()
        async def source():
            try:
                started.set()
                try: await asyncio.Event().wait()
                except asyncio.CancelledError: pass
                yield PCM
            finally: closed.set()
        delivery = asyncio.create_task(self.voice._deliver(0, 'Antiga.', source()))
        await started.wait()
        self.voice.cancel()
        delivery.cancel()
        await asyncio.wait_for(delivery, 1)
        self.assertTrue(self.owner.audio_in_queue.empty())
        self.assertTrue(closed.is_set())

    async def test_cancel_same_epoch_rejects_blocked_enqueue(self):
        self.owner.audio_in_queue = asyncio.Queue(maxsize=1)
        self.owner.audio_in_queue.put_nowait(b'prior')
        enqueue = asyncio.create_task(self.voice._enqueue(0, PCM))
        await asyncio.sleep(.01)
        self.voice.cancel()
        self.owner.audio_in_queue.get_nowait()
        self.assertFalse(await asyncio.wait_for(enqueue, 1))
        self.assertTrue(self.owner.audio_in_queue.empty())

    async def test_old_idle_callback_cannot_flush_new_text_in_same_epoch(self):
        generation = self.voice._generation
        self.voice.cancel()
        self.voice.feed('Nova frase incompleta')
        idle = self.voice._idle
        self.voice._idle_flush(0, generation)
        self.assertIs(self.voice._idle, idle)
        self.assertIsNone(self.voice.task)
        self.assertEqual(self.voice.buffer, 'Nova frase incompleta')

    async def test_receive_reconnect_closes_pending_source(self):
        started = asyncio.Event(); closed = asyncio.Event()
        async def source(text):
            try:
                started.set()
                await asyncio.Event().wait()
                yield PCM
            finally: closed.set()
        with patch.object(fish, 'pcm', source):
            self.voice.feed('Pendente.', flush=True)
            await started.wait()
            await asyncio.wait_for(self.voice.close(), 1)
        self.assertTrue(closed.is_set())
        self.assertFalse(self.voice.pending)
        self.assertTrue(self.owner.audio_in_queue.empty())

    async def test_source_stall_is_bounded_and_does_not_retry(self):
        calls = []
        async def source(text):
            calls.append(text)
            await asyncio.Event().wait()
            yield PCM
        with patch.object(fish, 'pcm', source), patch.object(fish, 'SOURCE_TIMEOUT_SECONDS', .02):
            self.voice.feed('Primeira.', flush=True)
            await asyncio.wait_for(self.voice.task, 1)
            self.voice.feed('Continuacao que nao deve tentar novamente.')
            self.voice.feed('', flush=True)
        self.assertEqual(calls, ['Primeira.'])
        self.assertTrue(self.voice._failed)
        self.assertFalse(self.voice.pending)


class PlaybackTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.owner = assistant_fixture(); self.owner._is_speaking = False
        self.owner._fish_voice = None
        self.owner._turn_done_event.set()
        self.stream = Mock(); self.stream.latency = .3; self.stream.write.return_value = False
        self.task = None
        self.patches = [patch.object(main.sd, 'RawOutputStream', return_value=self.stream),
                        patch.object(main, 'get_output_device', return_value=''),
                        patch.object(main.audio_devices, 'resolve', return_value=None),
                        patch.object(main, '_pcm_visemes', return_value=[])]
        for item in self.patches: item.start()

    async def asyncTearDown(self):
        if self.task:
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)
        for item in reversed(self.patches): item.stop()

    async def until(self, condition):
        async def wait():
            while not condition(): await asyncio.sleep(.001)
        await asyncio.wait_for(wait(), 1)

    async def start_audio(self):
        self.owner.audio_in_queue.put_nowait(PCM)
        self.task = asyncio.create_task(self.owner._play_audio())
        await self.until(lambda: self.owner.ui.presentation_audio.called)

    async def test_pcm_reaches_device_bit_exact_without_dsp(self):
        await self.start_audio()
        self.stream.write.assert_called_once_with(PCM)

    async def test_interrupt_drains_device_while_queue_is_empty(self):
        await self.start_audio()
        self.owner._response_epoch += 1
        await self.until(lambda: self.stream.abort.called)
        await self.until(lambda: self.stream.start.call_count >= 2)
        self.assertTrue(self.owner.audio_in_queue.empty())
        self.assertEqual(self.stream.start.call_count, 2)
        self.stream.write.assert_called_once()

    async def test_cancel_aborts_instead_of_playing_old_tail_on_reconnect(self):
        await self.start_audio()
        self.task.cancel()
        await asyncio.gather(self.task, return_exceptions=True)
        self.stream.abort.assert_called_once()
        self.stream.stop.assert_called_once()
        calls = [call[0] for call in self.stream.method_calls]
        self.assertLess(calls.index('abort'), calls.index('stop'))
        self.stream.close.assert_called_once()

    async def test_slow_visual_analysis_cannot_hold_next_write_or_echo_reference(self):
        entered = threading.Event(); release = threading.Event()
        def slow(*args):
            entered.set(); release.wait(1); return []
        self.owner._echo = Mock()
        def write(data):
            self.assertTrue(self.owner._echo.note_output.called)
            return False
        self.stream.write.side_effect = write
        with patch.object(main, '_pcm_visemes', side_effect=slow):
            try:
                self.owner.audio_in_queue.put_nowait(PCM)
                self.owner.audio_in_queue.put_nowait(PCM)
                self.task = asyncio.create_task(self.owner._play_audio())
                await self.until(lambda: self.stream.write.call_count == 2)
                self.assertTrue(entered.is_set())
                self.assertFalse(release.is_set())
            finally: release.set()
        self.assertEqual(b''.join(call.args[0] for call in self.stream.write.call_args_list), PCM * 2)


class GreetingTests(unittest.IsolatedAsyncioTestCase):
    async def test_delayed_greeting_cannot_cross_session_reconnect(self):
        owner = assistant_fixture(); owner._is_speaking = False; owner._server_turn_open = False
        owner._welcome_sent = False; owner._fish_required = True
        owner._fish_voice = NS(pending=False, feed=Mock())
        owner.session = Mock()
        async def reconnect(delay): owner.session = Mock()
        with patch.object(main.asyncio, 'sleep', side_effect=reconnect):
            await owner._opening_greeting()
        owner._fish_voice.feed.assert_not_called()
        self.assertFalse(owner._welcome_sent)

    async def test_greeting_does_not_overlap_pending_fish(self):
        owner = assistant_fixture(); owner._is_speaking = False; owner._server_turn_open = False
        owner._welcome_sent = False; owner.session = Mock()
        owner._fish_voice = NS(pending=True, feed=Mock())
        with patch.object(main.asyncio, 'sleep', new=AsyncMock()):
            await owner._opening_greeting()
        owner._fish_voice.feed.assert_not_called()

    async def test_unavailable_fish_greeting_does_not_request_native(self):
        owner = assistant_fixture(); owner._is_speaking = False; owner._server_turn_open = False
        owner._welcome_sent = False; owner._fish_voice = None; owner._fish_required = True
        owner.session = NS(send_client_content=AsyncMock())
        with patch.object(main.asyncio, 'sleep', new=AsyncMock()):
            await owner._opening_greeting()
        owner.session.send_client_content.assert_not_awaited()


if __name__ == '__main__':
    unittest.main()
