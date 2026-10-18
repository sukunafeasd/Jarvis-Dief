import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

from core.session_refresh import collect_updates
from core import startup


class StartupTests(unittest.TestCase):
    def test_dependency_install_is_refused_outside_private_environment(self):
        progress = Mock()
        with patch.object(startup,'missing_dependencies',return_value=['missing-test-package']), patch.object(startup.sys,'prefix','same'), patch.object(startup.sys,'base_prefix','same'), patch.object(startup.subprocess,'Popen') as launch:
            self.assertFalse(startup.check_startup(progress,Mock(),install=True))
            launch.assert_not_called()

    def test_undeclared_url_requirement_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(startup,'BASE',Path(folder)):
            (Path(folder)/'requirements.txt').write_text('example @ https://example.com/arbitrary.whl')
            with self.assertRaises(ValueError):
                startup.missing_dependencies()

    def test_only_absent_declared_distributions_are_requested(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(startup,'BASE',Path(folder)), patch.object(startup.importlib.metadata,'version',side_effect=[ '1.0', startup.importlib.metadata.PackageNotFoundError()]):
            (Path(folder)/'requirements.txt').write_text('present>=1\nabsent>=2\n# ignored')
            self.assertEqual(startup.missing_dependencies(),['absent>=2'])


class RefreshTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_completion_and_failure_are_reported_independently(self):
        progress = Mock()
        def failure():
            raise OSError('provider failed')
        package = await collect_updates(None,progress,sources={'tasks':('Tarefas',lambda:{'items':[],'count':0}),'calendar':('Agenda',failure)})
        self.assertIn('tasks',package['data'])
        self.assertEqual(package['unavailable'],['calendar'])
        final = progress.call_args.args[0]
        self.assertEqual(final['completed'],2)
        self.assertEqual([item['status'] for item in final['items']],['ok','warning'])
        self.assertFalse(final['narrationDriven'])

    async def test_missing_news_is_not_announced_as_updated(self):
        package = await collect_updates(None,Mock(),sources={'news':('Notícias',lambda:{'text':'No news found','model':{'items':[]}})})
        self.assertNotIn('news',package['data'])
        self.assertEqual(package['unavailable'],['news'])

    async def test_briefing_waits_for_collection_and_does_not_mark_early(self):
        from main import JarvisLive
        assistant = JarvisLive.__new__(JarvisLive)
        assistant.session=Mock(); assistant._manual_rest=False; assistant._awake=True
        assistant._is_speaking=False; assistant.audio_in_queue=asyncio.Queue()
        assistant._tail_active=Mock(return_value=False);assistant._turn_done_event=asyncio.Event()
        assistant.ui=Mock()
        async def audio_done(**kwargs):
            assistant._played_audio_seconds=getattr(assistant,'_played_audio_seconds',0)+1
            assistant._turn_done_event.set()
        assistant.session.send_client_content=AsyncMock(side_effect=audio_done)
        release = asyncio.Event()
        async def collect(*args):
            await release.wait()
            return {'data':{'tasks':{'count':2}},'unavailable':['news']}
        with patch('core.fish_audio.selected',return_value=False),patch('core.session_refresh.collect_updates',side_effect=collect), patch('core.daily_briefing.mark_delivered') as mark:
            task=asyncio.create_task(assistant._send_startup_briefing())
            await asyncio.sleep(.05)
            mark.assert_not_called()
            self.assertEqual(assistant.session.send_client_content.await_count,1)
            release.set();await task
            self.assertEqual(assistant.session.send_client_content.await_count,4)
            mark.assert_called_once()

    async def test_cancelled_collection_never_marks_delivery(self):
        from main import JarvisLive
        assistant = JarvisLive.__new__(JarvisLive)
        assistant.session=Mock();assistant.session.send_client_content=AsyncMock()
        assistant._manual_rest=False;assistant._awake=True
        assistant._is_speaking=False;assistant.audio_in_queue=asyncio.Queue()
        assistant._tail_active=Mock(return_value=False);assistant._turn_done_event=asyncio.Event();assistant.ui=Mock()
        async def wait(*args):
            await asyncio.Event().wait()
        with patch('core.fish_audio.selected',return_value=False),patch('core.session_refresh.collect_updates',side_effect=wait),patch('core.daily_briefing.mark_delivered') as mark:
            task=asyncio.create_task(assistant._send_startup_briefing());await asyncio.sleep(.02)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
            mark.assert_not_called()
            final=assistant.ui.show_manifestation.call_args.args[0]
            first=assistant.ui.show_manifestation.call_args_list[0].args[0]
            self.assertEqual(final,{'kind':'status-end','id':first['id']})
