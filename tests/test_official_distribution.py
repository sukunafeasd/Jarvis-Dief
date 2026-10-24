import base64
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
import zipfile
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from core.distribution import Installation,canonical,verified_manifest,version,extract,download,official_url
from core.release_identity import REPOSITORY


class OfficialDistributionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.base=Path(self.temp.name)
        self.installation=Installation(self.base/'installed');self.stop=threading.Event()
        self.key=Ed25519PrivateKey.generate()
        self.public=base64.b64encode(self.key.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)).decode()
    def tearDown(self):self.temp.cleanup()
    def package(self,number='1.0.0'):
        application=self.base/(number+'.zip');runtime=self.base/'runtime.zip'
        with zipfile.ZipFile(application,'w') as file:
            for name,value in {'main.py':'print(1)','requirements.txt':'','VERSION.json':json.dumps({'version':number}),
                'core/startup.py':'','config/defaults.json':'{}','config/__init__.py':'',
                'memory/config_manager.py':'VERSION="'+number+'"'}.items():file.writestr(name,value)
        with zipfile.ZipFile(runtime,'w') as file:file.writestr('python.exe',b'fake-runtime')
        def descriptor(path):return {'name':'application.zip' if path==application else 'runtime.zip','size':path.stat().st_size,
            'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'url':str(path)}
        return {'schema':1,'version':number,'repository':REPOSITORY,'application':descriptor(application),'runtime':descriptor(runtime),
            'launcher':{'name':'setup.exe','size':1,'sha256':'0'*64}}
    def local_download(self,item,target,progress,stop):Path(target).write_bytes(Path(item['url']).read_bytes())
    def install(self,body):
        with patch('core.distribution.download',side_effect=self.local_download):
            return self.installation.install(body,lambda *args:None,self.stop)
    def signed(self,body):return {'release':body,'signature':base64.b64encode(self.key.sign(canonical(body))).decode()}
    def test_signature_rejects_changed_version_and_wrong_channel(self):
        body=self.package();body['application'].pop('url');body['runtime'].pop('url')
        signed=self.signed(body);self.assertEqual(verified_manifest(signed,self.public)['version'],'1.0.0')
        changed=copy.deepcopy(signed);changed['release']['version']='1.0.1'
        with self.assertRaises(InvalidSignature):verified_manifest(changed,self.public)
        body['repository']='someone/else'
        with self.assertRaises(ValueError):verified_manifest(self.signed(body),self.public)
    def test_path_traversal_and_case_collisions_are_rejected(self):
        for names in (['../escape'],['C:/escape'],['test','TEST'],['AUX.txt'],['a\\b']):
            archive=self.base/'bad.zip'
            with zipfile.ZipFile(archive,'w') as file:
                for name in names:
                    info=zipfile.ZipInfo('safe');info.filename=name;file.writestr(info,'bad')
            with self.assertRaises(ValueError,msg=repr(names)):extract(archive,self.base/'out')
            self.assertFalse((self.base/'escape').exists())
    def test_non_releases_and_wrong_hosts_are_rejected(self):
        for url in ('http://github.com/'+REPOSITORY+'/releases/download/v1/a.zip','https://example.test/a.zip',
            'https://github.com/'+REPOSITORY+'/releases/download/v1/a.zip?token=bad'):
            with self.assertRaises(ValueError):official_url(url)
        self.assertEqual(version('v1.10.0'),(1,10,0))
        with self.assertRaises(ValueError):version('../main')
    def test_fresh_install_and_update_preserve_personal_files(self):
        first=self.install(self.package());self.installation.confirm()
        personal=self.installation.root/'data/config/api_keys.json';personal.write_text('{"user_name":"Teste"}')
        memory=self.installation.root/'data/memory/local.json';memory.write_text('{"fact":"Teste"}')
        second=self.install(self.package('1.0.1'))
        self.assertEqual((first/'config/api_keys.json').read_text(),personal.read_text())
        self.assertEqual((second/'memory/local.json').read_text(),memory.read_text())
        self.assertEqual(self.installation.state()['previous'],'1.0.0')
        self.assertTrue(self.installation.rollback())
        self.assertEqual(self.installation.state()['current'],'1.0.0')
        self.assertIn('1.0.0',(first/'memory/config_manager.py').read_text())
        self.assertIn('Teste',personal.read_text())
        self.assertEqual(self.install(self.package('1.0.1')),first)
    def test_invalid_app_does_not_replace_current_or_private_data(self):
        self.install(self.package());self.installation.confirm();body=self.package('1.0.1')
        with zipfile.ZipFile(body['application']['url'],'w') as file:file.writestr('main.py','broken')
        with self.assertRaises(ValueError):self.install(body)
        self.assertEqual(self.installation.state()['current'],'1.0.0')
    def test_download_integrity_and_cancellation_remove_partial_file(self):
        data=b'hello';item={'name':'a.zip','url':f'https://github.com/{REPOSITORY}/releases/download/v1.0.0/a.zip',
            'size':len(data),'sha256':hashlib.sha256(data).hexdigest()};target=self.base/'download.zip'
        with patch('urllib.request.urlopen',return_value=io.BytesIO(data)):download(item,target,lambda _:None,self.stop)
        self.assertEqual(target.read_bytes(),data);target.unlink()
        item['sha256']='0'*64
        with patch('urllib.request.urlopen',return_value=io.BytesIO(data)),self.assertRaises(ValueError):download(item,target,lambda _:None,self.stop)
        self.assertFalse(target.exists());self.stop.set()
        with patch('urllib.request.urlopen',return_value=io.BytesIO(data)),self.assertRaises(InterruptedError):download(item,target,lambda _:None,self.stop)
        self.assertFalse(target.exists())
    def test_offline_launch_preserves_installation_and_probes_it(self):
        import desktop_launcher
        app=self.install(self.package());self.installation.confirm()
        with patch.object(Installation,'prepare_python',return_value=Path('python.exe')),patch.object(desktop_launcher,'prepare_dependencies'),\
            patch.object(desktop_launcher,'run_probe') as probe,patch.object(desktop_launcher,'install_launcher'):
            value=desktop_launcher.prepare(self.installation.root,lambda *args:None,self.stop,fetch=lambda:(_ for _ in ()).throw(OSError('offline')))
        self.assertEqual(value[2],app);probe.assert_called_once()

    def test_opening_upgrades_one_to_two_and_preserves_accounts(self):
        import desktop_launcher
        self.install(self.package('1.0.0'));self.installation.confirm()
        personal=self.installation.root/'data/config/api_keys.json'
        personal.write_text('{"fixture":"preserved"}')
        release=self.package('2.0.7')
        with patch('core.distribution.download',side_effect=self.local_download),\
            patch.object(Installation,'prepare_python',return_value=Path('python.exe')),\
            patch.object(desktop_launcher,'prepare_dependencies') as dependencies,\
            patch.object(desktop_launcher,'run_probe') as probe,\
            patch.object(desktop_launcher,'install_launcher'):
            ready=desktop_launcher.prepare(self.installation.root,lambda *args:None,self.stop,fetch=lambda:release)
        self.assertEqual(ready[2],self.installation.application('2.0.7'))
        self.assertTrue(self.installation.state()['pending'])
        self.assertEqual(personal.read_text(),'{"fixture":"preserved"}')
        dependencies.assert_called_once();probe.assert_called_once()
        self.installation.confirm()
        self.assertFalse(self.installation.state()['pending'])
        self.assertTrue(self.installation.application('1.0.0').exists())
    def test_health_marker_cannot_write_outside_managed_sessions(self):
        from core.distribution_health import confirm_window
        sessions=self.installation.root/'sessions';sessions.mkdir()
        with patch.dict(os.environ,{'DIEF_MANAGED_ROOT':str(self.installation.root)}):
            self.assertFalse(confirm_window(self.base/'outside.ready'))
            self.assertTrue(confirm_window(sessions/'test.ready'))

    def test_failed_state_commit_restores_runtime_and_shared_code(self):
        from core.distribution import atomic_json
        first=self.install(self.package());self.installation.confirm();runtime=self.installation.root/'runtime/python.exe'
        prior=runtime.read_bytes();body=self.package('1.0.1')
        with zipfile.ZipFile(body['runtime']['url'],'w') as file:file.writestr('python.exe','new-runtime')
        body['runtime']['sha256']='1'*64
        def commit(path,value):
            if Path(path)==self.installation.state_file:raise OSError('disk failure')
            return atomic_json(path,value)
        with patch('core.distribution.atomic_json',side_effect=commit),self.assertRaises(OSError):self.install(body)
        self.assertEqual(runtime.read_bytes(),prior)
        self.assertEqual(self.installation.state()['current'],'1.0.0')
        self.assertIn('1.0.0',(first/'memory/config_manager.py').read_text())
        self.assertFalse(self.installation.application('1.0.1').exists())

    def test_abrupt_exit_recovers_before_the_next_install(self):
        first=self.install(self.package());self.installation.confirm();old_runtime=(self.installation.root/'runtime/python.exe').read_bytes()
        body=self.package('1.0.1')
        with zipfile.ZipFile(body['runtime']['url'],'w') as file:file.writestr('python.exe','new runtime')
        body['runtime']['sha256']='2'*64
        with patch.object(self.installation,'activate_shared',side_effect=KeyboardInterrupt),self.assertRaises(KeyboardInterrupt):self.install(body)
        self.assertTrue(self.installation.journal.exists())
        self.installation=Installation(self.installation.root)
        self.assertEqual(self.installation.state()['current'],'1.0.0')
        self.assertEqual((self.installation.root/'runtime/python.exe').read_bytes(),old_runtime)
        self.assertIn('1.0.0',(first/'memory/config_manager.py').read_text())
        self.assertFalse(self.installation.journal.exists())

    def test_download_failure_uses_the_confirmed_version(self):
        import desktop_launcher
        app=self.install(self.package());self.installation.confirm();release=self.package('1.0.1')
        with patch.object(Installation,'install',side_effect=OSError('download')),patch.object(Installation,'prepare_python',return_value=Path('python.exe')),\
            patch.object(desktop_launcher,'prepare_dependencies'),patch.object(desktop_launcher,'run_probe') as probe,patch.object(desktop_launcher,'install_launcher'):
            value=desktop_launcher.prepare(self.installation.root,lambda *args:None,self.stop,fetch=lambda:release)
        self.assertEqual(value[2],app);probe.assert_called_once()

    def test_interrupted_environment_is_recreated(self):
        target=self.installation.root/'environment/Scripts/python.exe';target.parent.mkdir(parents=True);target.touch()
        calls=[]
        def runner(command,stop,**kwargs):
            calls.append(command)
            if len(calls)==1:raise RuntimeError('missing pip')
            if '-m' in command and 'venv' in command:target.parent.mkdir(parents=True);target.touch()
        with patch('core.distribution.run',side_effect=runner):self.assertEqual(self.installation.prepare_python(self.stop),target)
        self.assertEqual(len(calls),3)

    def test_private_key_is_blocked_by_export_audit(self):
        from tools.prepare_public_release import audit
        path=self.base/'release-key.txt'
        path.write_bytes(self.key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
        with self.assertRaises(ValueError):audit(self.base,[Path('release-key.txt')])

    @unittest.skipUnless(os.name=='nt','Windows shortcut integration')
    def test_shortcut_helper_handles_spaces_without_touching_desktop(self):
        import sys
        import desktop_launcher
        root=self.base/'test install & name';root.mkdir();folder=self.base/'test desktop'
        with patch.object(sys,'frozen',True,create=True):desktop_launcher.install_launcher(root,folder)
        self.assertTrue((folder/'DIEF JARVIS.lnk').is_file())

    def test_cancel_stops_the_entire_installer_tree(self):
        import sys,time
        from core.distribution import run
        alive=self.base/'alive';late=self.base/'late';errors=[]
        child=f"from pathlib import Path;import time;Path({str(alive)!r}).touch();time.sleep(1);Path({str(late)!r}).touch();time.sleep(10)"
        parent=f"import subprocess,sys,time;subprocess.Popen([sys.executable,'-c',{child!r}]);time.sleep(20)"
        def worker():
            try:run([sys.executable,'-c',parent],self.stop,timeout=10)
            except InterruptedError:errors.append('cancelled')
        thread=threading.Thread(target=worker);thread.start();deadline=time.monotonic()+5
        while not alive.exists() and time.monotonic()<deadline:time.sleep(.02)
        self.stop.set();thread.join(timeout=5);time.sleep(1.1)
        self.assertEqual(errors,['cancelled']);self.assertFalse(thread.is_alive());self.assertFalse(late.exists())
