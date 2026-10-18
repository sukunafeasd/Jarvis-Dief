import asyncio
import json
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

from core import daily_briefing


class DailyStateTests(unittest.TestCase):
    def test_greeting_and_absence_do_not_repeat_delivered_summary(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(daily_briefing,'STATE_FILE',Path(folder)/'state.json'):
            now = datetime(2026,10,11,14,0)
            record = {'date':now.date().isoformat(),'updated_at':(now-timedelta(minutes=5)).isoformat(),'last_contact':(now-timedelta(hours=5)).isoformat()}
            daily_briefing.STATE_FILE.write_text(json.dumps(record))
            self.assertFalse(daily_briefing.refresh_due('bom dia jarvis',now))
            record['updated_at']=(now-timedelta(hours=5)).isoformat()
            daily_briefing.STATE_FILE.write_text(json.dumps(record))
            self.assertFalse(daily_briefing.refresh_due('oi',now))
            record['last_contact']=(now-timedelta(minutes=1)).isoformat()
            daily_briefing.STATE_FILE.write_text(json.dumps(record))
            self.assertFalse(daily_briefing.refresh_due('oi',now))
            self.assertFalse(daily_briefing.refresh_due('bom dia jarvis',now))
            self.assertTrue(daily_briefing.refresh_due('se atualiza do dia',now))
    def test_delivery_survives_restart_and_expires_next_day(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(daily_briefing, "STATE_FILE", Path(folder)/"state.json"):
            self.assertFalse(daily_briefing.delivered_today())
            daily_briefing.mark_delivered()
            self.assertTrue(daily_briefing.delivered_today())
            daily_briefing.STATE_FILE.write_text(json.dumps({"date": (date.today()-timedelta(days=1)).isoformat()}))
            self.assertFalse(daily_briefing.delivered_today())
            daily_briefing.STATE_FILE.write_text("broken")
            self.assertFalse(daily_briefing.delivered_today())


class DailyContactTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.folder=tempfile.TemporaryDirectory()
        self.state=patch.object(daily_briefing,'STATE_FILE',Path(self.folder.name)/'day.json')
        self.state.start()

    async def asyncTearDown(self):
        self.state.stop()
        self.folder.cleanup()

    async def test_cancelled_daily_summary_does_not_restart_on_greeting(self):
        from main import JarvisLive
        assistant=JarvisLive.__new__(JarvisLive)
        assistant.ui=Mock();assistant._manual_rest=False
        assistant._application_context=Mock(user_text='bom dia Jarvis')
        assistant._briefing_suppressed_day=datetime.now().date().isoformat()
        assistant._daily_briefing_task=None
        with patch('main.get_brief_enabled',return_value=True),patch.object(daily_briefing,'record_contact'),patch.object(daily_briefing,'delivered_today',return_value=False):
            assistant._queue_daily_briefing()
            self.assertIsNone(assistant._daily_briefing_task)

    async def test_first_contact_waits_for_response_and_deduplicates(self):
        from main import JarvisLive
        assistant=JarvisLive.__new__(JarvisLive)
        assistant.session=object();assistant.ui=Mock()
        assistant._manual_rest=False;assistant._awake=True;assistant._is_speaking=False
        assistant.audio_in_queue=asyncio.Queue();assistant._tail_active=Mock(return_value=False)
        assistant._turn_done_event=asyncio.Event();assistant._daily_briefing_task=None
        assistant._send_startup_briefing=AsyncMock()
        assistant._application_context = Mock(user_text='bom dia Jarvis')
        with patch("main.get_brief_enabled",return_value=True), patch.object(daily_briefing,'record_contact'), patch.object(daily_briefing,"delivered_today",return_value=False):
            assistant._queue_daily_briefing()
            first=assistant._daily_briefing_task
            assistant._queue_daily_briefing()
            self.assertIs(first,assistant._daily_briefing_task)
            await asyncio.sleep(0)
            assistant._send_startup_briefing.assert_not_awaited()
            assistant._turn_done_event.set()
            await first
            assistant._send_startup_briefing.assert_awaited_once()
        with patch("main.get_brief_enabled",return_value=True), patch.object(daily_briefing,'record_contact'), patch.object(daily_briefing,'refresh_due',return_value=False), patch.object(daily_briefing,"delivered_today",return_value=True):
            assistant._queue_daily_briefing()
            self.assertIs(first,assistant._daily_briefing_task)

    async def test_rest_cancels_pending_delivery(self):
        from main import JarvisLive
        assistant=JarvisLive.__new__(JarvisLive)
        assistant.session=object();assistant._manual_rest=True;assistant._awake=False
        assistant._turn_done_event=asyncio.Event();assistant._turn_done_event.set()
        assistant._send_startup_briefing=AsyncMock()
        await assistant._daily_briefing_after_contact()
        assistant._send_startup_briefing.assert_not_awaited()
