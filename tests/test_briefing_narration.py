import asyncio
import unittest
from unittest.mock import AsyncMock, Mock, patch

from core.briefing_narration import chapter_text
from core.briefing_presentation import chapters


class FactsTests(unittest.TestCase):
    def test_zero_temperature_and_rain_are_spoken(self):
        text=chapter_text(chapters({'data':{'weather':{'temperature':0,'rain':0}}})[0])
        self.assertIn('0 graus',text)
        self.assertIn('0 por cento',text)

    def test_weather_uses_only_returned_measurements(self):
        chapter = chapters({'data': {'weather': {'city': 'Teste', 'temperature': 19, 'condition': 'Chuva'}}})[0]
        text = chapter_text(chapter)
        self.assertIn('19 graus', text)
        self.assertIn('Chuva', text)
        self.assertNotIn('probabilidade', text)

    def test_news_is_the_focused_article_not_the_whole_list(self):
        sequence = chapters({'data': {'news': {'model': {'kind': 'news', 'items': [
            {'title': 'Primeira', 'summary': 'Resumo A'}, {'title': 'Segunda', 'summary': 'Resumo B'}]}}}})
        self.assertIn('Resumo A', chapter_text(sequence[0]))
        self.assertNotIn('Segunda', chapter_text(sequence[0]))
        self.assertIn('Resumo B', chapter_text(sequence[1]))

    def test_gmail_does_not_claim_body_read(self):
        text = chapter_text(chapters({'data': {'gmail': {'items': [{'title': 'Assunto', 'detail': 'Equipe'}]}}})[0])
        self.assertIn('ainda não foram lidos', text)


class DirectBriefingTests(unittest.IsolatedAsyncioTestCase):
    async def test_consumer_marks_audio_before_wait_for_returns(self):
        from main import JarvisLive
        owner=JarvisLive.__new__(JarvisLive)
        owner.audio_in_queue=asyncio.Queue()
        owner._audio_batch_pending=False
        consumer=asyncio.create_task(owner._next_audio_chunk())
        await asyncio.sleep(0)
        owner.audio_in_queue.put_nowait(b'\x00\x00')
        await asyncio.sleep(0)
        self.assertTrue(consumer.done())
        self.assertTrue(owner.audio_in_queue.empty())
        self.assertTrue(owner._audio_batch_pending)
        self.assertEqual(await consumer,b'\x00\x00')

    async def test_partial_audio_failure_does_not_count_as_a_completed_summary(self):
        from main import JarvisLive
        owner = JarvisLive.__new__(JarvisLive)
        owner.session = Mock(send_client_content=AsyncMock())
        owner._response_epoch=0
        owner._manual_rest = False
        owner._awake = True
        owner._is_speaking = False
        owner._played_audio_seconds = 0.
        owner.audio_in_queue = asyncio.Queue()
        owner._tail_active = Mock(return_value=False)
        owner._turn_done_event = asyncio.Event()
        owner.ui = Mock()
        owner._fish_voice = Mock(pending=False)
        def fail(text, flush=False):
            owner._played_audio_seconds += .1
            owner._fish_voice._failed = True
        owner._fish_voice.feed.side_effect = fail
        with patch('core.session_refresh.collect_updates', AsyncMock(return_value={'data': {}, 'unavailable': []})), patch('core.daily_briefing.mark_delivered') as mark:
            with self.assertRaisesRegex(RuntimeError, 'voz falhou'):
                await owner._send_startup_briefing()
            mark.assert_not_called()

    async def test_fish_briefing_does_not_request_generation_per_chapter(self):
        from main import JarvisLive
        owner = JarvisLive.__new__(JarvisLive)
        owner.session = Mock(send_client_content=AsyncMock())
        owner._response_epoch=0
        owner._manual_rest = False
        owner._awake = True
        owner._is_speaking = False
        owner._played_audio_seconds = 0.
        owner.audio_in_queue = asyncio.Queue()
        owner._tail_active = Mock(return_value=False)
        owner._turn_done_event = asyncio.Event()
        owner.ui = Mock()
        owner._fish_voice = Mock(pending=False)
        def feed(text, flush=False):
            self.assertTrue(flush)
            owner._played_audio_seconds += 1
        owner._fish_voice.feed.side_effect = feed
        package = {'data': {'weather': {'temperature': 21}, 'tasks': {'items': []}}, 'unavailable': []}
        with patch('core.session_refresh.collect_updates', AsyncMock(return_value=package)), patch('core.daily_briefing.mark_delivered') as mark:
            await owner._send_startup_briefing()
            mark.assert_called_once()
        self.assertEqual(owner._fish_voice.feed.call_count, 3)
        owner.session.send_client_content.assert_awaited_once()
        self.assertFalse(owner.session.send_client_content.call_args.kwargs['turn_complete'])
        self.assertFalse(owner._refresh_in_progress)

    async def test_voice_failure_cannot_mark_summary_delivered(self):
        from main import JarvisLive
        owner = JarvisLive.__new__(JarvisLive)
        owner.session = Mock(send_client_content=AsyncMock())
        owner._response_epoch=0
        owner._manual_rest = False
        owner._awake = True
        owner._is_speaking = False
        owner._played_audio_seconds = 0.
        owner.audio_in_queue = asyncio.Queue()
        owner._tail_active = Mock(return_value=False)
        owner._turn_done_event = asyncio.Event()
        owner.ui = Mock()
        owner._fish_voice = Mock(pending=False)
        with patch('core.session_refresh.collect_updates', AsyncMock(return_value={'data': {}, 'unavailable': []})), patch('core.daily_briefing.mark_delivered') as mark:
            with self.assertRaisesRegex(RuntimeError, 'sem audio'):
                await owner._send_startup_briefing()
            mark.assert_not_called()
        self.assertFalse(owner._refresh_in_progress)
