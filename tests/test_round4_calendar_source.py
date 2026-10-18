"""Daily calendar source labels and delivery dates, without real accounts."""
import json
import os
from datetime import date, datetime
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from core import daily_briefing, session_refresh
from core.briefing_presentation import chapters


class CalendarSourceTests(unittest.TestCase):
    def calendar(self, google_enabled, items):
        response = {'items': items, 'complete': True, 'next_page_token': None}
        local = {'kind': 'calendar', 'source': 'Agenda local', 'items': [], 'count': 0}
        with patch('memory.config_manager.get_plugin_enabled',
                   side_effect=lambda name: google_enabled and name == 'google_calendar'), \
                patch('core.gmail_connection.status') as gmail_status, \
                patch('core.google_services.status', return_value={'connected': True}) as status, \
                patch('core.google_services.calendar', return_value=response) as fetch, \
                patch('actions.organizer.organizer_action',
                      return_value=json.dumps({'ok': True, 'data': local})) as organizer:
            source = session_refresh.default_sources(lambda: None)['calendar'][1]
            model = source()
        gmail_status.assert_not_called()
        if google_enabled:
            status.assert_called_once_with('google_calendar')
            fetch.assert_called_once_with(model['refresh']['parameters'])
            organizer.assert_not_called()
        else:
            status.assert_not_called()
            fetch.assert_not_called()
            organizer.assert_called_once()
        return model

    def test_empty_google_calendar_preserves_source_specific_display(self):
        model = self.calendar(True, [])
        chapter = chapters({'data': {'calendar': model}})[0]
        self.assertEqual(chapter['model']['source'], 'Google Agenda')
        self.assertEqual(chapter['model']['items'], [])
        self.assertEqual(chapter['model']['emptyText'],
                         'Nenhum compromisso no Google Agenda para hoje.')
        self.assertNotIn('local', chapter['model']['emptyText'])

    def test_populated_google_calendar_preserves_event_and_query(self):
        model = self.calendar(True, [{'id': 'synthetic', 'summary': 'Synthetic event',
                                     'start': {'dateTime': '2026-10-16T10:00:00-03:00'}}])
        self.assertEqual(model['items'][0]['title'], 'Synthetic event')
        self.assertEqual(model['items'][0]['due'], '2026-10-16T10:00:00-03:00')
        self.assertEqual(model['refresh']['provider'], 'google_calendar')
        self.assertTrue(model['complete'])
        self.assertIsNone(model['next_page_token'])

    def test_disabled_google_calendar_keeps_local_empty_display(self):
        model = self.calendar(False, [])
        chapter = chapters({'data': {'calendar': model}})[0]
        self.assertEqual(chapter['model']['source'], 'Agenda local')
        self.assertEqual(chapter['model']['emptyText'],
                         'Nenhum compromisso na agenda local para hoje.')


class DeliveryDayTests(unittest.TestCase):
    def test_prior_data_date_does_not_mark_current_day_delivered(self):
        today = date(2026, 10, 17)
        previous = date(2026, 10, 16)
        with tempfile.TemporaryDirectory() as folder, \
                patch.object(daily_briefing, 'STATE_FILE', Path(folder)/'day.json'), \
                patch.object(daily_briefing, 'date') as clock:
            clock.today.return_value = today
            clock.fromisoformat.side_effect = date.fromisoformat
            for supplied in (previous.isoformat(), previous):
                with self.subTest(delivery_day=supplied):
                    daily_briefing.mark_delivered(['weather'], summary=False,
                                                  delivery_day=supplied)
                    state = json.loads(daily_briefing.STATE_FILE.read_text(encoding='utf-8'))
                    self.assertEqual(state['date'], previous.isoformat())
                    self.assertEqual(state['pending_sources'], ['weather'])
                    self.assertFalse(state['complete'])
                    self.assertEqual(state['delivery_kind'], 'context')
                    self.assertFalse(daily_briefing.delivered_today())
                    self.assertTrue(daily_briefing.refresh_due(now=datetime(2026, 10, 17, 0, 1)))

    def test_omitted_delivery_day_still_marks_today(self):
        with tempfile.TemporaryDirectory() as folder, \
                patch.object(daily_briefing, 'STATE_FILE', Path(folder)/'day.json'):
            daily_briefing.mark_delivered()
            self.assertTrue(daily_briefing.delivered_today())
            state = json.loads(daily_briefing.STATE_FILE.read_text(encoding='utf-8'))
            self.assertTrue(state['complete'])
            self.assertEqual(state['delivery_kind'], 'summary')


if __name__ == '__main__':
    unittest.main()
