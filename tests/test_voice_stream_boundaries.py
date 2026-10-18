"""Offline packet-boundary regressions; synthetic PCM and mocked output only."""
import asyncio
import unittest
from unittest.mock import patch

from core import fish_audio as fish
from tests import test_fish_playback as fixtures


class PlaybackBoundaryTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = fixtures.PlaybackIntegrationTests.asyncSetUp
    asyncTearDown = fixtures.PlaybackIntegrationTests.asyncTearDown

    async def until(self, condition):
        async def wait():
            while not condition():
                await asyncio.sleep(.001)
        await asyncio.wait_for(wait(), 2)

    async def test_large_packet_uses_bounded_writes_without_changing_pcm(self):
        data = fixtures.PCM * 4
        self.owner._fish_voice = None
        self.owner._turn_done_event.set()
        self.owner.audio_in_queue.put_nowait(data)
        self.task = asyncio.create_task(self.owner._play_audio())
        await self.until(lambda: sum(len(call.args[0]) for call in self.stream.write.call_args_list) >= len(data))
        chunks = [call.args[0] for call in self.stream.write.call_args_list]
        self.assertEqual(b''.join(chunks), data)
        self.assertTrue(all(len(chunk) <= 4800 for chunk in chunks))

    async def test_split_sample_survives_gap_between_transport_packets(self):
        data = fixtures.PCM[:4800]
        self.owner.audio_in_queue.put_nowait(data[:2401])
        self.task = asyncio.create_task(self.owner._play_audio())
        await self.until(lambda: self.stream.write.called)
        self.owner.audio_in_queue.put_nowait(data[2401:])
        await self.until(lambda: sum(len(call.args[0]) for call in self.stream.write.call_args_list) >= len(data))
        self.assertEqual(b''.join(call.args[0] for call in self.stream.write.call_args_list), data)
        self.owner.ui.write_log.assert_not_called()

    async def test_fresh_epoch_restarts_device_before_first_write_and_keeps_remainder(self):
        self.task = asyncio.create_task(self.owner._play_audio())
        await asyncio.sleep(.02)
        self.owner._response_epoch += 1
        data = fixtures.PCM * 3
        self.owner.audio_in_queue.put_nowait(data)
        await self.until(lambda: sum(len(call.args[0]) for call in self.stream.write.call_args_list) >= len(data))
        operations = [call[0] for call in self.stream.method_calls]
        self.assertLess(operations.index('abort'), operations.index('write'))
        self.assertEqual(self.stream.abort.call_count, 1)
        self.assertEqual(b''.join(call.args[0] for call in self.stream.write.call_args_list), data)

    async def test_epoch_change_during_inner_jitter_wait_preserves_fresh_packet(self):
        inner_wait = asyncio.Event()
        original_get = self.owner.audio_in_queue.get
        gets = 0
        fresh = fixtures.PCM[:2400]
        async def observed_get():
            nonlocal gets
            gets += 1
            if gets == 2:
                inner_wait.set()
                self.owner._response_epoch += 1
                self.owner.audio_in_queue.put_nowait(fresh)
            return await original_get()
        self.owner.audio_in_queue.put_nowait(b'\x01\x02')
        with patch.object(self.owner.audio_in_queue, 'get', observed_get):
            self.task = asyncio.create_task(self.owner._play_audio())
            await asyncio.wait_for(inner_wait.wait(), 1)
            await self.until(lambda: self.stream.write.called)
            self.stream.write.assert_called_once_with(fresh)
            self.assertTrue(self.owner.audio_in_queue.empty())
            operations = [call[0] for call in self.stream.method_calls]
            self.assertLess(operations.index('abort'), operations.index('write'))

    async def test_interruption_discards_local_remainder_from_large_packet(self):
        def interrupt_after_write(data):
            self.owner._response_epoch += 1
            return False
        self.stream.write.side_effect = interrupt_after_write
        self.owner.audio_in_queue.put_nowait(fixtures.PCM * 4)
        self.task = asyncio.create_task(self.owner._play_audio())
        await self.until(lambda: self.stream.abort.called)
        await asyncio.sleep(.15)
        self.stream.write.assert_called_once_with(fixtures.PCM[:4800])

    async def test_single_trailing_byte_waits_for_sample_and_is_discarded_only_at_end(self):
        self.owner.audio_in_queue.put_nowait(b'\x01')
        self.task = asyncio.create_task(self.owner._play_audio())
        await asyncio.sleep(.25)
        self.stream.write.assert_not_called()
        self.owner.ui.write_log.assert_not_called()
        self.owner._fish_voice.pending = False
        self.owner._turn_done_event.set()
        await self.until(lambda: self.owner.ui.write_log.called)
        await asyncio.sleep(.15)
        self.owner.ui.write_log.assert_called_once()


class SegmentationBoundaryTests(unittest.IsolatedAsyncioTestCase):
    async def test_segment_limit_does_not_turn_decimal_into_sentence_boundary(self):
        voice = fish.FishVoiceSession(fixtures.owner())
        spoken = []
        async def source(text):
            spoken.append(text)
            yield fixtures.PCM[:2]
        # The decimal point lands exactly at the segmentation limit.
        text = 'Contexto ' + 'x ' * 193 + '123.45 reais no total.'
        limit = text.index('.') + 1
        try:
            with patch.object(fish, 'MAX_SEGMENT_CHARS', limit), patch.object(fish, 'pcm', source):
                voice.feed(text, flush=True)
                await voice.task
            self.assertEqual(' '.join(spoken), text)
            self.assertTrue(any('123.45' in segment for segment in spoken))
        finally:
            await voice.close()


if __name__ == '__main__':
    unittest.main()
