import asyncio
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

from core import session_refresh
from core.ultron import ultron_service as service


class CalendarDayTests(unittest.TestCase):
    def test_daily_calendar_uses_local_day_and_preserves_refresh_bounds(self):
        current = datetime(2026, 10, 15, 18, 30, tzinfo=timezone(timedelta(hours=-3)))
        with patch('core.gmail_connection.status', return_value={'connected': False}), \
                patch('memory.config_manager.get_plugin_enabled', return_value=True), \
                patch('core.google_services.status', return_value={'connected': True}), \
                patch('core.google_services.calendar', return_value={
                    'items': [], 'complete': True, 'next_page_token': None}) as fetch, \
                patch.object(session_refresh, 'datetime') as clock:
            clock.now.return_value = current
            source = session_refresh.default_sources(lambda: None)['calendar'][1]
            result = source()
        parameters = fetch.call_args.args[0]
        self.assertEqual(parameters['date_from'], datetime(2026, 10, 15).astimezone().isoformat())
        self.assertEqual(parameters['date_to'], datetime(2026, 10, 16).astimezone().isoformat())
        self.assertEqual(result['refresh']['parameters'], parameters)

    def test_calendar_callback_recalculates_day_across_year_boundary(self):
        with patch('core.gmail_connection.status', return_value={'connected': False}), \
                patch('memory.config_manager.get_plugin_enabled', return_value=True), \
                patch('core.google_services.status', return_value={'connected': True}), \
                patch('core.google_services.calendar', return_value={
                    'items': [], 'complete': True, 'next_page_token': None}) as fetch, \
                patch.object(session_refresh, 'datetime') as clock:
            clock.now.side_effect = [datetime(2026, 12, 31, 23, 59), datetime(2027, 1, 1, 0, 1)]
            source = session_refresh.default_sources(lambda: None)['calendar'][1]
            source()
            source()
        first, second = [call.args[0] for call in fetch.call_args_list]
        self.assertEqual(first['date_to'], second['date_from'])
        self.assertEqual(second['date_to'], datetime(2027, 1, 2).astimezone().isoformat())


class MonitorRecoveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_invalid_sample_processing_also_disables_monitor(self):
        with patch.object(service, 'STATE', service.initial_state()), \
                patch.object(service, 'MONITOR_TASK', None), \
                patch.object(service, 'telemetry', return_value={'cpu_percent': 1}), \
                patch.object(service, 'monitor_events', side_effect=ValueError('private detail')):
            await service.monitor(service.Monitor(enabled=True))
            await service.MONITOR_TASK
            self.assertFalse(service.STATE['monitor']['enabled'])
            self.assertEqual(service.STATE['monitor']['error'], 'ValueError')

    async def test_failed_monitor_reports_failure_and_can_restart(self):
        with patch.object(service, 'STATE', service.initial_state()), \
                patch.object(service, 'MONITOR_TASK', None), \
                patch.object(service, 'telemetry', side_effect=RuntimeError('private detail')):
            await service.monitor(service.Monitor(enabled=True))
            await service.MONITOR_TASK
            self.assertFalse(service.STATE['monitor']['enabled'])
            self.assertEqual(service.STATE['monitor']['error'], 'RuntimeError')
            with patch.object(service, 'telemetry', return_value={'cpu_percent': 1}):
                await service.monitor(service.Monitor(enabled=True))
                try:
                    self.assertTrue(service.STATE['monitor']['enabled'])
                    self.assertNotIn('error', service.STATE['monitor'])
                    self.assertFalse(service.MONITOR_TASK.done())
                finally:
                    await service.monitor(service.Monitor(enabled=False))
            self.assertFalse(service.STATE['monitor']['enabled'])

    async def test_cancelling_monitor_does_not_report_failure(self):
        with patch.object(service, 'STATE', service.initial_state()), \
                patch.object(service, 'MONITOR_TASK', None), \
                patch.object(service, 'telemetry', return_value={'cpu_percent': 1}):
            await service.monitor(service.Monitor(enabled=True))
            await asyncio.sleep(.02)
            await service.monitor(service.Monitor(enabled=False))
            self.assertFalse(service.STATE['monitor']['enabled'])
            self.assertNotIn('error', service.STATE['monitor'])
