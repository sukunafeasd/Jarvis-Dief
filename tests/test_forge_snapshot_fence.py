"""Delayed FORJA updates cannot represent a newer user command."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock,patch

from core.forge import Runtime
from core.forge_controller import ForgeController
from core.forge_status import snapshot_current,summary
import test_protocol_voice_context_round as voice_tests


class RuntimeFenceTests(unittest.TestCase):
    def test_admission_and_submission_order_are_atomic_across_threads(self):
        with tempfile.TemporaryDirectory() as folder:
            runtime=Runtime(data_root=Path(folder)/'forge')
            before_submit=threading.Event();allow_submit=threading.Event();second_submitted=threading.Event()
            first_started=threading.Event();second_started=threading.Event()
            finish_first=threading.Event();finish_second=threading.Event();attempted_second=threading.Event()
            original=runtime._submit;submissions=[]
            def submit(coroutine):
                submissions.append(runtime._command_epoch)
                if len(submissions)==1:
                    before_submit.set();allow_submit.wait(2)
                else:second_submitted.set()
                return original(coroutine)
            async def work(action,prompt,*args):
                async with runtime.operation_lock:
                    started,release=(first_started,finish_first) if prompt=='first' else (second_started,finish_second)
                    started.set();await asyncio.to_thread(release.wait,2)
                    return {'accepted':True}
            def second():
                attempted_second.set();return runtime.command('steer',prompt='second')
            try:
                with patch.object(runtime,'_submit',submit),patch.object(runtime,'_command',work),ThreadPoolExecutor(max_workers=2) as pool:
                    first=pool.submit(runtime.command,'steer',prompt='first')
                    self.assertTrue(before_submit.wait(2))
                    later=pool.submit(second)
                    self.assertTrue(attempted_second.wait(2))
                    try:
                        self.assertFalse(second_submitted.wait(.03))
                        allow_submit.set()
                        self.assertTrue(first_started.wait(2));self.assertTrue(second_submitted.wait(2))
                        finish_first.set();self.assertTrue(second_started.wait(2))
                        self.assertTrue(runtime.snapshot()['command_pending'])
                        self.assertEqual(runtime.display_epoch(),2)
                    finally:allow_submit.set();finish_first.set();finish_second.set()
                    self.assertTrue(first.result(timeout=3)['accepted']);self.assertTrue(later.result(timeout=3)['accepted'])
                    self.assertEqual(submissions,[1,2])
                self.assertFalse(runtime.snapshot()['command_pending'])
            finally:allow_submit.set();finish_first.set();finish_second.set();runtime.close()
    def test_delayed_poll_is_rejected_before_new_snapshot_is_displayed(self):
        with tempfile.TemporaryDirectory() as folder:
            runtime=Runtime(data_root=Path(folder)/'forge')
            started=threading.Event();release=threading.Event()
            async def work(*args):
                started.set()
                await asyncio.to_thread(release.wait,2)
                runtime._update(phase='running',turn_id='new-turn')
                return {'accepted':True}
            old=runtime.snapshot()
            old.update(phase='ready',preview_validation='passed',preview_url='http://127.0.0.1:1111/old',turn_id='old-turn')
            token=object();callback=Mock();page=Mock()
            controller=NS(phase='ready',generation=1,_polling=token,_snapshot={},
                window=NS(_forge_runtime=runtime,on_forge_snapshot=callback),
                interceptor=NS(preview_port=None),_validating=None,_validated_revisions=set(),
                view=NS(page=lambda:page),_signature='')
            try:
                with patch.object(runtime,'_command',work),ThreadPoolExecutor(max_workers=1) as pool:
                    future=pool.submit(runtime.command,'steer',prompt='Novo pedido')
                    self.assertTrue(started.wait(2))
                    try:
                        self.assertFalse(snapshot_current(old,runtime))
                        pending=runtime.snapshot()
                        self.assertTrue(pending['command_pending'])
                        self.assertNotEqual(summary(pending)['status'],'completed')
                        ForgeController._update(controller,{'poll_token':token,'generation':1,'snapshot':old})
                        self.assertEqual(controller._snapshot,{})
                        self.assertFalse(controller._polling)
                        callback.assert_not_called();page.runJavaScript.assert_not_called()
                    finally:release.set()
                    self.assertTrue(future.result(timeout=3)['accepted'])
                current=runtime.snapshot()
                self.assertFalse(current['command_pending'])
                self.assertTrue(snapshot_current(current,runtime))
                ForgeController._update(controller,current)
                self.assertEqual(controller._snapshot['turn_id'],'new-turn')
                callback.assert_called_once()
            finally:release.set();runtime.close()

    def test_new_pending_command_does_not_report_previous_preview_completed(self):
        state={'phase':'ready','command_pending':True,'preview_validation':'passed','preview_url':'old'}
        self.assertEqual(summary(state)['status'],'waiting')

    def test_timed_out_new_command_cannot_fall_back_to_previous_success(self):
        with tempfile.TemporaryDirectory() as folder:
            runtime=Runtime(data_root=Path(folder)/'forge')
            def timeout(future):
                future.cancel();raise TimeoutError('synthetic timeout')
            try:
                runtime._update(phase='ready',preview_url='old',preview_validation='passed')
                with patch.object(runtime,'_wait',timeout):
                    with self.assertRaises(TimeoutError):runtime.command('steer',prompt='New request')
                state=runtime.snapshot()
                self.assertFalse(state['command_pending'])
                self.assertEqual(summary(state)['status'],'failed')
                self.assertEqual(state['preview_url'],'old')
            finally:runtime.close()


class VoiceFenceTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=voice_tests.ProtocolVoiceContextTests.asyncSetUp
    asyncTearDown=voice_tests.ProtocolVoiceContextTests.asyncTearDown
    until=voice_tests.ProtocolVoiceContextTests.until

    def snapshot(self):
        return {'phase':'ready','preview_validation':'passed','preview_url':'old',
                'project':{'id':'old'},'turn_id':'old','command_epoch':1}

    async def test_old_snapshot_cannot_attach_to_new_user_context(self):
        self.owner.ui._win._forge_runtime=NS(display_epoch=lambda:2)
        self.owner._on_forge_snapshot(self.snapshot())
        await asyncio.sleep(.02)
        self.owner._fish_voice.feed.assert_not_called()
        self.assertIsNone(getattr(self.owner,'_forge_notice_task',None))

    async def test_waiting_notice_rechecks_command_epoch_before_speaking(self):
        epoch=[1]
        self.owner.ui._win._forge_runtime=NS(display_epoch=lambda:epoch[0])
        self.owner._is_speaking=True
        self.owner._on_forge_snapshot(self.snapshot())
        await self.until(lambda:getattr(self.owner,'_forge_notice_task',None) is not None)
        epoch[0]=2;self.owner._is_speaking=False
        await asyncio.wait_for(self.owner._forge_notice_task,1)
        self.owner._fish_voice.feed.assert_not_called()

    async def test_new_notice_uses_its_own_epoch_when_replacing_waiting_notice(self):
        epoch=[1]
        self.owner.ui._win._forge_runtime=NS(display_epoch=lambda:epoch[0])
        self.owner._is_speaking=True
        self.owner._on_forge_snapshot(self.snapshot())
        await self.until(lambda:getattr(self.owner,'_forge_notice_task',None) is not None)
        epoch[0]=2
        self.owner._on_forge_snapshot({**self.snapshot(),'command_epoch':2,'phase':'error','error':'Falha atual de teste'})
        await self.until(lambda:self.owner._forge_pending_notice[1]['status']=='failed')
        self.owner._is_speaking=False
        await asyncio.wait_for(self.owner._forge_notice_task,1)
        self.owner._fish_voice.feed.assert_called_once()
        self.assertIn('Falha atual de teste',self.owner._fish_voice.feed.call_args.args[0])

    async def test_dispatch_before_runtime_admission_suppresses_old_notices(self):
        from main import JarvisLive
        started=asyncio.Event();release=asyncio.Event()
        async def dispatch(command):started.set();await release.wait()
        with patch.object(self.owner,'_dispatch_forge_command',dispatch):
            task=asyncio.create_task(JarvisLive._dispatch_forge(self.owner,{'action':'steer'}))
            await started.wait()
            try:
                self.owner._on_forge_snapshot(self.snapshot())
                await asyncio.sleep(.02)
                self.owner._fish_voice.feed.assert_not_called()
                self.assertIsNone(getattr(self.owner,'_forge_notice_task',None))
            finally:release.set();await task
        self.assertEqual(self.owner._forge_dispatch_depth,0)
