import asyncio
import unittest
from unittest.mock import Mock, AsyncMock, patch
import test_voice_interrupt
import main


class AudioEighthAudit(unittest.IsolatedAsyncioTestCase):
    async def test_audio_write_is_not_held_by_viseme_analysis(self):
        assistant=test_voice_interrupt.assistant_fixture()
        assistant.set_speaking=Mock()
        data=b'\0'*2400
        assistant.audio_in_queue.get=AsyncMock(side_effect=[data,asyncio.CancelledError()])
        stream=Mock();stream.latency=.15
        written=asyncio.Event()
        order=[]
        async def thread(function,*args):
            if function==stream.write:
                written.set()
                order.append('write')
                return False
            if function==main._pcm_visemes:
                await asyncio.wait_for(written.wait(),.1)
                order.append('analysis-finished')
                return []
            return function(*args)
        with patch.object(main.sd,'RawOutputStream',return_value=stream) as opened,patch.object(main,'get_output_device',return_value=''),patch.object(main.audio_devices,'resolve',return_value=None),patch.object(main.asyncio,'to_thread',side_effect=thread):
            with self.assertRaises(asyncio.CancelledError):await assistant._play_audio()
        self.assertTrue(written.is_set())
        self.assertEqual(order,['write','analysis-finished'])
        self.assertEqual(opened.call_args.kwargs['blocksize'],0)
        self.assertEqual(opened.call_args.kwargs['latency'],'high')
        assistant.ui.presentation_audio.assert_called_once_with(.05)
        stream.close.assert_called_once()

    async def test_cancelled_analysis_waits_for_audio_write_before_close(self):
        assistant=test_voice_interrupt.assistant_fixture();assistant.set_speaking=Mock()
        assistant.audio_in_queue.get=AsyncMock(return_value=b'\0'*2400)
        stream=Mock();stream.latency=.1
        completed=[]
        async def thread(function,*args):
            if function==stream.write:
                await asyncio.sleep(.02);completed.append('write');return False
            if function==main._pcm_visemes:
                raise asyncio.CancelledError()
            return function(*args)
        stream.close.side_effect=lambda:completed.append('close')
        with patch.object(main.sd,'RawOutputStream',return_value=stream),patch.object(main,'get_output_device',return_value=''),patch.object(main.audio_devices,'resolve',return_value=None),patch.object(main.asyncio,'to_thread',side_effect=thread):
            with self.assertRaises(asyncio.CancelledError):await assistant._play_audio()
        self.assertEqual(completed,['write','close'])
