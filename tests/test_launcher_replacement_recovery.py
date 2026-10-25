import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch,Mock

from core.distribution import Installation,atomic_json
from core.launcher_update import replacement_body


class LauncherRepairTests(unittest.TestCase):
    def test_external_new_executable_does_not_discard_installed_replacement(self):
        from core.launcher_update import schedule
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);install=Installation(root)
            (root/'DIEF JARVIS.exe').write_bytes(b'old')
            external=root/'external.exe';external.write_bytes(b'new')
            pending=root/('launcher-next-'+'a'*32+'.exe');pending.write_bytes(b'new')
            atomic_json(install.state_file,{'pending_launcher':{'name':pending.name,'sha256':hashlib.sha256(b'new').hexdigest()}})
            with patch('sys.frozen',True,create=True),patch('sys.executable',str(external)),patch('core.launcher_update.subprocess.Popen') as launch:
                self.assertTrue(schedule(install,'2.1.1'))
                launch.assert_called_once()
                script=base64.b64decode(launch.call_args.args[0][-1]).decode('utf-16le')
                self.assertIn('elseif($restored)',script)
                self.assertNotIn('--update-version',script.split('elseif($restored)',1)[1])
            self.assertTrue(pending.exists())
            self.assertIsNotNone(install.state()['pending_launcher'])

    def test_probe_requires_working_tk_and_surface_before_success_marker(self):
        from core.launcher_probe import run
        for failure in ('window','surface'):
            with self.subTest(failure=failure),tempfile.TemporaryDirectory() as folder:
                root=Path(folder);window=Mock()
                with patch('tkinter.Tk',side_effect=RuntimeError('broken Tk') if failure=='window' else None,return_value=window),patch('core.fui_bootstrap.BootstrapSurface',side_effect=RuntimeError('broken surface')):
                    with self.assertRaises(RuntimeError):run(root,'a'*32)
                self.assertFalse((root/'sessions'/('launcher-'+'a'*32+'.ready')).exists())
                if failure=='surface':window.destroy.assert_called_once()

    def test_current_application_opens_after_launcher_repair_failure(self):
        import desktop_launcher
        install=Mock();install.state.return_value={'current':'2.1.1'}
        install.application.return_value=Path('healthy-app')
        install.prepare_python.return_value=Path('python')
        install.ensure_launcher.side_effect=TimeoutError()
        progress=Mock()
        with patch.object(desktop_launcher,'Installation',return_value=install),patch.object(desktop_launcher,'prepare_dependencies'),patch.object(desktop_launcher,'run_probe'),patch.object(desktop_launcher,'install_launcher'),patch('core.update_diagnostics.record_failure') as log:
            result=desktop_launcher.prepare(Path('root'),progress,threading.Event(),fetch=lambda:{'version':'2.1.1'})
        self.assertEqual(result[2],Path('healthy-app'))
        install.install.assert_not_called()
        log.assert_called_once()
        self.assertEqual(progress.call_args.args[2],'warning')

    def test_external_setup_cannot_overwrite_installed_executable(self):
        import desktop_launcher
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);target=root/'DIEF JARVIS.exe'
            target.write_bytes(b'installed launcher')
            source=root/'external.exe';source.write_bytes(b'older external launcher')
            with patch('sys.frozen',True,create=True),patch('sys.executable',str(source)),patch('desktop_launcher.subprocess.run'):
                desktop_launcher.install_launcher(root,root/'shortcuts')
            self.assertEqual(target.read_bytes(),b'installed launcher')

    def test_failure_messages_only_claim_restoration_when_confirmed(self):
        from desktop_launcher import recovery_message
        install=Mock()
        install.rollback.return_value=False
        self.assertIn('Nao ha uma versao anterior',recovery_message(install))
        install.rollback.return_value=True
        self.assertIn('foi restaurada',recovery_message(install))
        install.rollback.side_effect=OSError('blocked')
        with patch('core.update_diagnostics.record_failure') as log:
            self.assertIn('nao foi concluida',recovery_message(install))
            log.assert_called_once()

    def test_current_app_still_repairs_old_launcher_without_touching_data(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);install=Installation(root)
            atomic_json(install.state_file,{'current':'2.1.1','pending':False})
            target=root/'DIEF JARVIS.exe';target.write_bytes(b'old')
            data=root/'data';data.mkdir();(data/'memory').write_bytes(b'keep')
            digest=hashlib.sha256(b'new').hexdigest()
            release={'version':'2.1.1','launcher':{'sha256':digest}}
            def fetch(item,path,*args):path.write_bytes(b'new')
            with patch('sys.frozen',True,create=True),patch('core.distribution.download',side_effect=fetch) as download:
                self.assertTrue(install.ensure_launcher(release,lambda *args:None,threading.Event()))
                self.assertFalse(install.ensure_launcher(release,lambda *args:None,threading.Event()))
                self.assertEqual(download.call_count,1)
            self.assertEqual(target.read_bytes(),b'old')
            self.assertEqual((data/'memory').read_bytes(),b'keep')
            self.assertEqual(install.state()['pending_launcher']['sha256'],digest)

    def test_failed_download_does_not_damage_installed_launcher(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);install=Installation(root)
            atomic_json(install.state_file,{'current':'2.1.1'})
            target=root/'DIEF JARVIS.exe';target.write_bytes(b'old')
            with patch('sys.frozen',True,create=True),patch('core.distribution.download',side_effect=TimeoutError()):
                with self.assertRaises(TimeoutError):
                    install.ensure_launcher({'version':'2.1.1','launcher':{'sha256':'a'*64}},lambda *args:None,threading.Event())
            self.assertEqual(target.read_bytes(),b'old')
            self.assertNotIn('pending_launcher',install.state())

    @unittest.skipUnless(os.name=='nt','PowerShell replacement test')
    def test_replacement_success_and_failed_probe_restore_actual_files(self):
        for succeeds in (True,False):
            with self.subTest(succeeds=succeeds),tempfile.TemporaryDirectory() as folder:
                root=Path(folder);nonce='a'*32
                source=root/'new.exe';source.write_bytes(b'new executable fixture')
                target=root/'installed.exe';target.write_bytes(b'previous executable fixture')
                paths=[source,target,root/'temp.exe',root/'backup.exe',root/'logs/result.json',root/'probe.ready',root]
                assignments=';'.join('$p'+str(i)+'=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String("'+base64.b64encode(str(p).encode()).decode()+'"))' for i,p in enumerate(paths))+';'
                digest=hashlib.sha256(source.read_bytes()).hexdigest()
                # Only the child process is simulated. Copy, atomic replace,
                # hashing, rollback and diagnostic writes run in PowerShell.
                fake='function Start-Process { param($FilePath,$ArgumentList,$WindowStyle,[switch]$PassThru) '
                if succeeds:fake+="[IO.File]::WriteAllText($p5,'"+digest+"');"
                fake+='$v=[pscustomobject]@{ExitCode='+('0' if succeeds else '1')+';HasExited=$true};$v|Add-Member ScriptMethod WaitForExit {param($t) return $true};return $v };'
                script=assignments+fake+replacement_body(digest,nonce)
                result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-EncodedCommand',base64.b64encode(script.encode('utf-16le')).decode()],capture_output=True,timeout=30)
                self.assertEqual(result.returncode,0,result.stderr.decode(errors='replace'))
                status=json.loads(paths[4].read_text(encoding='utf-8-sig'))
                self.assertEqual(status['success'],succeeds,status)
                self.assertEqual(status['restored'],not succeeds,status)
                self.assertEqual(target.read_bytes(),source.read_bytes() if succeeds else b'previous executable fixture')
                self.assertEqual(paths[3].read_bytes(),b'previous executable fixture')


if __name__=='__main__':unittest.main()
