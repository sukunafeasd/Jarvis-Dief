"""Protocol speech stays with its originating turn, session and mode generation."""
import asyncio
import threading
import unittest
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, Mock, patch

from main import JarvisLive


class ProtocolVoiceContextTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.owner=JarvisLive.__new__(JarvisLive)
        self.owner.session=NS(send_client_content=AsyncMock())
        self.owner._loop=asyncio.get_running_loop()
        self.owner._response_epoch=1
        self.owner._last_user_speech=10.
        self.owner._forge_mode=True
        self.owner._manual_rest=False
        self.owner._interrupted=False
        self.owner._is_speaking=False
        self.owner._fish_voice=Mock(pending=False)
        self.owner._routing_protocol_input=False
        self.owner._server_turn_open=False
        self.owner._protocol_input_consumed=True
        self.controller=NS(generation=2)
        self.owner.ui=NS(write_log=Mock(),_win=NS(_forge_controller=self.controller),
                         forge_runtime=NS(snapshot=Mock(return_value={'project':{'id':'old'}}),
                                          command=Mock(return_value={'accepted':True})))
        self.actual_input={'serial':1,'text':'Pedido sintetico'}
        self.owner.ui.ultron_user_context=lambda:dict(self.actual_input)
        self.provider=patch('core.fish_audio.httpx.AsyncClient',side_effect=AssertionError('Provider forbidden'))
        self.provider.start()
        self.addCleanup(self.provider.stop)

    async def asyncTearDown(self):
        task=getattr(self.owner,'_forge_notice_task',None)
        if task is not None:
            task.cancel()
            await asyncio.gather(task,return_exceptions=True)

    async def until(self,condition):
        async def wait():
            while not condition():await asyncio.sleep(.001)
        await asyncio.wait_for(wait(),2)

    async def queued_native(self):
        self.owner._fish_voice=None
        self.owner._routing_protocol_input=True
        with patch('core.fish_audio.selected',return_value=False):
            await self.owner._speak_protocol('Mensagem sintetica antiga')
        self.owner.session.send_client_content.assert_not_awaited()

    async def test_native_queue_rejects_interrupted_epoch_without_clearing_interrupt(self):
        await self.queued_native()
        self.owner._response_epoch+=1
        self.owner._interrupted=True
        with patch('core.fish_audio.selected',return_value=False):
            await self.owner._flush_protocol_voice()
        self.owner.session.send_client_content.assert_not_awaited()
        self.assertTrue(self.owner._interrupted)
        self.assertTrue(self.owner._protocol_input_consumed)
        self.assertEqual(self.owner._native_protocol_messages,[])

    async def test_native_queue_never_crosses_reconnect(self):
        await self.queued_native()
        old=self.owner.session
        self.owner.session=NS(send_client_content=AsyncMock())
        with patch('core.fish_audio.selected',return_value=False):
            await self.owner._flush_protocol_voice()
        old.send_client_content.assert_not_awaited()
        self.owner.session.send_client_content.assert_not_awaited()

    async def test_native_queue_rejects_new_actual_turn_with_unchanged_timestamp(self):
        await self.queued_native()
        self.actual_input.update(serial=2,text='Outro pedido sintetico')
        with patch('core.fish_audio.selected',return_value=False):
            await self.owner._flush_protocol_voice()
        self.owner.session.send_client_content.assert_not_awaited()

    async def test_delayed_dispatch_rejects_new_actual_turn_with_same_timestamp(self):
        task,release=await self.blocked_dispatch('status')
        try:self.actual_input.update(serial=2,text='Outro pedido sintetico')
        finally:release.set()
        await task
        self.owner._fish_voice.feed.assert_not_called()

    async def test_native_queue_drops_only_old_contact_and_keeps_new_message(self):
        await self.queued_native()
        self.owner._last_user_speech+=1
        with patch('core.fish_audio.selected',return_value=False):
            await self.owner._speak_protocol('Mensagem sintetica atual')
            await self.owner._flush_protocol_voice()
        sent=self.owner.session.send_client_content.call_args.kwargs['turns']['parts'][0]['text']
        self.assertIn('Mensagem sintetica atual',sent)
        self.assertNotIn('antiga',sent)

    async def test_native_queue_rejects_exit_and_reentry_generation(self):
        await self.queued_native()
        self.controller.generation+=2
        with patch('core.fish_audio.selected',return_value=False):
            await self.owner._flush_protocol_voice()
        self.owner.session.send_client_content.assert_not_awaited()

    async def test_native_same_context_batches_and_reopens_reply(self):
        await self.queued_native()
        with patch('core.fish_audio.selected',return_value=False):
            await self.owner._speak_protocol('Segunda mensagem')
            await self.owner._flush_protocol_voice()
        self.owner.session.send_client_content.assert_awaited_once()
        self.assertFalse(self.owner._protocol_input_consumed)
        self.assertEqual(self.owner._native_protocol_messages,[])

    async def test_selected_fish_never_silently_uses_native(self):
        self.owner._fish_voice=None
        with patch('core.fish_audio.selected',return_value=True):
            await self.owner._speak_protocol('Mensagem sem voz disponivel')
        self.owner.session.send_client_content.assert_not_awaited()

    async def test_explicit_entry_and_exit_speeches_use_current_mode(self):
        voice=self.owner._fish_voice
        await self.owner._speak_protocol('Modo Forja ativo')
        self.owner._forge_mode=False
        self.controller.generation+=1
        await self.owner._speak_protocol('Modo Forja desativado')
        self.assertEqual([call.args[0] for call in voice.feed.call_args_list],
                         ['Modo Forja ativo','Modo Forja desativado'])

    def snapshot(self):
        return {'phase':'ready','generation_verified':True,'project':{'id':'old'},'turn_id':'old'}

    async def waiting_snapshot(self):
        self.owner._is_speaking=True
        self.owner._on_forge_snapshot(self.snapshot())
        await self.until(lambda:getattr(self.owner,'_forge_notice_task',None) is not None)

    async def test_snapshot_waiting_for_voice_is_discarded_on_reconnect(self):
        await self.waiting_snapshot()
        self.owner.session=NS(send_client_content=AsyncMock())
        voice=Mock(pending=False)
        self.owner._fish_voice=voice
        self.owner._is_speaking=False
        await asyncio.wait_for(self.owner._forge_notice_task,1)
        voice.feed.assert_not_called()

    async def test_snapshot_exit_reentry_cannot_reuse_old_notice(self):
        await self.waiting_snapshot()
        self.controller.generation+=2
        self.owner._is_speaking=False
        await asyncio.wait_for(self.owner._forge_notice_task,1)
        self.owner._fish_voice.feed.assert_not_called()
        old_task=self.owner._forge_notice_task
        self.owner._on_forge_snapshot(self.snapshot())
        await self.until(lambda:self.owner._forge_notice_task is not old_task)
        await asyncio.wait_for(self.owner._forge_notice_task,1)
        self.owner._fish_voice.feed.assert_called_once()

    async def test_snapshot_waiting_notice_is_discarded_on_new_contact(self):
        await self.waiting_snapshot()
        self.owner._last_user_speech+=1
        self.owner._is_speaking=False
        await asyncio.wait_for(self.owner._forge_notice_task,1)
        self.owner._fish_voice.feed.assert_not_called()

    async def test_old_scheduled_snapshot_cannot_replace_newer_quiet_state(self):
        self.owner._on_forge_snapshot(self.snapshot())
        self.owner._on_forge_snapshot({'phase':'ready','authenticated':True})
        await asyncio.sleep(.02)
        self.owner._fish_voice.feed.assert_not_called()

    async def test_waiting_snapshot_is_superseded_by_current_status(self):
        await self.waiting_snapshot()
        self.owner._on_forge_snapshot({'phase':'error','error':'Falha sintetica atual'})
        await self.until(lambda:self.owner._forge_pending_notice[1]['title']=='Trabalho interrompido')
        self.owner._is_speaking=False
        await asyncio.wait_for(self.owner._forge_notice_task,1)
        self.owner._fish_voice.feed.assert_called_once()
        self.assertIn('Falha sintetica atual',self.owner._fish_voice.feed.call_args.args[0])

    async def test_waiting_snapshot_is_cleared_by_quiet_state(self):
        await self.waiting_snapshot()
        self.owner._on_forge_snapshot({'phase':'ready','authenticated':True})
        self.owner._is_speaking=False
        await asyncio.wait_for(self.owner._forge_notice_task,1)
        self.owner._fish_voice.feed.assert_not_called()

    async def test_explicit_native_exit_discards_pending_entry_speech(self):
        await self.queued_native()
        self.owner._forge_mode=False
        self.controller.generation+=1
        self.owner._routing_protocol_input=False
        with patch('core.fish_audio.selected',return_value=False):
            await self.owner._speak_protocol('Modo Forja desativado')
        sent=self.owner.session.send_client_content.call_args.kwargs['turns']['parts'][0]['text']
        self.assertIn('Modo Forja desativado',sent)
        self.assertNotIn('antiga',sent)

    async def blocked_dispatch(self,action,block_command=False):
        started=threading.Event();release=threading.Event()
        def block(*args,**kwargs):
            started.set()
            if not release.wait(2):raise TimeoutError('Offline fixture timed out')
            return {'accepted':True} if block_command else self.snapshot()
        runtime=self.owner.ui.forge_runtime
        if block_command:runtime.command.side_effect=block
        else:runtime.snapshot.side_effect=block
        task=asyncio.create_task(self.owner._dispatch_forge({'action':action}))
        await self.until(started.is_set)
        return task,release

    async def test_status_result_after_exit_does_not_speak_on_new_session(self):
        task,release=await self.blocked_dispatch('status')
        try:
            self.owner._forge_mode=False
            self.owner.session=NS(send_client_content=AsyncMock())
        finally:release.set()
        await task
        self.owner._fish_voice.feed.assert_not_called()

    async def test_stale_snapshot_does_not_start_command(self):
        task,release=await self.blocked_dispatch('save')
        try:self.owner._response_epoch+=1
        finally:release.set()
        await task
        self.owner.ui.forge_runtime.command.assert_not_called()
        self.owner._fish_voice.feed.assert_not_called()

    async def test_completed_command_after_new_generation_has_no_old_confirmation(self):
        task,release=await self.blocked_dispatch('save',block_command=True)
        try:self.controller.generation+=2
        finally:release.set()
        await task
        self.owner.ui.forge_runtime.command.assert_called_once_with('save')
        self.owner._fish_voice.feed.assert_not_called()

    async def test_current_command_still_speaks_confirmation(self):
        await self.owner._dispatch_forge({'action':'save'})
        self.owner._fish_voice.feed.assert_called_once_with('Projeto salvo.',flush=True)


if __name__=='__main__':unittest.main()
