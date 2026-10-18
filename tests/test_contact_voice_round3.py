"""User-reported daily contact, barge-in and conversational style regressions."""
import asyncio
from datetime import datetime,timedelta
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import AsyncMock, Mock, patch

import numpy as np
from core import daily_briefing
from core.briefing_presentation import explicit_refresh, refresh_only
from core.voice_interrupt import VoiceInterruptGate
from main import JarvisLive
from test_command_chaos_round import assistant
from test_voice_interrupt import assistant_fixture


class RoutingTests(unittest.TestCase):
    def test_prefetched_context_respects_connections_disabled_after_collection(self):
        from core.session_refresh import enabled_context
        package={'data':{'gmail':{'items':[{'title':'Synthetic'}]},
                 'calendar':{'items':[],'refresh':{'provider':'google_calendar'}},
                 'tasks':{'items':[]}},'unavailable':[]}
        with patch('memory.config_manager.get_plugin_enabled',return_value=False):
            value=enabled_context(package)
        self.assertEqual(set(value['data']),{'tasks'})
        self.assertIn('gmail',package['data'])

    def test_context_update_variants_do_not_request_software_update(self):
        for phrase in ('se atualize','Jarvis, se atualize, por favor.',
                       'pode se atualizar agora?', 'por favor se atualiza',
                       'Jarvis atualize-se por gentileza'):
            self.assertTrue(refresh_only(phrase),phrase)
            self.assertTrue(explicit_refresh(phrase),phrase)
        for phrase in ('atualize o Windows','se atualize e abra o Gmail',
                       'nao se atualize','atualize o aplicativo'):
            self.assertFalse(refresh_only(phrase),phrase)

    def test_selective_server_silence_is_opt_in(self):
        from memory.config_manager import get_proactive_audio_enabled
        with patch('memory.config_manager.load_api_keys',return_value={}):
            self.assertFalse(get_proactive_audio_enabled())
        with patch('memory.config_manager.load_api_keys',return_value={'proactive_audio':True}):
            self.assertTrue(get_proactive_audio_enabled())


class VoiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_sustained_distinct_voice_interrupts_without_keyword_model(self):
        owner=assistant_fixture()
        owner._stop_keyword=None
        owner._echo=Mock();owner._echo.is_user_speech.return_value=True
        vad=Mock();vad.is_speech.return_value=True
        owner._voice_interrupt=VoiceInterruptGate(vad)
        loop=asyncio.get_running_loop()
        pcm=np.full((1024,1),9000,dtype=np.int16)
        for _ in range(4):owner._consider_voice_interruption(pcm,loop)
        await asyncio.sleep(0)
        self.assertFalse(owner._interrupted)
        owner._consider_voice_interruption(pcm,loop)
        await asyncio.sleep(0)
        self.assertTrue(owner._interrupted)
        self.assertGreater(owner.out_queue.qsize(),0)

    async def test_echo_and_short_noise_do_not_interrupt(self):
        for distinct in (False,True):
            owner=assistant_fixture();owner._stop_keyword=None
            owner._echo=Mock();owner._echo.is_user_speech.return_value=distinct
            vad=Mock();vad.is_speech.return_value=True
            owner._voice_interrupt=VoiceInterruptGate(vad)
            loop=Mock()
            pcm=np.full((1024,1),9000,dtype=np.int16)
            for _ in range(20 if not distinct else 2):owner._consider_voice_interruption(pcm,loop)
            loop.call_soon_threadsafe.assert_not_called()

    async def test_speech_during_refresh_silence_cancels_refresh(self):
        owner=assistant_fixture();owner._is_speaking=False
        owner._server_turn_open=False;owner._refresh_in_progress=True
        owner._accept_voice_interruption([b'new request'])
        owner._cancel_context_refresh.assert_called_once()
        self.assertEqual(owner.out_queue.get_nowait()['data'],b'new request')

    async def test_new_typed_request_can_interrupt_active_briefing(self):
        owner=assistant();owner.interrupt=Mock()
        task=asyncio.create_task(asyncio.sleep(60))
        owner._daily_briefing_task=task
        owner._route_protocol_user=AsyncMock(return_value=False)
        try:
            self.assertTrue(await owner._handle_text_command('vamos conversar'))
            owner.interrupt.assert_called_once()
            owner.session.send_client_content.assert_awaited_once()
        finally:
            task.cancel();await asyncio.gather(task,return_exceptions=True)


class DailyTests(unittest.IsolatedAsyncioTestCase):
    async def test_failed_or_legacy_attempt_cannot_block_updates_for_whole_day(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(daily_briefing,'STATE_FILE',Path(folder)/'day.json'):
            state={'automatic_attempt_date':datetime.now().date().isoformat()}
            daily_briefing.STATE_FILE.write_text(json.dumps(state))
            self.assertFalse(daily_briefing.automatic_attempted_today())
            state['automatic_attempt_at']=(datetime.now()-timedelta(minutes=6)).isoformat()
            daily_briefing.STATE_FILE.write_text(json.dumps(state))
            self.assertFalse(daily_briefing.automatic_attempted_today())
            daily_briefing.record_contact(automatic=True)
            self.assertTrue(daily_briefing.automatic_attempted_today())

    def owner(self):
        owner=assistant();owner._awake=True;owner._forge_mode=False
        owner.ui._win._ultron_payload=None
        owner._application_context=NS(user_text='bom dia')
        owner._daily_briefing_task=None;owner._turn_done_event=None
        owner._send_startup_briefing=AsyncMock()
        owner._response_busy=Mock(return_value=False)
        # Use the real scheduler rather than the command fixture stub.
        owner._queue_daily_briefing=JarvisLive._queue_daily_briefing.__get__(owner)
        return owner

    async def test_cancel_before_start_does_not_consume_daily_attempt(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(daily_briefing,'STATE_FILE',Path(folder)/'day.json'),patch('main.get_brief_enabled',return_value=True):
            owner=self.owner()
            owner._queue_daily_briefing(wait_for_turn=False)
            owner._application_context.user_text='outra pergunta'
            await owner._daily_briefing_task
            self.assertFalse(daily_briefing.automatic_attempted_today())
            self.assertTrue(owner._queue_daily_briefing(wait_for_turn=False))
            await owner._daily_briefing_task
            owner._send_startup_briefing.assert_awaited_once()

    async def test_existing_contact_without_delivery_does_not_block_new_day_update(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(daily_briefing,'STATE_FILE',Path(folder)/'day.json'),patch('main.get_brief_enabled',return_value=True):
            daily_briefing.record_contact()
            owner=self.owner()
            self.assertTrue(owner._queue_daily_briefing(wait_for_turn=False))
            await owner._daily_briefing_task
            self.assertTrue(daily_briefing.automatic_attempted_today())

    async def test_fetch_starts_without_waiting_for_opening_speech(self):
        owner=assistant();owner._awake=True;owner._refresh_summary=False
        owner._tail_active=Mock(return_value=False)
        owner._turn_done_event=asyncio.Event()
        started=asyncio.Event()
        async def collect(*args):
            started.set()
            await asyncio.Event().wait()
        owner._fish_voice=None
        owner.ui.show_manifestation=Mock();owner.ui.play_sound=Mock()
        with patch('core.fish_audio.selected',return_value=False),patch('core.session_refresh.collect_updates',side_effect=collect):
            task=asyncio.create_task(owner._send_startup_briefing())
            try:
                await asyncio.wait_for(started.wait(),1)
                self.assertFalse(owner._turn_done_event.is_set())
            finally:
                task.cancel();await asyncio.gather(task,return_exceptions=True)

    async def test_connection_prefetch_is_real_but_does_not_open_ui_or_speak(self):
        owner=assistant();owner.ui.show_manifestation=Mock()
        package={'data':{'tasks':{'items':[]}},'unavailable':[]}
        with patch('core.session_refresh.collect_updates',new=AsyncMock(return_value=package)) as collect:
            result=await owner._prepare_daily_context()
        self.assertEqual(result,package)
        self.assertEqual(owner._day_context,package)
        collect.assert_awaited_once()
        owner.ui.show_manifestation.assert_not_called()
        owner.session.send_client_content.assert_not_awaited()

    async def test_valid_long_news_audio_is_not_cut_at_one_minute(self):
        owner=assistant();owner._awake=True;owner._refresh_summary=True
        owner.ui.show_manifestation=Mock();owner.ui.play_sound=Mock()
        owner._tail_active=Mock(return_value=False)
        owner._played_audio_seconds=0.
        clock=NS(now=0.)
        class Voice:
            remaining=0
            _failed=False
            @property
            def pending(self):
                if not self.remaining:return False
                self.remaining-=1;clock.now+=7
                if not self.remaining:
                    owner._played_audio_seconds+=100
                    return False
                return True
            def feed(self,text,flush=False):
                self.remaining=8 if text.startswith('Estou') else 18
        owner._fish_voice=Voice()
        async def pause(_):pass
        chapter={'model':{'kind':'news'},'facts':{},'instruction':'Somente dados reais.'}
        with patch('main.time',NS(monotonic=lambda:clock.now)),patch('main.asyncio.sleep',side_effect=pause),patch('core.session_refresh.collect_updates',new=AsyncMock(return_value={'data':{'news':{}},'unavailable':[]})),patch('core.briefing_presentation.chapters',return_value=[chapter]),patch('core.briefing_narration.chapter_text',return_value=' '.join(['noticia']*200)),patch('core.daily_briefing.mark_delivered') as delivered:
            await owner._send_startup_briefing()
        self.assertGreater(clock.now,120)
        delivered.assert_called_once()


class PersonalityTests(unittest.IsolatedAsyncioTestCase):
    async def test_learned_style_reaches_current_session_without_new_reply(self):
        owner=assistant()
        # Restore the actual persistence/synchronization method on the fixture.
        owner._remember_user_turn=JarvisLive._remember_user_turn.__get__(owner)
        profile={'synthetic':'style'}
        with patch('core.conversation_memory.observe_user',return_value={'changed':True,'profile':profile}),patch('core.personality.prompt_context',return_value='safe style'):
            await owner._remember_user_turn('seja mais natural')
        owner.session.send_client_content.assert_awaited_once()
        self.assertFalse(owner.session.send_client_content.call_args.kwargs['turn_complete'])
        self.assertIn('safe style',owner.session.send_client_content.call_args.kwargs['turns']['parts'][0]['text'])

    async def test_unchanged_style_does_not_add_an_extra_remote_request(self):
        owner=assistant()
        owner._remember_user_turn=JarvisLive._remember_user_turn.__get__(owner)
        with patch('core.conversation_memory.observe_user',return_value={'changed':False}):
            await owner._remember_user_turn('como voce esta?')
        owner.session.send_client_content.assert_not_awaited()


class NewsTests(unittest.TestCase):
    def test_spoken_excerpt_does_not_cut_the_last_word(self):
        from core.briefing_narration import clean,chapter_text
        text='Noticia importante. '+('desenvolvimento cientifico ' * 30)
        result=clean(text,100)
        self.assertLessEqual(len(result),100)
        self.assertTrue(result.endswith(('.','!','?')))
        self.assertNotIn('desenvolv...',result)
        spoken=chapter_text({'facts':{'title':'Titulo','summary':'Um resumo completo'},'model':{'kind':'news'}})
        self.assertTrue(spoken.endswith('.'))
