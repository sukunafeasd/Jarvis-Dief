"""Synthetic failures and measured work counts; no providers or physical audio."""
import asyncio
import threading
import unittest
from unittest.mock import AsyncMock, patch

from core.bounded_work import BoundedWork
from actions import web_search
from tests.test_voice_interrupt import assistant_fixture
from tests import test_fish_playback as playback


class WorkerBudgetTests(unittest.TestCase):
    def test_timeouts_do_not_spawn_more_workers_or_run_cancelled_queue(self):
        pool=BoundedWork(workers=2,capacity=3,name='BoundedSearchTest')
        release=threading.Event();lock=threading.Lock();calls=[]
        def blocked():
            with lock:calls.append(1)
            release.wait(2)
            return 'late'
        try:
            with patch.object(web_search,'_SEARCH_WORK',pool):
                self.assertEqual(web_search._parallel_bounded([blocked,blocked],.03),[None,None])
                for _ in range(8):self.assertIsNone(web_search._run_bounded(blocked,.005))
                self.assertEqual(len(pool.threads),2)
                self.assertEqual(len(calls),2)
        finally:
            pool.close();release.set()
            for worker in pool.threads:worker.join(1)
        self.assertEqual(len(calls),2)
        self.assertTrue(all(not worker.is_alive() for worker in pool.threads))

    def test_parallel_batch_preserves_order_and_reuses_fixed_pool(self):
        pool=BoundedWork(workers=2,capacity=6)
        try:
            with patch.object(web_search,'_SEARCH_WORK',pool):
                self.assertEqual(web_search._parallel_bounded([lambda i=i:i for i in range(8)],1,workers=2),list(range(8)))
                self.assertEqual(len(pool.threads),2)
        finally:
            pool.close()
            for worker in pool.threads:worker.join(1)


class NoticeRecoveryTests(unittest.IsolatedAsyncioTestCase):
    def owner(self):
        owner=assistant_fixture();owner._is_speaking=False;owner._server_turn_open=False
        owner._fish_voice=None;owner._turn_done_event.set()
        owner.session=AsyncMock()
        return owner

    async def test_failed_send_releases_fictitious_turn(self):
        owner=self.owner();owner.session.send_client_content.side_effect=OSError('offline')
        owner._protocol_input_consumed=True
        with self.assertRaises(OSError):await owner._send_host_notice(owner.session,'Aviso de teste')
        self.assertFalse(owner._server_turn_open)
        self.assertTrue(owner._turn_done_event.is_set())
        self.assertFalse(owner._response_busy())
        self.assertTrue(owner._protocol_input_consumed)
        owner.ui.set_state.assert_called_with('LISTENING')

    async def test_failed_old_notice_cannot_close_newer_turn(self):
        owner=self.owner()
        async def replace(**kwargs):
            owner._response_epoch+=1
            raise OSError('offline')
        owner.session.send_client_content.side_effect=replace
        with self.assertRaises(OSError):await owner._send_host_notice(owner.session,'Aviso antigo')
        self.assertTrue(owner._server_turn_open)
        self.assertFalse(owner._turn_done_event.is_set())

    async def test_cancelled_notice_releases_its_own_turn(self):
        owner=self.owner();started=asyncio.Event()
        async def blocked(**kwargs):started.set();await asyncio.Event().wait()
        owner.session.send_client_content.side_effect=blocked
        task=asyncio.create_task(owner._send_host_notice(owner.session,'Aviso de teste'))
        await started.wait();task.cancel()
        with self.assertRaises(asyncio.CancelledError):await task
        self.assertFalse(owner._server_turn_open)
        self.assertTrue(owner._turn_done_event.is_set())


class NativeAudioGapTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=playback.PlaybackIntegrationTests.asyncSetUp
    asyncTearDown=playback.PlaybackIntegrationTests.asyncTearDown
    wait_for_write=playback.PlaybackIntegrationTests.wait_for_write

    async def test_native_pause_waits_for_actual_generation_end(self):
        self.owner._fish_voice=None
        self.owner._server_turn_open=True
        self.owner.audio_in_queue.put_nowait(playback.PCM[:2400])
        self.task=asyncio.create_task(self.owner._play_audio())
        await self.wait_for_write();await asyncio.sleep(.3)
        self.owner.ui.set_state.assert_called_with('THINKING')
        self.assertNotIn('LISTENING',[call.args[0] for call in self.owner.ui.set_state.call_args_list])
        self.owner.audio_in_queue.put_nowait(playback.PCM[2400:4800])
        async def second_write():
            while self.stream.write.call_count<2:await asyncio.sleep(.005)
        await asyncio.wait_for(second_write(),1)
        self.owner.ui.set_state.assert_called_with('SPEAKING')
        self.owner._server_turn_open=False;self.owner._turn_done_event.set()
        await asyncio.sleep(.3)
        self.owner.ui.set_state.assert_called_with('LISTENING')
        self.assertEqual(b''.join(call.args[0] for call in self.stream.write.call_args_list),playback.PCM[:4800])
