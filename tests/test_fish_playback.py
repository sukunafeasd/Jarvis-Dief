"""Offline delivery regression tests: synthetic PCM, no credentials or network."""
import asyncio
import struct
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import httpx
from core import fish_audio as fish


def owner(maxsize=0):
    return SimpleNamespace(_response_epoch=0, _manual_rest=False,
                           ui=Mock(), audio_in_queue=asyncio.Queue(maxsize=maxsize))


PCM = b''.join(struct.pack('<h', (i % 200) * 100 - 10000) for i in range(3600))


class DeliveryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.owner = owner()
        self.voice = fish.FishVoiceSession(self.owner)

    async def asyncTearDown(self):
        await self.voice.close()

    async def test_pcm_is_bit_exact_across_odd_transport_boundaries(self):
        async def source():
            for start, end in ((0, 1), (1, 3501), (3501, len(PCM))):
                yield PCM[start:end]
        await self.voice._deliver(0, 'Voz natural.', source())
        chunks = []
        while not self.owner.audio_in_queue.empty():
            chunks.append(self.owner.audio_in_queue.get_nowait())
        self.assertEqual(b''.join(chunks), PCM)
        self.assertTrue(all(len(c) <= 2400 and len(c) % 2 == 0 for c in chunks))
        self.assertAlmostEqual(self.voice.cursor, len(PCM) / 48000)
        self.owner.ui.narration_text.assert_called_once()

    async def test_backpressure_is_bounded_and_preserves_order(self):
        self.owner.audio_in_queue = asyncio.Queue(maxsize=2)
        expected = PCM * 4
        async def source():
            yield expected
        task = asyncio.create_task(self.voice._deliver(0, 'Texto.', source()))
        result = bytearray()
        while not task.done() or not self.owner.audio_in_queue.empty():
            self.assertLessEqual(self.owner.audio_in_queue.qsize(), 2)
            try:result.extend(self.owner.audio_in_queue.get_nowait())
            except asyncio.QueueEmpty:pass
            await asyncio.sleep(.001)
        await task
        self.assertEqual(bytes(result), expected)

    async def test_undrained_queue_times_out_without_switching_voice(self):
        async def source(text):
            yield PCM * 10
        with patch.object(fish, 'pcm', source), patch.object(fish, 'QUEUE_TIMEOUT_SECONDS', .025):
            self.voice.feed('Uma frase.', flush=True)
            await asyncio.wait_for(self.voice.task, 1)
        self.assertEqual(self.owner.audio_in_queue.qsize(), fish.MAX_AUDIO_CHUNKS)
        self.assertFalse(self.voice.pending)

    async def test_stalled_source_is_closed_and_pending_clears(self):
        closed = asyncio.Event()
        async def source(text):
            try:
                await asyncio.Event().wait()
                yield PCM
            finally:closed.set()
        with patch.object(fish, 'pcm', source), patch.object(fish, 'SOURCE_TIMEOUT_SECONDS', .025):
            self.voice.feed('Uma frase.', flush=True)
            await asyncio.wait_for(self.voice.task, 1)
        self.assertTrue(closed.is_set())
        self.assertFalse(self.voice.pending)
        self.assertTrue(self.owner.audio_in_queue.empty())

    async def test_no_fallback_or_replay_after_partial_provider_failure(self):
        async def source(text):
            yield PCM[:2400]
            raise ValueError('synthetic failure')
        with patch.object(fish, 'pcm', source):
            self.voice.feed('Uma frase.', flush=True)
            await self.voice.task
        self.assertEqual(self.owner.audio_in_queue.get_nowait(), PCM[:2400])
        self.assertTrue(self.owner.audio_in_queue.empty())
        self.assertFalse(self.voice.pending)
        self.voice.begin_turn()
        self.assertFalse(self.voice._failed)
        self.assertEqual(self.voice.cursor, 0)

    async def test_cancel_then_feed_does_not_erase_new_response(self):
        started = asyncio.Event()
        closed = asyncio.Event()
        async def source(text):
            if text == 'Antiga.':
                try:
                    started.set()
                    await asyncio.Event().wait()
                finally:closed.set()
            yield PCM[:2400]
        with patch.object(fish, 'pcm', source):
            self.voice.feed('Antiga.', flush=True)
            await started.wait()
            self.owner._response_epoch += 1
            self.voice.cancel()
            self.voice.feed('Nova.', flush=True)
            await self.voice.task
            await asyncio.wait_for(closed.wait(), 1)
        self.assertEqual(self.owner.audio_in_queue.qsize(), 1)
        self.owner.ui.narration_text.assert_called_once_with('Nova.', at=0., duration=None)

    async def test_manual_rest_stops_backpressure_and_closes_source(self):
        self.owner.audio_in_queue = asyncio.Queue(maxsize=1)
        closed = asyncio.Event()
        async def source():
            try:yield PCM
            finally:closed.set()
        task = asyncio.create_task(self.voice._deliver(0, 'Texto.', source()))
        while self.owner.audio_in_queue.empty():await asyncio.sleep(0)
        self.owner._manual_rest = True
        await asyncio.wait_for(task, 1)
        self.assertTrue(closed.is_set())
        self.assertEqual(self.owner.audio_in_queue.qsize(), 1)

    async def test_idle_flush_delivers_text_without_punctuation(self):
        async def source(text):yield PCM[:2400]
        with patch.object(fish, 'pcm', source), patch.object(fish, 'TEXT_IDLE_SECONDS', .01):
            self.voice.feed('Resposta sem pontuacao')
            await asyncio.sleep(.03)
            await self.voice.task
        self.assertFalse(self.voice.pending)
        self.assertEqual(self.owner.audio_in_queue.qsize(), 1)

    async def test_incremental_fragments_preserve_words_spaces_and_decimal(self):
        spoken=[]
        async def source(text):
            spoken.append(text)
            yield PCM[:2]
        with patch.object(fish,'pcm',source), patch.object(fish,'TEXT_IDLE_SECONDS',.01):
            self.voice.feed('Confi',incremental=True)
            await asyncio.sleep(.03)
            self.assertIsNone(self.voice.task)
            self.voice.feed('guracao',incremental=True)
            self.voice.feed(' ',incremental=True)
            self.voice.feed('verificada. O valor informado para a verificacao completa do computador e 123.',incremental=True)
            await asyncio.sleep(.03)
            self.assertEqual(spoken,['Configuracao verificada.'])
            self.voice.feed('45 reais.',incremental=True)
            self.voice.feed('',flush=True)
            await self.voice.task
        self.assertEqual(' '.join(spoken),'Configuracao verificada. O valor informado para a verificacao completa do computador e 123.45 reais.')

    async def test_completed_streaming_opener_starts_before_continuation_finishes(self):
        started=asyncio.Event();spoken=[]
        async def source(text):
            spoken.append(text);started.set()
            yield PCM[:2]
        with patch.object(fish,'pcm',source):
            self.voice.feed('Claro, senhor.',incremental=True)
            await asyncio.wait_for(started.wait(),.2)
            for text in (' Estou',' verificando',' os dados'):
                self.voice.feed(text,incremental=True)
                await asyncio.sleep(.01)
            self.assertEqual(spoken,['Claro, senhor.'])
            self.voice.feed('',flush=True)
            await self.voice.task
        self.assertEqual(' '.join(spoken),'Claro, senhor. Estou verificando os dados')

    async def test_empty_whitespace_does_not_create_synthesis(self):
        with patch.object(fish,'pcm') as source:
            self.voice.feed(' ',incremental=True)
            self.voice.feed('',flush=True)
            await asyncio.sleep(0)
        source.assert_not_called()
        self.assertFalse(self.voice.pending)

    async def test_decimal_at_exact_segment_limit_keeps_number_intact(self):
        spoken=[]
        async def source(text):
            spoken.append(text)
            yield PCM[:2]
        text='Contextos '+'x '*193+'123.'
        self.assertEqual(len(text),fish.MAX_SEGMENT_CHARS)
        with patch.object(fish,'pcm',source):
            self.voice.feed(text,incremental=True)
            self.voice.feed('45 reais.',incremental=True)
            self.voice.feed('',flush=True)
            await self.voice.task
        self.assertEqual(' '.join(spoken),text+'45 reais.')
        self.assertTrue(any('123.45' in segment for segment in spoken))

    async def test_streaming_abbreviation_waits_for_name(self):
        spoken=[]
        async def source(text):
            spoken.append(text)
            yield PCM[:2]
        with patch.object(fish,'pcm',source),patch.object(fish,'TEXT_IDLE_SECONDS',.01):
            self.voice.feed('Consulte o Dr.',incremental=True)
            await asyncio.sleep(.03)
            self.assertEqual(spoken,[])
            self.voice.feed(' Silva para detalhes.',incremental=True)
            self.voice.feed('',flush=True)
            await self.voice.task
        self.assertEqual(spoken,['Consulte o Dr. Silva para detalhes.'])

    async def test_word_at_exact_segment_limit_waits_for_continuation(self):
        spoken=[]
        async def source(text):
            spoken.append(text)
            yield PCM[:2]
        text='Contexto '+'x '*193+'Confi'
        self.assertEqual(len(text),fish.MAX_SEGMENT_CHARS)
        with patch.object(fish,'pcm',source):
            self.voice.feed(text,incremental=True)
            self.voice.feed('guracao verificada.',incremental=True)
            self.voice.feed('',flush=True)
            await self.voice.task
        self.assertEqual(' '.join(spoken),text+'guracao verificada.')
        self.assertTrue(any('Configuracao' in segment for segment in spoken))

    async def test_late_text_prefetches_before_staged_audio_drains(self):
        first_done=asyncio.Event();second_started=asyncio.Event();spoken=[]
        async def source(text):
            spoken.append(text)
            if len(spoken)==2:second_started.set()
            yield PCM*8
            first_done.set()
        with patch.object(fish,'pcm',source):
            self.voice.feed('Primeira frase completa.',flush=True)
            await asyncio.wait_for(first_done.wait(),1)
            await asyncio.sleep(.02)
            self.assertEqual(self.owner.audio_in_queue.qsize(),fish.MAX_AUDIO_CHUNKS)
            self.voice.feed('Segunda frase posterior.',flush=True)
            await asyncio.wait_for(second_started.wait(),1)
            result=[]
            while not self.voice.task.done() or not self.owner.audio_in_queue.empty():
                try:result.append(self.owner.audio_in_queue.get_nowait())
                except asyncio.QueueEmpty:pass
                await asyncio.sleep(.001)
            await self.voice.task
        self.assertEqual(spoken,['Primeira frase completa.','Segunda frase posterior.'])
        self.assertEqual(b''.join(result),PCM*16)

    async def test_full_text_queue_retains_every_segment(self):
        self.voice.queue = asyncio.Queue(maxsize=2)
        text = ' '.join('Frase %d completa.' % i for i in range(80))
        spoken = []
        async def source(segment):
            spoken.append(segment)
            yield PCM[:2]
        with patch.object(fish, 'pcm', source), patch.object(fish, 'MAX_AUDIO_CHUNKS', 100):
            self.voice.feed(text, flush=True)
            self.assertTrue(self.voice.buffer)
            await self.voice.task
        self.assertEqual(' '.join(spoken), text)
        self.assertTrue(all(len(s) <= 400 for s in spoken))
        self.assertFalse(self.voice.pending)
        await asyncio.wait_for(self.voice.queue.join(), 1)

    async def test_sentence_groups_do_not_split_abbreviations_or_decimals(self):
        text = 'Sr. Silva informou 3.14 reais. ' + 'Mais contexto natural. ' * 5
        spoken = []
        async def source(segment):
            spoken.append(segment)
            yield PCM[:2]
        with patch.object(fish, 'pcm', source):
            self.voice.feed(text, flush=True)
            await self.voice.task
        self.assertEqual(' '.join(spoken), text.strip())
        self.assertIn('Sr. Silva informou 3.14 reais.', spoken[0])
        self.assertGreater(len(spoken[0]), 80)

    async def test_overflow_is_explicit_and_bounded(self):
        self.voice.feed('x' * (fish.MAX_TEXT_CHARS + 1))
        self.assertFalse(self.voice.pending)
        self.owner.ui.write_log.assert_called_once()

    async def test_deferred_cross_thread_cancel_preserves_new_epoch(self):
        self.voice.feed('Antiga incompleta')
        self.owner._response_epoch = 1
        with patch.object(self.voice.loop, 'call_soon_threadsafe') as schedule:
            thread = threading.Thread(target=self.voice.cancel)
            thread.start()
            thread.join(timeout=1)
            self.assertFalse(thread.is_alive())
        callback = schedule.call_args.args[0]
        self.voice.feed('Nova incompleta')
        callback()
        self.assertEqual(self.voice.buffer, 'Nova incompleta')

    async def test_close_clears_queued_text_and_idle_timer(self):
        self.voice.feed('Texto incompleto')
        await self.voice.close()
        self.assertFalse(self.voice.pending)
        self.assertIsNone(self.voice._idle)

    async def test_empty_chunks_cannot_keep_source_alive_forever(self):
        async def source(text):
            while True:
                await asyncio.sleep(.002)
                yield b''
        with patch.object(fish, 'pcm', source), patch.object(fish, 'SEGMENT_TIMEOUT_SECONDS', .02):
            self.voice.feed('Uma frase.', flush=True)
            await asyncio.wait_for(self.voice.task, 1)
        self.assertFalse(self.voice.pending)

    async def test_direct_new_literal_recovers_failure_without_rebasing_clock(self):
        spoken=[]
        async def source(text):
            spoken.append(text)
            yield PCM[:2400]
            if text=='Primeira.':raise ValueError('synthetic failure')
        with patch.object(fish,'pcm',source):
            self.voice.feed('Primeira.',flush=True)
            await self.voice.task
            self.assertTrue(self.voice._failed)
            anchor=self.voice.cursor
            self.owner.audio_in_queue.get_nowait()
            literal='Agora estou atualizando sua agenda e as noticias.'
            self.voice.feed(literal,flush=True)
            await self.voice.task
        self.assertEqual(spoken,['Primeira.',literal])
        self.assertAlmostEqual(self.voice.cursor,anchor+.05)
        self.owner.ui.narration_text.assert_called_with(literal,at=anchor,duration=None)
        self.assertFalse(self.voice._failed)

    async def test_explicit_failure_reset_preserves_clock_and_does_not_replay(self):
        self.voice.cursor=12.5;self.voice._failed=True
        self.voice.reset_failure()
        self.assertEqual(self.voice.cursor,12.5)
        self.assertFalse(self.voice.pending)
        self.assertFalse(self.voice._failed)

    async def test_failed_stream_does_not_retry_on_later_transcript_fragments(self):
        spoken=[]
        async def source(text):
            spoken.append(text)
            yield PCM[:2400]
            if len(spoken)==1:raise ValueError('synthetic failure')
        with patch.object(fish,'pcm',source):
            self.voice.feed('Primeira frase.',flush=True)
            await self.voice.task
            anchor=self.voice.cursor
            self.voice.feed('Continuacao da mesma resposta.')
            self.voice.feed('Mais uma continuacao.')
            self.voice.feed('',flush=True)
            await asyncio.sleep(.01)
            self.assertEqual(spoken,['Primeira frase.'])
            self.assertTrue(self.voice._failed)
            self.assertFalse(self.voice.pending)
            self.assertEqual(self.owner.audio_in_queue.get_nowait(),PCM[:2400])
            self.assertTrue(self.owner.audio_in_queue.empty())
            self.voice.reset_failure()
            self.voice.feed('Nova resposta explicita.',flush=True)
            await self.voice.task
        self.assertEqual(spoken,['Primeira frase.','Nova resposta explicita.'])
        self.assertEqual(self.owner.audio_in_queue.get_nowait(),PCM[:2400])
        self.owner.ui.narration_text.assert_called_with('Nova resposta explicita.',at=anchor,duration=None)

    async def test_empty_and_incomplete_pcm_are_failures(self):
        async def empty():
            if False:yield b''
        async def odd():yield b'\x01'
        for source in (empty, odd):
            with self.assertRaises(ValueError):
                await self.voice._deliver(0, 'Texto.', source())

    async def test_playback_backpressure_does_not_spend_source_time_budget(self):
        self.owner.audio_in_queue=asyncio.Queue(maxsize=1)
        async def source():yield PCM
        async def drain():
            result=[]
            for _ in range(3):
                result.append(await self.owner.audio_in_queue.get())
                await asyncio.sleep(.04)
            return b''.join(result)
        with patch.object(fish,'SEGMENT_TIMEOUT_SECONDS',.03):
            consumer=asyncio.create_task(drain())
            await self.voice._deliver(0,'Texto.',source())
            self.assertEqual(await consumer,PCM)

    async def test_next_segment_starts_while_previous_audio_is_still_queued(self):
        second=asyncio.Event();spoken=[]
        first='Uma frase natural completa. '*12
        text=first+'Outra frase natural completa. '*12
        async def source(segment):
            spoken.append(segment)
            if len(spoken)==2:second.set()
            yield PCM*8
        with patch.object(fish,'pcm',source):
            self.voice.feed(text,flush=True)
            await asyncio.wait_for(second.wait(),1)
            self.assertTrue(self.voice.pending)
            self.assertEqual(self.owner.audio_in_queue.qsize(),fish.MAX_AUDIO_CHUNKS)
            self.assertLessEqual(len(spoken),2)
            result=[]
            while not self.voice.task.done() or not self.owner.audio_in_queue.empty():
                try:result.append(self.owner.audio_in_queue.get_nowait())
                except asyncio.QueueEmpty:pass
                await asyncio.sleep(.001)
            await self.voice.task
        self.assertEqual(b''.join(result),PCM*8*len(spoken))
        self.assertEqual(' '.join(spoken),text.strip())

    async def test_staging_is_bounded_and_cancel_closes_blocked_producer(self):
        requests=[];closed=asyncio.Event()
        async def source(text):
            requests.append(text)
            try:
                for _ in range(fish.MAX_AUDIO_CHUNKS+fish.MAX_STAGED_CHUNKS+10):
                    yield PCM[:2400]
            finally:closed.set()
        with patch.object(fish,'pcm',source):
            self.voice.feed('Uma frase longa e completa. '*30,flush=True)
            async def full():
                while self.owner.audio_in_queue.qsize()<fish.MAX_AUDIO_CHUNKS:await asyncio.sleep(.001)
            await asyncio.wait_for(full(),1)
            await asyncio.sleep(.02)
            self.assertEqual(len(requests),1)
            self.owner._response_epoch+=1
            self.voice.cancel()
            await asyncio.wait_for(closed.wait(),1)
            await self.voice.close()
        self.assertFalse(self.voice.pending)
        self.assertFalse(self.voice._retired)


class ProviderTests(unittest.IsolatedAsyncioTestCase):
    async def fetch(self, payload, content_type='application/octet-stream', code=200):
        requests = []
        def handle(request):
            requests.append(request)
            return httpx.Response(code, content=payload, headers={'content-type': content_type})
        factory = httpx.AsyncClient
        def client(**kwargs):return factory(transport=httpx.MockTransport(handle), **kwargs)
        with patch.object(fish.integration_tokens, 'read', return_value={'token': 'offline-test-only'}), patch.object(fish, 'settings', return_value={'voice_id': fish.VOICE_ID, 'model': 'configured-model'}), patch.object(fish.httpx, 'AsyncClient', client):
            chunks = [chunk async for chunk in fish.pcm('Texto natural.')]
        return b''.join(chunks), requests

    async def test_request_preserves_voice_model_and_pcm(self):
        import json
        data, requests = await self.fetch(PCM)
        self.assertEqual(data, PCM)
        request = requests[0]
        body = json.loads(request.content)
        self.assertEqual(body['reference_id'], fish.VOICE_ID)
        self.assertEqual(request.headers['model'], 'configured-model')
        self.assertEqual(body['format'], 'pcm')
        self.assertEqual(body['sample_rate'], 24000)
        self.assertEqual(body['latency'], 'normal')
        self.assertEqual(body['chunk_length'], 300)
        self.assertNotIn('prosody', body)

    async def test_rejects_http_errors_containers_empty_and_odd_pcm(self):
        for data, kind, code in ((PCM, 'application/octet-stream', 401),
                                 (b'{"error":"test"}', 'application/json', 200),
                                 (b'RIFF' + b'\x00' * 30, 'application/octet-stream', 200),
                                 (b'RIFF', 'application/octet-stream', 200),
                                 (b'', 'application/octet-stream', 200),
                                 (b'\x01', 'application/octet-stream', 200)):
            with self.subTest(kind=kind, code=code, size=len(data)):
                with self.assertRaises(ValueError):await self.fetch(data, kind, code)

    async def test_long_text_is_rejected_before_credentials_or_network(self):
        with patch.object(fish.integration_tokens, 'read') as credentials:
            with self.assertRaises(ValueError):
                async for _ in fish.pcm('x' * 1801):pass
        credentials.assert_not_called()


class PlaybackIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        import main
        from tests.test_voice_interrupt import assistant_fixture
        self.main=main
        self.owner=assistant_fixture()
        self.owner._is_speaking=False
        self.owner._fish_voice=SimpleNamespace(pending=True)
        self.stream=Mock();self.stream.latency=.01;self.stream.write.return_value=False
        self.patches=[patch.object(main.sd,'RawOutputStream',return_value=self.stream),
                      patch.object(main,'get_output_device',return_value=''),
                      patch.object(main.audio_devices,'resolve',return_value=None),
                      patch.object(main,'_pcm_visemes',return_value=[])]
        for item in self.patches:item.start()
        self.task=None

    async def asyncTearDown(self):
        if self.task is not None:
            self.task.cancel()
            await asyncio.gather(self.task,return_exceptions=True)
        for item in reversed(self.patches):item.stop()

    async def wait_for_write(self):
        async def wait():
            while not self.stream.write.called:await asyncio.sleep(.005)
        await asyncio.wait_for(wait(),1)

    async def test_pending_synthesis_does_not_keep_speaking_or_clear_completion(self):
        self.owner.audio_in_queue.put_nowait(PCM[:2400])
        self.owner._turn_done_event.set()
        self.task=asyncio.create_task(self.owner._play_audio())
        await self.wait_for_write()
        await asyncio.sleep(.25)
        self.assertFalse(self.owner._is_speaking)
        self.assertTrue(self.owner._turn_done_event.is_set())
        self.assertTrue(self.owner._fish_voice.pending)
        self.owner.ui.set_state.assert_called_with('THINKING')
        self.stream.write.assert_called_once_with(PCM[:2400])
        tail=self.owner._tail_until
        self.owner._fish_voice.pending=False
        await asyncio.sleep(.15)
        self.owner.ui.set_state.assert_called_with('LISTENING')
        self.assertEqual(self.owner._tail_until,tail)
        self.assertFalse(self.owner._speech_waiting)

    async def test_gap_resume_announces_speaking_and_preserves_pcm(self):
        self.owner.audio_in_queue.put_nowait(PCM[:2400])
        self.owner._turn_done_event.set()
        self.task=asyncio.create_task(self.owner._play_audio())
        await self.wait_for_write()
        await asyncio.sleep(.25)
        self.owner.ui.set_state.assert_called_with('THINKING')
        self.owner.audio_in_queue.put_nowait(PCM[2400:4800])
        async def resumed():
            while self.stream.write.call_count<2:await asyncio.sleep(.005)
        await asyncio.wait_for(resumed(),1)
        self.owner.ui.set_state.assert_called_with('SPEAKING')
        self.assertFalse(self.owner._speech_waiting)
        self.assertEqual(b''.join(call.args[0] for call in self.stream.write.call_args_list),PCM[:4800])

    async def test_true_end_after_gap_publishes_listening_without_extending_tail(self):
        self.owner._is_speaking=True
        self.owner.set_speaking(False,waiting=True)
        tail=self.owner._tail_until
        self.owner.set_speaking(False)
        self.owner.set_speaking(False)
        self.assertEqual([call.args[0] for call in self.owner.ui.set_state.call_args_list],['THINKING','LISTENING'])
        self.assertEqual(self.owner._tail_until,tail)

    async def test_interruption_and_rest_are_not_synthesis_gaps(self):
        for attr in ('_manual_rest','_interrupted'):
            setattr(self.owner,attr,True)
            self.owner._is_speaking=True
            self.owner.set_speaking(False,waiting=True)
            self.owner.ui.set_state.assert_called_with('LISTENING')
            self.assertFalse(self.owner._speech_waiting)
            setattr(self.owner,attr,False)

    async def test_initial_buffer_combines_exact_pcm_before_speaking(self):
        self.owner.audio_in_queue.put_nowait(PCM[:2400])
        self.task=asyncio.create_task(self.owner._play_audio())
        await asyncio.sleep(.025)
        self.assertFalse(self.owner._is_speaking)
        self.stream.write.assert_not_called()
        self.owner.audio_in_queue.put_nowait(PCM[2400:4800])
        await self.wait_for_write()
        self.stream.write.assert_called_once_with(PCM[:4800])

    async def test_initial_buffer_deadline_and_cancel_during_buffer(self):
        self.owner.audio_in_queue.put_nowait(PCM[:2400])
        start=asyncio.get_running_loop().time()
        self.task=asyncio.create_task(self.owner._play_audio())
        await self.wait_for_write()
        self.assertLess(asyncio.get_running_loop().time()-start,.4)
        self.task.cancel();await asyncio.gather(self.task,return_exceptions=True)
        self.stream.reset_mock()
        self.owner._is_speaking=False
        self.owner.audio_in_queue.put_nowait(PCM[:2400])
        self.task=asyncio.create_task(self.owner._play_audio())
        await asyncio.sleep(.02)
        self.owner._response_epoch+=1
        await asyncio.sleep(.15)
        self.stream.write.assert_not_called()
        self.assertFalse(self.owner._is_speaking)

    async def test_repeated_idle_does_not_extend_echo_tail(self):
        self.owner._is_speaking=True
        self.owner.set_speaking(False)
        tail=self.owner._tail_until
        self.owner.set_speaking(False)
        self.assertEqual(self.owner._tail_until,tail)
        self.owner.ui.set_state.assert_called_once_with('LISTENING')

    async def test_device_operations_use_one_dedicated_thread(self):
        calls=[]
        def record(operation):
            def run(*args):
                calls.append((operation,threading.current_thread().name))
                return False
            return run
        self.stream.write.side_effect=record('write')
        self.stream.stop.side_effect=record('stop')
        self.stream.close.side_effect=record('close')
        self.owner._turn_done_event.set();self.owner._fish_voice=None
        self.owner.audio_in_queue.put_nowait(PCM[:2400])
        self.task=asyncio.create_task(self.owner._play_audio())
        await self.wait_for_write()
        self.task.cancel();await asyncio.gather(self.task,return_exceptions=True)
        self.assertEqual([operation for operation,_ in calls],['write','stop','close'])
        self.assertEqual(len({name for _,name in calls}),1)
        self.assertTrue(calls[0][1].startswith('jarvis-playback'))

    async def test_interrupt_after_queue_get_discards_stale_chunk_before_write(self):
        self.owner._fish_voice.cancel=Mock()
        original_get=self.owner.audio_in_queue.get
        async def get_then_interrupt():
            chunk=await original_get()
            asyncio.get_running_loop().call_soon(self.owner.interrupt)
            return chunk
        self.owner.audio_in_queue.put_nowait(PCM[:2400])
        with patch.object(self.owner.audio_in_queue,'get',get_then_interrupt):
            self.task=asyncio.create_task(self.owner._play_audio())
            await asyncio.sleep(.2)
        self.stream.write.assert_not_called()

    async def test_fresh_audio_arriving_after_epoch_change_is_not_discarded(self):
        self.task=asyncio.create_task(self.owner._play_audio())
        await asyncio.sleep(.02)
        self.owner._response_epoch+=1
        self.owner.audio_in_queue.put_nowait(PCM[:2400])
        await self.wait_for_write()
        self.stream.write.assert_called_once_with(PCM[:2400])

    async def test_receive_clears_completion_on_new_fish_response_and_closes(self):
        from tests.test_voice_interrupt import content,response
        voice=Mock();voice.close=AsyncMock();voice.cursor=12.5
        async def receive():
            yield response(server_content=content(output_transcription=SimpleNamespace(text='Primeira frase.'),turn_complete=True))
            self.assertTrue(self.owner._turn_done_event.is_set())
            yield response(server_content=content(output_transcription=SimpleNamespace(text='Outra resposta')))
            self.assertFalse(self.owner._turn_done_event.is_set())
            yield response(server_content=content(output_transcription=SimpleNamespace(text='segue aqui.')))
            raise asyncio.CancelledError()
        self.owner.session=Mock();self.owner.session.receive=receive
        self.owner._turn_done_event.set()
        with patch.object(fish,'enabled',return_value=True),patch.object(fish,'FishVoiceSession',return_value=voice):
            with self.assertRaises(asyncio.CancelledError):await self.owner._receive_audio()
        self.assertEqual(voice.reset_failure.call_count,2)
        self.assertEqual(voice.cursor,12.5)
        voice.close.assert_awaited_once()
        self.assertIsNone(self.owner._fish_voice)

    async def test_receive_failure_closes_fish(self):
        voice=Mock();voice.close=AsyncMock()
        async def receive():
            raise ValueError('synthetic receive error')
            yield
        self.owner.session=Mock();self.owner.session.receive=receive
        with patch.object(fish,'enabled',return_value=True),patch.object(fish,'FishVoiceSession',return_value=voice):
            with self.assertRaises(ValueError):await self.owner._receive_audio()
        voice.close.assert_awaited_once()
        self.assertIsNone(self.owner._fish_voice)


class ProtocolReceiverTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        from tests.test_voice_interrupt import assistant_fixture,content,response
        self.owner=assistant_fixture();self.owner._is_speaking=False
        self.content=content;self.response=response
        self.owner._route_protocol_user=AsyncMock(return_value=True)
        self.owner._execute_tool=AsyncMock(return_value=Mock())
        self.owner._flush_pending_vision=AsyncMock()
        self.fc=SimpleNamespace(id='offline-call',name='native_operation',args={'text':'generated argument'})

    async def run_stream(self,stream,voice=None):
        self.owner.session=Mock();self.owner.session.receive=stream
        self.owner.session.send_tool_response=AsyncMock()
        with patch.object(fish,'enabled',return_value=voice is not None),patch.object(fish,'FishVoiceSession',return_value=voice):
            with self.assertRaises(asyncio.CancelledError):await self.owner._receive_audio()

    async def test_missing_finished_routes_actual_fragments_before_tool_and_silences_continuation(self):
        async def stream():
            yield self.response(server_content=self.content(input_transcription=SimpleNamespace(text='Ative Ultron')))
            yield self.response(tool_call=SimpleNamespace(function_calls=[self.fc]))
            self.owner.ui.record_ultron_user.assert_called_once_with('Ative Ultron')
            self.owner._route_protocol_user.assert_awaited_once_with('Ative Ultron')
            yield self.response(data=PCM,server_content=self.content(output_transcription=SimpleNamespace(text='Resposta nativa duplicada'),turn_complete=True))
            yield self.response(data=PCM,server_content=self.content(output_transcription=SimpleNamespace(text='Continuacao nativa'),turn_complete=True))
            raise asyncio.CancelledError()
        await self.run_stream(stream)
        self.owner._execute_tool.assert_not_awaited()
        self.assertTrue(self.owner.audio_in_queue.empty())
        self.owner._visemes.feed_text.assert_not_called()
        self.assertTrue(self.owner._protocol_input_consumed)
        self.assertEqual(self.owner._route_protocol_user.await_count,1)
        result=self.owner.session.send_tool_response.call_args.kwargs['function_responses'][0]
        self.assertTrue(result.response['result']['cancelled'])

    async def test_finished_false_holds_tools_and_output_until_turn_closed(self):
        async def stream():
            yield self.response(server_content=self.content(input_transcription=SimpleNamespace(text='Ative Forja',finished=False)))
            yield self.response(data=PCM,tool_call=SimpleNamespace(function_calls=[self.fc]),server_content=self.content(output_transcription=SimpleNamespace(text='Resposta precoce')))
            self.owner._route_protocol_user.assert_not_awaited()
            self.owner._execute_tool.assert_not_awaited()
            self.assertTrue(self.owner.audio_in_queue.empty())
            yield self.response(server_content=self.content(turn_complete=True))
            raise asyncio.CancelledError()
        await self.run_stream(stream)
        self.owner._route_protocol_user.assert_awaited_once_with('Ative Forja')
        self.owner._execute_tool.assert_not_awaited()
        self.assertTrue(self.owner.audio_in_queue.empty())

    async def test_unconsumed_input_releases_held_exact_pcm_and_tools(self):
        self.owner._route_protocol_user.return_value=False
        async def stream():
            yield self.response(server_content=self.content(input_transcription=SimpleNamespace(text='Pedido comum',finished=False)))
            yield self.response(data=PCM,tool_call=SimpleNamespace(function_calls=[self.fc]))
            yield self.response(server_content=self.content(turn_complete=True))
            raise asyncio.CancelledError()
        with patch('memory.config_manager.load_api_keys',return_value={'speech_provider':'gemini'}):
            await self.run_stream(stream)
        self.owner._execute_tool.assert_awaited_once_with(self.fc)
        chunks=[]
        while not self.owner.audio_in_queue.empty():chunks.append(self.owner.audio_in_queue.get_nowait())
        self.assertEqual(b''.join(chunks),PCM)

    async def test_consumed_route_keeps_own_fish_voice_on_live_interruption(self):
        voice=Mock();voice.pending=True;voice.close=AsyncMock()
        async def route(text):
            self.owner.ui.record_ultron_user.assert_called_once_with(text)
            voice.feed('Resposta local natural.',flush=True)
            return True
        self.owner._route_protocol_user.side_effect=route
        async def stream():
            yield self.response(server_content=self.content(input_transcription=SimpleNamespace(text='Ative Ultron',finished=True),output_transcription=SimpleNamespace(text='Duplicada'),interrupted=True,turn_complete=True))
            raise asyncio.CancelledError()
        await self.run_stream(stream,voice)
        voice.feed.assert_called_once_with('Resposta local natural.',flush=True)
        voice.cancel.assert_not_called()
        self.assertEqual(self.owner._response_epoch,0)

    async def test_new_actual_input_resets_consumption_and_routes_once_again(self):
        self.owner._route_protocol_user.side_effect=[True,False]
        async def stream():
            yield self.response(server_content=self.content(input_transcription=SimpleNamespace(text='Ative Ultron',finished=True),turn_complete=True))
            yield self.response(server_content=self.content(input_transcription=SimpleNamespace(text='Pedido comum',finished=True)),tool_call=SimpleNamespace(function_calls=[self.fc]))
            raise asyncio.CancelledError()
        await self.run_stream(stream)
        self.assertEqual(self.owner._route_protocol_user.await_count,2)
        self.owner._execute_tool.assert_awaited_once_with(self.fc)
        self.assertFalse(self.owner._protocol_input_consumed)

    async def test_live_only_interruption_does_not_cancel_active_fish(self):
        voice=Mock();voice.pending=True;voice.close=AsyncMock()
        async def stream():
            yield self.response(server_content=self.content(interrupted=True,turn_complete=True))
            raise asyncio.CancelledError()
        await self.run_stream(stream,voice)
        voice.cancel.assert_not_called()
        self.assertEqual(self.owner._response_epoch,0)

    async def test_actual_new_user_input_in_gap_can_interrupt_old_fish(self):
        voice=Mock();voice.pending=True;voice.close=AsyncMock()
        self.owner._route_protocol_user.return_value=False
        async def stream():
            yield self.response(server_content=self.content(input_transcription=SimpleNamespace(text='Outro pedido',finished=True),interrupted=True,turn_complete=True))
            raise asyncio.CancelledError()
        await self.run_stream(stream,voice)
        voice.cancel.assert_called_once()
        self.assertEqual(self.owner._response_epoch,1)


class PresentationGapContractTests(unittest.TestCase):
    def fixture(self,state='SPEAKING'):
        from core.presentation_clock import PresentationClock
        clock=PresentationClock();clock.advance(.1)
        return SimpleNamespace(
            _resting=False,hud=SimpleNamespace(state=state,speaking=state=='SPEAKING'),
            _visual_scene=Mock(),_presentation_clock=clock,
            _ultron_clock=SimpleNamespace(cancelled=False),_ui_sounds=Mock(),
            _settle_timer=Mock(),_content_spatial=Mock(),_set_news_phase=Mock(),
            _presentation={'narration_active':True,'audio_started':True,'model':{'newsLast':True}},
            _pinned=False,_refresh_lock=None)

    def test_real_ui_gap_does_not_finish_visual_or_presentation(self):
        from ui import MainWindow
        window=self.fixture()
        with patch('ui._read_full_config',return_value={'presentation_hold':0}):
            MainWindow._apply_state(window,'THINKING')
        self.assertEqual(window.hud.state,'THINKING')
        self.assertFalse(window.hud.speaking)
        window._visual_scene.finish.assert_not_called()
        window._content_spatial.page.return_value.runJavaScript.assert_not_called()
        self.assertTrue(window._presentation['narration_active'])
        self.assertTrue(window._presentation['audio_started'])
        window._settle_timer.start.assert_not_called()

    def test_real_ui_true_end_after_gap_finishes_once(self):
        from ui import MainWindow
        window=self.fixture('THINKING')
        with patch('ui._read_full_config',return_value={'presentation_hold':0}):
            MainWindow._apply_state(window,'LISTENING')
            MainWindow._apply_state(window,'LISTENING')
        window._visual_scene.finish.assert_called_once()
        window._content_spatial.page.return_value.runJavaScript.assert_called_once()
        self.assertFalse(window._presentation['narration_active'])
        self.assertFalse(window._presentation['audio_started'])


if __name__ == '__main__':
    unittest.main()
