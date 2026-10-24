import threading
import base64
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import desktop_launcher
from core.update_status import release_status
from core.update_watch import UpdateWatch


class UpdateConsentTests(unittest.TestCase):
    def test_restart_waits_for_launcher_and_uses_exact_version(self):
        from core.launcher_update import schedule_restart
        with patch('core.launcher_update.subprocess.Popen') as launch, patch('core.launcher_update.subprocess.CREATE_NO_WINDOW',0,create=True):
            schedule_restart(Path('C:/Jarvis'),'2.0.13')
        script=base64.b64decode(launch.call_args.args[0][-1]).decode('utf-16le')
        self.assertIn('Wait-Process',script)
        self.assertIn('--update-version 2.0.13',script)
        self.assertIn('PYINSTALLER_RESET_ENVIRONMENT="1"',script)
        self.assertIn('--root',script)
        self.assertLess(script.index('Wait-Process'),script.index('Start-Process'))
        with self.assertRaises(ValueError):schedule_restart(Path('C:/Jarvis'),'2.0.13; arbitrary')

    def test_watch_deduplicates_and_does_not_overlap_checks(self):
        watch=UpdateWatch('2.0.12')
        watch.busy=True;watch.next_check=200
        watch.fetch=Mock()
        self.assertIsNone(watch.tick(now=100))
        watch.fetch.assert_not_called()
        watch.results.put({'version':'2.0.13'})
        self.assertEqual(watch.tick(now=100)['version'],'2.0.13')
        watch.results.put({'version':'2.0.13'})
        self.assertIsNone(watch.tick(now=100))

    def test_watch_ignores_failed_checks_and_older_releases(self):
        watch=UpdateWatch('2.0.12');watch.next_check=200
        for release in (None,{'version':'2.0.0'},{'version':'2.0.12'}):
            watch.results.put(release)
            self.assertIsNone(watch.tick(now=100))

    def test_comparison(self):
        for state, latest, expected in [
            ({}, '2.0.13', 'first_install'),
            ({'current':'2.0.12'}, '2.0.12', 'current'),
            ({'current':'2.0.12'}, '2.0.0', 'current'),
            ({'current':'2.0.12'}, '2.0.13', 'available'),
            ({'current':'2.0.12','rejected':'2.0.13'}, '2.0.13', 'rejected'),
        ]:
            with self.subTest(state=state, latest=latest):
                self.assertEqual(release_status(state, {'version':latest})[0], expected)

    def run_prepare(self, accept=True, failure=False, offline=False):
        install=Mock()
        install.state.return_value={'current':'2.0.12'}
        install.application.return_value=Path('old-app')
        install.prepare_python.return_value=Path('python')
        install.install.return_value=Path('new-app')
        if failure:install.install.side_effect=OSError('download failed')
        fetch=Mock(return_value={'version':'2.0.13'})
        if offline:fetch.side_effect=TimeoutError()
        consent=Mock(return_value=accept)
        progress=Mock()
        with patch.object(desktop_launcher,'Installation',return_value=install), \
             patch.object(desktop_launcher,'prepare_dependencies'), \
             patch.object(desktop_launcher,'run_probe'), \
             patch.object(desktop_launcher,'install_launcher'):
            result=desktop_launcher.prepare(Path('root'),progress,threading.Event(),fetch=fetch,approve_update=consent)
        return install,consent,progress,result

    def test_decline_keeps_current_without_download(self):
        install,consent,progress,result=self.run_prepare(accept=False)
        consent.assert_called_once()
        install.install.assert_not_called()
        self.assertEqual(result[2],Path('old-app'))

    def test_accept_installs(self):
        install,consent,progress,result=self.run_prepare()
        install.install.assert_called_once()
        self.assertEqual(result[2],Path('new-app'))

    def test_download_failure_is_not_overwritten_by_success(self):
        install,consent,progress,result=self.run_prepare(failure=True)
        self.assertEqual(progress.call_args.args[2],'warning')
        self.assertEqual(result[2],Path('old-app'))

    def test_offline_does_not_claim_latest_installed(self):
        install,consent,progress,result=self.run_prepare(offline=True)
        consent.assert_not_called()
        install.install.assert_not_called()
        self.assertEqual(progress.call_args.args[2],'warning')


if __name__=='__main__':unittest.main()
