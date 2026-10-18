import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch
from core import daily_briefing
from core.briefing_presentation import explicit_refresh


class DailyRefreshContract(unittest.IsolatedAsyncioTestCase):
    def owner(self, text='bom dia'):
        from main import JarvisLive
        owner = JarvisLive.__new__(JarvisLive)
        owner.ui = Mock()
        owner.session = object()
        owner._application_context = Mock(user_text=text)
        owner._manual_rest = False
        owner._awake = True
        owner._daily_briefing_task = None
        owner._turn_done_event = None
        owner._response_busy = Mock(return_value=False)
        owner._send_startup_briefing = AsyncMock()
        return owner

    async def test_automatic_attempt_persists_and_explicit_retry_remains_available(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(daily_briefing, 'STATE_FILE', Path(folder)/'daily.json'), patch('main.get_brief_enabled', return_value=True):
            first = self.owner()
            self.assertTrue(first._queue_daily_briefing(wait_for_turn=False))
            await first._daily_briefing_task
            self.assertTrue(daily_briefing.automatic_attempted_today())
            second = self.owner()
            self.assertFalse(second._queue_daily_briefing(wait_for_turn=False))
            second._application_context.user_text = 'Jarvis se atualiza do dia'
            self.assertTrue(second._queue_daily_briefing(wait_for_turn=False))
            await second._daily_briefing_task
            second._send_startup_briefing.assert_awaited_once()

    async def test_new_request_cancels_waiting_refresh(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(daily_briefing, 'STATE_FILE', Path(folder)/'daily.json'), patch('main.get_brief_enabled', return_value=True):
            owner = self.owner()
            owner._queue_daily_briefing(wait_for_turn=False)
            owner._application_context.user_text = 'abrir aplicativo'
            await owner._daily_briefing_task
            owner._send_startup_briefing.assert_not_awaited()

    async def test_session_replacement_cannot_replay_old_request(self):
        owner = self.owner()
        owner._refresh_intent = {'text':'bom dia', 'session':object(), 'manual':True}
        await owner._daily_briefing_after_contact(False)
        owner._send_startup_briefing.assert_not_awaited()

    async def test_negative_request_is_not_refresh(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(daily_briefing,'STATE_FILE',Path(folder)/'day.json'):
            for text in ('Jarvis não se atualize agora','não me atualize','não atualize o contexto','sem resumo hoje'):
                owner = self.owner(text)
                self.assertFalse(explicit_refresh(text),text)
                self.assertFalse(owner._queue_daily_briefing(False,False),text)
            owner._application_context.user_text='boa tarde'
            self.assertFalse(owner._queue_daily_briefing(False,False))
            self.assertTrue(explicit_refresh('briefing do dia'))

    async def test_session_changed_during_wait_cannot_start_refresh(self):
        owner=self.owner()
        owner._refresh_intent={'text':'bom dia','session':owner.session,'manual':True}
        async def reconnect(_):owner.session=object()
        with patch('main.asyncio.sleep',side_effect=reconnect):
            await owner._daily_briefing_after_contact(False)
        owner._send_startup_briefing.assert_not_awaited()


class DailyRefreshViewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtGui import QFontDatabase
        cls.app = QApplication.instance() or QApplication([])
        font = Path(os.environ.get('WINDIR', 'C:/Windows'))/'Fonts/segoeui.ttf'
        if font.exists():QFontDatabase.addApplicationFont(str(font))

    def test_progress_bounds_stale_completion_and_no_buttons(self):
        from PyQt6.QtWidgets import QWidget, QPushButton
        from core.daily_refresh_view import DailyRefreshView
        stage = QWidget()
        stage.setStyleSheet('background: #040b12;')
        stage.resize(1280, 720)
        stage.show()
        view = DailyRefreshView(stage)
        view.update_model({'id':'new', 'total':3, 'completed':1, 'items':[{'title':'Agenda', 'status':'working'}]})
        self.assertEqual(view.bar.value(), 1)
        self.assertEqual(view.bar.maximum(), 3)
        self.assertIn('Agenda', view.detail.text())
        self.assertFalse(view.findChildren(QPushButton))
        view.finish('old')
        self.assertTrue(view.isVisible())
        for width, height in ((1920,1080), (800,600), (390,640)):
            stage.resize(width,height)
            view.reposition()
            self.assertTrue(stage.rect().contains(view.geometry()))
        stage.resize(1280,720)
        view.reposition()
        output = Path(__file__).resolve().parents[1]/'validation/daily-refresh-compact.png'
        output.parent.mkdir(exist_ok=True)
        stage.grab().save(str(output))
        view.finish('new')
        self.assertFalse(view.isVisible())
        stage.close()
