"""Startup optimizations with synthetic providers and no installation changes."""
import builtins
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock,patch

from core.startup import check_connections
from core.dependency_integrity import repair_requirements, repair
from core.distribution import Installation


class StartupUpdateSpeed(unittest.TestCase):
    def test_preflight_never_imports_optional_network_connections(self):
        progress=Mock()
        original=builtins.__import__
        def guarded(name,*args,**kwargs):
            if 'gmail' in name or 'whatsapp' in name:raise AssertionError('network import')
            return original(name,*args,**kwargs)
        with patch('builtins.__import__',side_effect=guarded):
            self.assertTrue(check_connections(progress,threading.Event(),False))
        self.assertEqual(progress.call_args.args[2],'pending')

    def test_cancelled_preflight_cannot_announce_success(self):
        stop=threading.Event();stop.set();progress=Mock()
        self.assertFalse(check_connections(progress,stop,False))
        progress.assert_not_called()

    def test_healthy_python_is_probed_only_once(self):
        with tempfile.TemporaryDirectory() as folder:
            install=Installation(folder)
            python=Path(folder)/'environment/Scripts/python.exe'
            python.parent.mkdir(parents=True);python.touch()
            with patch('core.distribution.run') as run:
                self.assertEqual(install.prepare_python(threading.Event()),python)
            run.assert_called_once()

    def test_repair_selects_only_damaged_locked_packages_preserving_hashes(self):
        with tempfile.TemporaryDirectory() as folder:
            lock=Path(folder)/'requirements.lock'
            first='--hash=sha256:'+'a'*64
            second='--hash=sha256:'+'b'*64
            lock.write_text('Fixture_A==1.0 \\\n    '+first+' \\\n    '+second+'\nother==2 '+first+'\n')
            selected=repair_requirements(lock,['fixture-a'])
            self.assertIn('Fixture_A==1.0',selected)
            self.assertIn(first,selected);self.assertIn(second,selected)
            self.assertNotIn('other',selected)
            self.assertIsNone(repair_requirements(lock,['missing']))

    def test_complex_or_unhashed_lock_uses_original_install_path(self):
        with tempfile.TemporaryDirectory() as folder:
            lock=Path(folder)/'requirements.lock'
            for text in ('fixture>=1','fixture==1 --index-url=https://example.test',
                         'fixture @ https://example.test/a.whl'):
                lock.write_text(text)
                self.assertIsNone(repair_requirements(lock,['fixture']))

    def test_current_project_lock_can_select_a_single_package(self):
        lock=Path(__file__).resolve().parents[1]/'requirements-win.lock'
        selected=repair_requirements(lock,['requests'])
        self.assertIsNotNone(selected)
        self.assertTrue(selected.startswith('requests=='))
        self.assertIn('--hash=sha256:',selected)

    def test_targeted_repair_rechecks_integrity_and_removes_temporary_lock(self):
        self._repair_flow([])

    def test_unsuccessful_repair_does_not_announce_healthy_environment(self):
        self._repair_flow(['fixture'],fails=True)

    def _repair_flow(self,after,fails=False):
        with tempfile.TemporaryDirectory() as folder:
            app=Path(folder)
            digest='--hash=sha256:'+'a'*64
            (app/'requirements-win.lock').write_text('fixture==1 '+digest+'\nother==2 '+digest+'\n')
            processes=[Mock(stdout=io.StringIO(json.dumps(value)),returncode=0)
                       for value in (['fixture'],after)]
            for process in processes:process.poll.return_value=0
            captured=[]
            def install(command,*args,**kwargs):
                selected=Path(command[command.index('-r')+1])
                captured.append(selected)
                text=selected.read_text()
                self.assertIn('fixture==1',text)
                self.assertNotIn('other==',text)
                self.assertIn(digest,text)
                self.assertIn('--require-hashes',command)
            progress=Mock()
            with patch('core.installer_process.spawn',side_effect=processes) as spawn,\
                 patch('core.installer_process.close_tree'),patch('core.distribution.run',side_effect=install):
                if fails:
                    with self.assertRaises(RuntimeError):repair('python',app,progress,threading.Event())
                else:repair('python',app,progress,threading.Event())
            self.assertEqual(spawn.call_count,2)
            self.assertEqual(len(captured),1)
            self.assertFalse(captured[0].exists())
            self.assertEqual(any(call.args[-1]=='ok' for call in progress.call_args_list),not fails)


if __name__=='__main__':unittest.main()
