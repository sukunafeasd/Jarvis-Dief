import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

from core.whatsapp_web import WhatsAppWeb


class WhatsAppLifecycleTests(unittest.IsolatedAsyncioTestCase):
    def session(self):
        session = WhatsAppWeb()
        session.lock = asyncio.Lock()
        session.pw = Mock()
        context = Mock()
        page = Mock()
        page.goto = AsyncMock()
        page.bring_to_front = AsyncMock()
        page.is_closed.return_value = False
        context.pages = [page]
        context.close = AsyncMock()
        session.pw.chromium.launch_persistent_context = AsyncMock(return_value=context)
        return session, context, page

    async def test_saved_profile_reopens_hidden_and_waits_for_account(self):
        session, context, page = self.session()
        session._connected = AsyncMock(return_value=True)
        with tempfile.TemporaryDirectory() as folder, patch('core.whatsapp_web.PROFILE', Path(folder)):
            result = await session._execute('status', '', '')
            launch = session.pw.chromium.launch_persistent_context.call_args
            self.assertEqual(launch.args[0], folder)
            self.assertTrue(launch.kwargs['headless'])
            self.assertTrue(result['connected'])
            self.assertTrue(result['background'])
            session._connected.assert_awaited_once_with(wait=True)
            page.bring_to_front.assert_not_called()

    async def test_close_event_discards_stale_context(self):
        session, context, _ = self.session()
        await session._ensure_session(False)
        handler = context.on.call_args.args[1]
        handler()
        self.assertIsNone(session.context)
        self.assertIsNone(session.page)
        self.assertIsNone(session.background)

    async def test_old_close_event_does_not_clear_replacement(self):
        session, old_context, _ = self.session()
        session.context = Mock()
        replacement = session.context
        session._context_closed(old_context)
        self.assertIs(session.context, replacement)

    async def test_connect_replaces_hidden_session_with_visible_same_profile(self):
        session, context, page = self.session()
        session.context = Mock()
        old_context = session.context
        old_context.close = AsyncMock()
        session.page = page
        session.background = True
        result = await session._execute('connect', '', '')
        self.assertTrue(result['ok'])
        old_context.close.assert_awaited_once()
        self.assertFalse(session.pw.chromium.launch_persistent_context.call_args.kwargs['headless'])
        page.bring_to_front.assert_awaited_once()

    async def test_unconfirmed_account_never_sends_or_claims_connected(self):
        session, _, _ = self.session()
        session._connected = AsyncMock(return_value=False)
        with tempfile.TemporaryDirectory() as folder, patch('core.whatsapp_web.PROFILE', Path(folder)), patch('core.whatsapp_web.send_on_page', new_callable=AsyncMock) as send:
            result = await session._execute('send', 'Contato', 'Mensagem')
            self.assertFalse(result['ok'])
            self.assertFalse(result['connected'])
            send.assert_not_awaited()

    async def test_closed_page_releases_old_profile_before_reopening(self):
        session, _, _ = self.session()
        old_context = Mock()
        old_context.close = AsyncMock()
        session.context = old_context
        session.page = Mock()
        session.page.is_closed.return_value = True
        self.assertTrue(await session._ensure_session(True))
        old_context.close.assert_awaited_once()
        self.assertTrue(session.background)

    async def test_linked_visible_session_moves_to_background_without_new_login(self):
        session, context, page = self.session()
        old_context=Mock();old_context.close=AsyncMock()
        session.context=old_context;session.page=page;session.background=False
        session._connected=AsyncMock(return_value=True)
        await session._ensure_session(True)
        old_context.close.assert_awaited_once()
        self.assertTrue(session.pw.chromium.launch_persistent_context.call_args.kwargs['headless'])
        page.bring_to_front.assert_not_called()
