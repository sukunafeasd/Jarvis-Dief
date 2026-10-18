import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock,patch


class LibraryTests(unittest.TestCase):
    def test_bundled_skills_have_valid_integrity(self):
        from core.skill_library import entries,run
        items=entries()
        self.assertGreaterEqual(len(items),23)
        self.assertTrue(all(item['available'] for item in items))
        self.assertTrue(all(not item['scripts_allowed'] for item in items))
        for item in items:self.assertTrue(run({'action':'read','id':item['id']})['text'])

    def test_corrupt_skill_is_not_read(self):
        from core import skill_library as library
        with tempfile.TemporaryDirectory() as folder,patch.object(library,'ROOT',Path(folder)):
            (Path(folder)/'SKILL.md').write_text('unsafe')
            (Path(folder)/'manifest.json').write_text(json.dumps([{'id':'test','path':'SKILL.md','sha256':'bad'}]))
            with self.assertRaises(ValueError):library.run({'action':'read','id':'test'})

    def test_missing_accounts_are_not_connected(self):
        from core.extension_suite import status
        with patch('core.integration_tokens.read',return_value={}):
            for name in ('github_mcp','context7','deep_research'):
                value=status(name);self.assertFalse(value['connected']);self.assertFalse(value['authorized'])

    def test_unreadable_voice_credential_does_not_break_startup(self):
        from core.fish_audio import enabled,status
        with patch('core.integration_tokens.read',side_effect=ValueError('invalid protected token')):
            self.assertFalse(enabled());self.assertFalse(status()['connected'])

    def test_schema_only_exposes_real_actions(self):
        from core.extension_plugin import definition
        self.assertEqual(definition('markitdown')['parameters']['properties']['action']['enum'],['status','read'])
        self.assertNotIn('call',definition('deep_research')['parameters']['properties']['action']['enum'])

    def test_planets_have_sources_and_comparisons(self):
        from plugins.planet_knowledge import facts
        result=facts({'action':'compare','planet':'earth','other':'mars'})
        self.assertEqual(len(result['items']),2)
        self.assertTrue(all(item['source'].startswith('https://science.nasa.gov/') for item in result['items']))
        self.assertTrue(result['artistic_scale'])

    def test_greeting_with_direct_command_is_not_refresh_only(self):
        from core.briefing_presentation import refresh_only
        self.assertFalse(refresh_only('Bom dia, abra a calculadora'))
        self.assertFalse(refresh_only('Jarvis, se atualize e abra o Spotify'))
        self.assertTrue(refresh_only('Jarvis, se atualize'))
        self.assertTrue(refresh_only('me atualize sobre o dia'))

    def test_tools_and_continuation_block_daily_briefing(self):
        from main import JarvisLive
        owner=JarvisLive.__new__(JarvisLive);owner._is_speaking=False;owner._tail_active=lambda:False;owner.audio_in_queue=None;owner._fish_voice=None
        owner._tools_inflight=1;owner._tool_continuation=False;owner._server_turn_open=False
        self.assertTrue(owner._response_busy());owner._tools_inflight=0;owner._tool_continuation=True
        self.assertTrue(owner._response_busy());owner._tool_continuation=False
        self.assertFalse(owner._response_busy())


class FishTests(unittest.IsolatedAsyncioTestCase):
    async def test_opening_greeting_is_exact_and_waits_for_human(self):
        from main import JarvisLive
        from unittest.mock import AsyncMock
        owner=JarvisLive.__new__(JarvisLive)
        owner.session=Mock();owner._manual_rest=False;owner._is_speaking=False;owner._application_context=Mock(user_text='')
        owner._welcome_sent=False;owner._awaiting_welcome_reply=False;owner._turn_done_event=asyncio.Event();owner._fish_voice=Mock();owner.ui=Mock()
        owner._tail_until=0.;owner.audio_in_queue=asyncio.Queue();owner._fish_voice.pending=False
        owner._server_turn_open=False;owner._tool_continuation=False;owner._tools_inflight=0;owner._audio_batch_pending=False
        with patch('main.asyncio.sleep',new=AsyncMock()):await owner._opening_greeting()
        owner._fish_voice.feed.assert_called_once_with('Bem-vindo, senhor.',flush=True)
        self.assertTrue(owner._awaiting_welcome_reply)
        self.assertTrue(owner._welcome_sent)
        self.assertTrue(owner._turn_done_event.is_set())
        with patch('main.asyncio.sleep',new=AsyncMock()):await owner._opening_greeting()
        owner._fish_voice.feed.assert_called_once_with('Bem-vindo, senhor.',flush=True)
        owner.session.send_client_content.assert_not_called()

    def owner(self):
        value=Mock();value._response_epoch=0;value._manual_rest=False;value.ui=Mock();value.audio_in_queue=asyncio.Queue()
        return value

    async def test_partial_text_is_cleared_on_cancel(self):
        from core.fish_audio import FishVoiceSession
        owner=self.owner();voice=FishVoiceSession(owner);voice.feed('Texto incompleto')
        self.assertTrue(voice.pending)
        owner._response_epoch+=1;voice.cancel();await asyncio.sleep(0)
        self.assertFalse(voice.pending);self.assertEqual(voice.buffer,'');await voice.close()

    async def test_pcm_delivery_is_driven_by_actual_voice_audio(self):
        from core.fish_audio import FishVoiceSession
        owner=self.owner();voice=FishVoiceSession(owner)
        async def source(text):yield b'\x00\x00'*1200
        with patch('core.fish_audio.pcm',source):
            voice.feed('Bem-vindo, senhor.',flush=True);await voice.task
        self.assertEqual(owner.audio_in_queue.qsize(),1)
        owner.ui.narration_text.assert_called_once()
        self.assertAlmostEqual(voice.cursor,.05);await voice.close()

    async def test_provider_failure_has_no_duplicate_partial_audio(self):
        from core.fish_audio import FishVoiceSession
        owner=self.owner();voice=FishVoiceSession(owner)
        async def source(text):
            yield b'\x00\x00'*1200
            raise ValueError('network')
        with patch('core.fish_audio.pcm',source):
            voice.feed('Uma frase.',flush=True);await voice.task
        self.assertEqual(owner.audio_in_queue.qsize(),1)
        self.assertEqual(owner.audio_in_queue.get_nowait(),b'\x00\x00'*1200)
        self.assertTrue(voice._failed);await voice.close()

    async def test_provider_failure_before_audio_preserves_configured_voice(self):
        from core.fish_audio import FishVoiceSession
        owner=self.owner();voice=FishVoiceSession(owner)
        async def failed(text):
            raise ValueError('network')
            yield b''
        with patch('core.fish_audio.pcm',failed):
            voice.feed('Uma frase.',flush=True);await voice.task
        self.assertEqual(owner.audio_in_queue.qsize(),0)
        self.assertTrue(voice._failed)
        owner.ui.write_log.assert_called_once()
        await voice.close()


if __name__=='__main__':unittest.main()
