import base64
import hashlib
import json
from pathlib import Path
import tempfile
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from core.dependency_integrity import broken_distributions
from desktop_launcher import bounded_release


class IncrementalIntegrityTests(unittest.TestCase):
    def test_directory_replacing_file_is_damage_and_outside_entries_are_ignored(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)/'env';root.mkdir()
            payload=root/'sample.py';payload.mkdir()
            entry=SimpleNamespace(hash=SimpleNamespace(mode='sha256',value='invalid'))
            distribution=SimpleNamespace(files=[entry],metadata={'Name':'sample'},locate_file=lambda e:payload)
            with patch('core.dependency_integrity.sys.prefix',str(root)),patch('core.dependency_integrity.importlib.metadata.distributions',return_value=[distribution]):
                self.assertEqual(broken_distributions(root/'cache.json'),['sample'])
                distribution.locate_file=lambda e:Path(folder)/'outside.py'
                self.assertEqual(broken_distributions(root/'cache.json'),[])

    def test_file_reparse_point_gets_canonical_target_checked(self):
        import stat
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);payload=root/'sample.py';payload.write_bytes(b'hello')
            digest=base64.urlsafe_b64encode(hashlib.sha256(b'hello').digest()).rstrip(b'=').decode()
            entry=SimpleNamespace(hash=SimpleNamespace(mode='sha256',value=digest))
            distribution=SimpleNamespace(files=[entry],metadata={'Name':'sample'},locate_file=lambda e:payload)
            original=Path.lstat
            def lstat(path):
                if path==payload:return SimpleNamespace(st_mode=stat.S_IFREG,st_file_attributes=1024)
                return original(path)
            with patch('core.dependency_integrity.sys.prefix',folder),patch('core.dependency_integrity.importlib.metadata.distributions',return_value=[distribution]),patch.object(Path,'lstat',lstat):
                self.assertEqual(broken_distributions(root/'cache.json'),[])

    def test_outside_link_to_missing_inside_target_is_not_skipped(self):
        import stat
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)/'env';root.mkdir()
            link=Path(folder)/'outside-link';target=root/'missing.py'
            entry=SimpleNamespace(hash=SimpleNamespace(mode='sha256',value='invalid'))
            distribution=SimpleNamespace(files=[entry],metadata={'Name':'sample'},locate_file=lambda e:link)
            resolve=Path.resolve;lstat=Path.lstat
            def redirected(path,*args,**kwargs):
                return target if path==link else resolve(path,*args,**kwargs)
            def info(path):
                return SimpleNamespace(st_mode=stat.S_IFLNK,st_file_attributes=1024) if path==link else lstat(path)
            with patch('core.dependency_integrity.sys.prefix',str(root)),patch('core.dependency_integrity.importlib.metadata.distributions',return_value=[distribution]),patch.object(Path,'resolve',redirected),patch.object(Path,'lstat',info):
                self.assertEqual(broken_distributions(root/'cache.json'),['sample'])

    def test_unchanged_files_skip_hash_but_damage_and_expiry_do_not(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);payload=root/'sample.py';payload.write_bytes(b'hello')
            digest=base64.urlsafe_b64encode(hashlib.sha256(b'hello').digest()).rstrip(b'=').decode()
            entry=SimpleNamespace(hash=SimpleNamespace(mode='sha256',value=digest))
            distribution=SimpleNamespace(files=[entry],metadata={'Name':'sample'},locate_file=lambda e:payload)
            cache=root/'cache.json'
            with patch('core.dependency_integrity.sys.prefix',folder),patch('core.dependency_integrity.importlib.metadata.distributions',return_value=[distribution]):
                self.assertEqual(broken_distributions(cache),[])
                with patch('core.dependency_integrity.hashlib.new',side_effect=AssertionError('unnecessary hashing')):
                    self.assertEqual(broken_distributions(cache),[])
                saved=json.loads(cache.read_text());saved['verified_at']=0;cache.write_text(json.dumps(saved))
                with patch('core.dependency_integrity.hashlib.new',wraps=hashlib.new) as hashing:
                    self.assertEqual(broken_distributions(cache),[])
                    hashing.assert_called_once()
                payload.write_bytes(b'wrong')
                self.assertEqual(broken_distributions(cache),['sample'])
                payload.unlink()
                self.assertEqual(broken_distributions(cache),['sample'])

    def test_network_timeout_and_cancellation_are_bounded(self):
        gate=threading.Event()
        try:
            with self.assertRaises(TimeoutError):bounded_release(lambda:gate.wait(2),threading.Event(),timeout=.03)
            stop=threading.Event();stop.set()
            with self.assertRaises(InterruptedError):bounded_release(lambda:None,stop)
            self.assertEqual(bounded_release(lambda:{'version':'test'},threading.Event()),{'version':'test'})
        finally:gate.set()


if __name__=='__main__':unittest.main()
