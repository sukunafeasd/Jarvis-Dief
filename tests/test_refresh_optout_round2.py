"""Account refresh opt-out with synthetic providers and an isolated worker pool."""
import os
import tempfile

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('DIEF_JARVIS_DATA_DIR', tempfile.mkdtemp(prefix='dief-refresh-optout-'))

import asyncio
import threading
import unittest
from unittest.mock import patch

from core import session_refresh
from core.bounded_work import BoundedWork


class RefreshOptoutTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.enabled = True
        self.calendar_enabled = False
        self.pool = BoundedWork(workers=1, capacity=2, name='SyntheticOptout')
        self.addCleanup(self.close_pool)
        patches = {
            'pool': patch.object(session_refresh, '_SOURCE_WORK', self.pool),
            'plugin_enabled': patch('memory.config_manager.get_plugin_enabled',
                                   side_effect=lambda name: self.enabled if name == 'gmail_control'
                                   else self.calendar_enabled if name == 'google_calendar' else False),
            'status': patch('core.gmail_connection.status', return_value={'connected': True}),
            'listing': patch('core.gmail_connection.list_messages', return_value={
                'ok': True, 'messages': [{'id': 'synthetic', 'subject': 'Synthetic mail'}]}),
            'counts': patch('core.gmail_connection.inbox_summary', return_value={'ok': True}),
            'calendar_status': patch('core.google_services.status', return_value={'connected': True}),
            'calendar_fetch': patch('core.google_services.calendar', return_value={
                'items': [{'id': 'synthetic', 'summary': 'Synthetic event',
                           'start': {'dateTime': '2026-10-16T10:00:00-03:00'}}],
                'complete': True, 'next_page_token': None}),
        }
        for name, context in patches.items():
            setattr(self, name, context.start())
            self.addCleanup(context.stop)

    def close_pool(self):
        self.pool.close()
        for thread in self.pool.threads:
            thread.join(timeout=2)
            self.assertFalse(thread.is_alive())

    def sources(self):
        sources = session_refresh.default_sources(lambda: None)
        return {'gmail': sources['gmail']}

    async def collect(self, sources):
        return await session_refresh.collect_updates(None, lambda model: None,
                                                     sources=sources, timeout=2)

    def test_disabled_inventory_never_reads_account_status(self):
        self.enabled = False
        sources = session_refresh.default_sources(lambda: None)
        self.assertNotIn('gmail', sources)
        self.status.assert_not_called()
        self.listing.assert_not_called()
        self.counts.assert_not_called()

    async def test_enabled_gmail_preserves_synthetic_headers(self):
        result = await self.collect(self.sources())
        self.assertEqual(result['unavailable'], [])
        self.assertEqual(result['data']['gmail']['items'][0]['title'], 'Synthetic mail')
        self.listing.assert_called_once_with('is:unread is:important', limit=5)
        self.counts.assert_called_once_with()

    async def test_disabled_while_queued_never_calls_account_apis(self):
        sources = self.sources()
        release = threading.Event()
        entered = threading.Event()
        submitted = asyncio.Event()

        def blocked():
            entered.set()
            release.wait(timeout=3)

        blocker = self.pool.submit(blocked)
        task = None
        try:
            self.assertTrue(entered.wait(timeout=1))
            submit = self.pool.submit

            def enqueue(callback):
                future = submit(callback)
                submitted.set()
                return future

            with patch.object(self.pool, 'submit', side_effect=enqueue):
                task = asyncio.create_task(self.collect(sources))
                await asyncio.wait_for(submitted.wait(), timeout=1)
                self.assertEqual(self.pool.queue.qsize(), 1)
                self.enabled = False
                release.set()
                result = await task
            self.assertEqual(result['data'], {})
            self.assertEqual(result['unavailable'], ['gmail'])
            self.listing.assert_not_called()
            self.counts.assert_not_called()
        finally:
            release.set()
            await asyncio.wrap_future(blocker)
            if task is not None:
                await asyncio.gather(task, return_exceptions=True)

    async def test_disabled_during_listing_skips_counts_and_discards_headers(self):
        def listing(*args, **kwargs):
            self.enabled = False
            return {'ok': True, 'messages': [{'id': 'synthetic', 'subject': 'Do not publish'}]}

        self.listing.side_effect = listing
        result = await self.collect(self.sources())
        self.assertEqual(result['data'], {})
        self.assertEqual(result['unavailable'], ['gmail'])
        self.listing.assert_called_once()
        self.counts.assert_not_called()

    async def test_disabled_during_counts_discards_account_data(self):
        def counts():
            self.enabled = False
            return {'ok': True, 'unread': 3}

        self.counts.side_effect = counts
        result = await self.collect(self.sources())
        self.assertEqual(result['data'], {})
        self.assertEqual(result['unavailable'], ['gmail'])
        self.listing.assert_called_once()
        self.counts.assert_called_once()

    def calendar_sources(self):
        sources = session_refresh.default_sources(lambda: None)
        return {'calendar': sources['calendar']}

    def test_disabled_calendar_inventory_keeps_local_source_without_account_status(self):
        self.enabled = False
        sources = session_refresh.default_sources(lambda: None)
        self.assertEqual(sources['calendar'][0], 'Agenda local')
        self.calendar_status.assert_not_called()
        self.calendar_fetch.assert_not_called()

    async def test_enabled_calendar_preserves_event_and_refresh_query(self):
        self.calendar_enabled = True
        result = await self.collect(self.calendar_sources())
        self.assertEqual(result['unavailable'], [])
        model = result['data']['calendar']
        self.assertEqual(model['source'], 'Google Agenda')
        self.assertEqual(model['items'][0]['title'], 'Synthetic event')
        self.assertEqual(model['items'][0]['due'], '2026-10-16T10:00:00-03:00')
        self.assertEqual(model['refresh']['parameters'], self.calendar_fetch.call_args.args[0])
        self.calendar_fetch.assert_called_once()

    async def test_calendar_disabled_while_queued_never_calls_account_api(self):
        self.calendar_enabled = True
        sources = self.calendar_sources()
        release = threading.Event()
        entered = threading.Event()
        submitted = asyncio.Event()

        def blocked():
            entered.set()
            release.wait(timeout=3)

        blocker = self.pool.submit(blocked)
        task = None
        try:
            self.assertTrue(entered.wait(timeout=1))
            submit = self.pool.submit

            def enqueue(callback):
                future = submit(callback)
                submitted.set()
                return future

            with patch.object(self.pool, 'submit', side_effect=enqueue):
                task = asyncio.create_task(self.collect(sources))
                await asyncio.wait_for(submitted.wait(), timeout=1)
                self.assertEqual(self.pool.queue.qsize(), 1)
                self.calendar_enabled = False
                release.set()
                result = await task
            self.assertEqual(result['data'], {})
            self.assertEqual(result['unavailable'], ['calendar'])
            self.calendar_fetch.assert_not_called()
        finally:
            release.set()
            await asyncio.wrap_future(blocker)
            if task is not None:
                await asyncio.gather(task, return_exceptions=True)

    async def test_calendar_disabled_during_fetch_discards_events(self):
        self.calendar_enabled = True
        response = self.calendar_fetch.return_value

        def fetch(parameters):
            self.calendar_enabled = False
            return response

        self.calendar_fetch.side_effect = fetch
        result = await self.collect(self.calendar_sources())
        self.assertEqual(result['data'], {})
        self.assertEqual(result['unavailable'], ['calendar'])
        self.calendar_fetch.assert_called_once()


if __name__ == '__main__':
    unittest.main()
