import json
import tempfile
import unittest
from datetime import datetime,timedelta
from pathlib import Path
from unittest.mock import patch

from core import daily_briefing, session_refresh


class PartialSourceTests(unittest.IsolatedAsyncioTestCase):
    async def test_gmail_headers_survive_unavailable_total_counts(self):
        with patch('core.gmail_connection.status',return_value={'connected':True}), patch('memory.config_manager.get_plugin_enabled',side_effect=lambda name:name=='gmail_control'), patch('core.gmail_connection.list_messages',return_value={
            'ok':True,'messages':[{'id':'sample','subject':'Assunto sintético','from':'Equipe'}]}), patch('core.gmail_connection.inbox_summary',return_value={'ok':False,'error':'synthetic'}):
            sources=session_refresh.default_sources(lambda:None)
            result=await session_refresh.collect_updates(None,lambda value:None,sources={'gmail':sources['gmail']})
        self.assertEqual(result['unavailable'],[])
        self.assertTrue(result['data']['gmail']['counts_unavailable'])
        self.assertEqual(result['data']['gmail']['items'][0]['title'],'Assunto sintético')

    def test_partial_delivery_remembers_missing_sources_without_repeating_immediately(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(daily_briefing,'STATE_FILE',Path(folder)/'day.json'):
            daily_briefing.mark_delivered(['weather'])
            data=json.loads(daily_briefing.STATE_FILE.read_text())
            self.assertFalse(data['complete'])
            self.assertEqual(data['pending_sources'],['weather'])
            self.assertTrue(daily_briefing.delivered_today())
            self.assertFalse(daily_briefing.refresh_due('bom dia'))
            self.assertTrue(daily_briefing.refresh_due('se atualize'))
            now=datetime.now()
            data.update(updated_at=(now-timedelta(minutes=16)).isoformat(),last_contact=now.isoformat())
            daily_briefing.STATE_FILE.write_text(json.dumps(data))
            self.assertFalse(daily_briefing.refresh_due('bom dia',now))
            daily_briefing.mark_delivered()
            self.assertTrue(json.loads(daily_briefing.STATE_FILE.read_text())['complete'])

    def test_context_update_is_distinct_from_spoken_summary(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(daily_briefing,'STATE_FILE',Path(folder)/'day.json'):
            daily_briefing.mark_delivered([],summary=False)
            self.assertEqual(json.loads(daily_briefing.STATE_FILE.read_text())['delivery_kind'],'context')
