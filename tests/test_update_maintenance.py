"""Isolated updater checks; never touch the user's installation or packages."""
import json
import os
from pathlib import Path
import tempfile
import threading
import subprocess
import sys
import unittest
from unittest.mock import Mock, patch

from core.distribution import Installation, atomic_json, prepare_dependencies
from core.dependency_integrity import environment_state, check_environment_state


class UpdateMaintenance(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)

    def test_confirm_prunes_only_managed_obsolete_versions(self):
        install=Installation(self.root)
        for version in ('1.0.0','2.0.0','2.0.7','notes'):
            path=self.root/'versions'/version
            path.mkdir(parents=True)
            (path/'fixture').write_text('fixture')
        personal=self.root/'data'/'memory.json'
        personal.parent.mkdir();personal.write_text('personal')
        atomic_json(install.state_file,{'current':'2.0.7','previous':'2.0.0','pending':True})
        self.assertEqual(install.prune(),[])
        install.confirm()
        self.assertFalse((self.root/'versions/1.0.0').exists())
        for name in ('2.0.0','2.0.7','notes'):self.assertTrue((self.root/'versions'/name).exists())
        self.assertEqual(personal.read_text(),'personal')

    def test_cleanup_preserves_runtime_rollback_and_active_transaction(self):
        install=Installation(self.root)
        backup='runtime-backup-'+'a'*32
        stale='runtime-backup-'+'b'*32
        for name in (backup,stale): (self.root/name).mkdir()
        atomic_json(install.state_file,{'current':'2.0.7','previous':'2.0.0',
            'runtime_changed':True,'runtime_backup':backup,'pending':False})
        install.journal.write_text('{}')
        self.assertEqual(install.prune(),[])
        install.journal.unlink()
        self.assertEqual(install.prune(),[stale])
        self.assertTrue((self.root/backup).exists())

    def test_busy_files_do_not_break_successful_confirmation(self):
        install=Installation(self.root)
        atomic_json(install.state_file,{'current':'2.0.7','pending':True})
        with patch.object(install,'prune',side_effect=PermissionError('busy')):
            install.confirm()
        self.assertFalse(install.state()['pending'])

    @unittest.skipUnless(os.name=='nt','Windows junction behavior')
    def test_version_junction_is_not_followed_and_shared_data_survives(self):
        import _winapi
        install=Installation(self.root)
        versions=self.root/'versions';versions.mkdir()
        data=self.root/'data';data.mkdir();(data/'personal').write_text('keep')
        old=versions/'1.0.0';old.mkdir()
        _winapi.CreateJunction(str(data),str(old/'config'))
        _winapi.CreateJunction(str(data),str(versions/'1.1.0'))
        atomic_json(install.state_file,{'current':'2.0.7','previous':'2.0.0','pending':False})
        install.prune()
        self.assertFalse(old.exists())
        self.assertTrue((versions/'1.1.0').is_junction())
        self.assertEqual((data/'personal').read_text(),'keep')

    def test_state_changes_when_requirements_or_installed_versions_change(self):
        requirements=self.root/'requirements.txt';requirements.write_text('fixture==1')
        stamp=self.root/'state.json'
        distribution=Mock(metadata={'Name':'Fixture'},version='1')
        with patch('core.dependency_integrity.importlib.metadata.distributions',return_value=[distribution]):
            self.assertFalse(check_environment_state(requirements,stamp))
            stamp.write_text(json.dumps(environment_state(requirements)))
            self.assertTrue(check_environment_state(requirements,stamp))
            distribution.version='2'
            self.assertFalse(check_environment_state(requirements,stamp))
            distribution.version='1';requirements.write_text('fixture==3')
            self.assertFalse(check_environment_state(requirements,stamp))
            stamp.write_text('invalid')
            self.assertFalse(check_environment_state(requirements,stamp))

    def test_warm_start_skips_pip_but_keeps_integrity_and_browser_check(self):
        self._prepare(False)

    def test_changed_environment_installs_before_integrity(self):
        self._prepare(True)

    def _prepare(self,changed):
        app=self.root/'app';app.mkdir()
        (app/'requirements-win.lock').write_text('fixture')
        commands=[]
        def run(command,*args,**kwargs):
            commands.append(command)
            if changed and '--check-state' in command:raise RuntimeError('changed')
        with patch('core.distribution.run',side_effect=run),patch('core.dependency_integrity.repair') as repair:
            prepare_dependencies(self.root/'environment/Scripts/python.exe',app,Mock(),threading.Event())
        installs=[c for c in commands if 'pip' in c]
        self.assertEqual(len(installs),int(changed))
        if changed:self.assertIn('--require-hashes',installs[0])
        repair.assert_called_once()
        self.assertTrue(any('sync_playwright' in ' '.join(c) for c in commands))
        self.assertIn('--record-state',commands[-1])

    def test_failure_does_not_record_success_stamp(self):
        app=self.root/'app';app.mkdir();(app/'requirements.txt').touch()
        with patch('core.distribution.run') as run,patch('core.dependency_integrity.repair',side_effect=RuntimeError('damaged')):
            with self.assertRaises(RuntimeError):
                prepare_dependencies(self.root/'environment/Scripts/python.exe',app,Mock(),threading.Event())
        self.assertFalse(any('--record-state' in c.args[0] for c in run.call_args_list))

    def test_cancel_does_not_fall_through_to_install(self):
        app=self.root/'app';app.mkdir();(app/'requirements.txt').touch()
        with patch('core.distribution.run',side_effect=InterruptedError('cancel')) as run:
            with self.assertRaises(InterruptedError):
                prepare_dependencies(self.root/'environment/Scripts/python.exe',app,Mock(),threading.Event())
        self.assertEqual(run.call_count,1)

    def test_legacy_dependency_cli_still_prepares_for_rollback(self):
        app=self.root/'legacy';(app/'core').mkdir(parents=True)
        helper=app/'core/dependency_integrity.py'
        helper.write_text("import argparse\np=argparse.ArgumentParser()\np.add_argument('--inspect',action='store_true')\np.parse_args()\nprint('[]')\n")
        (app/'requirements.txt').touch()
        commands=[]
        def run(command,*args,**kwargs):
            commands.append(command)
            if str(helper) in command:
                completed=subprocess.run(command,capture_output=True)
                if completed.returncode:raise RuntimeError('legacy parser')
        with patch('core.distribution.run',side_effect=run),patch('core.dependency_integrity.repair') as repair:
            prepare_dependencies(Path(sys.executable),app,Mock(),threading.Event())
        self.assertEqual(sum('pip' in c for c in commands),1)
        self.assertFalse(any('--record-state' in c or '--check-state' in c for c in commands))
        repair.assert_called_once()


if __name__=='__main__':unittest.main()
