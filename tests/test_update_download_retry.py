import hashlib
import io
from pathlib import Path
import ssl
import tempfile
import unittest
import urllib.error
from unittest.mock import Mock,patch
from core.distribution import download


class DownloadRecoveryTests(unittest.TestCase):
    def setUp(self):
        folder=tempfile.TemporaryDirectory();self.addCleanup(folder.cleanup)
        self.target=Path(folder.name)/'package.zip'
        self.data=b'verified content'
        self.item={'url':'https://github.com/sukunafeasd/Jarvis-Dief/releases/download/v2.1.0/package.zip',
                   'size':len(self.data),'sha256':hashlib.sha256(self.data).hexdigest()}
        self.stop=Mock();self.stop.is_set.return_value=False;self.stop.wait.return_value=False

    def test_short_download_restarts_cleanly_and_checks_hash(self):
        with patch('urllib.request.urlopen',side_effect=[io.BytesIO(b'partial'),io.BytesIO(self.data)]) as fetch:
            download(self.item,self.target,lambda _:None,self.stop)
        self.assertEqual(fetch.call_count,2)
        self.assertEqual(self.target.read_bytes(),self.data)

    def test_retry_limit_removes_only_own_partial_file(self):
        with patch('urllib.request.urlopen',side_effect=TimeoutError()) as fetch:
            with self.assertRaises(TimeoutError):download(self.item,self.target,lambda _:None,self.stop)
        self.assertEqual(fetch.call_count,3)
        self.assertFalse(self.target.exists())

    def test_existing_file_is_not_deleted_or_overwritten(self):
        self.target.write_bytes(b'keep')
        with patch('urllib.request.urlopen') as fetch:
            with self.assertRaises(FileExistsError):download(self.item,self.target,lambda _:None,self.stop)
        fetch.assert_not_called()
        self.assertEqual(self.target.read_bytes(),b'keep')

    def test_bad_hash_is_rejected_without_retry(self):
        with patch('urllib.request.urlopen',return_value=io.BytesIO(b'x'*len(self.data))) as fetch:
            with self.assertRaises(ValueError):download(self.item,self.target,lambda _:None,self.stop)
        self.assertEqual(fetch.call_count,1)
        self.assertFalse(self.target.exists())

    def test_cancel_during_backoff_does_not_open_second_connection(self):
        self.stop.wait.return_value=True
        with patch('urllib.request.urlopen',side_effect=TimeoutError()) as fetch:
            with self.assertRaises(InterruptedError):download(self.item,self.target,lambda _:None,self.stop)
        self.assertEqual(fetch.call_count,1)
        self.assertFalse(self.target.exists())

    def test_certificate_error_is_not_retried(self):
        error=urllib.error.URLError(ssl.SSLCertVerificationError('invalid certificate'))
        with patch('urllib.request.urlopen',side_effect=error) as fetch:
            with self.assertRaises(urllib.error.URLError):download(self.item,self.target,lambda _:None,self.stop)
        self.assertEqual(fetch.call_count,1)

    def test_permanent_http_error_is_not_retried(self):
        error=urllib.error.HTTPError(self.item['url'],404,'missing',{},None)
        with patch('urllib.request.urlopen',side_effect=error) as fetch:
            with self.assertRaises(urllib.error.HTTPError):download(self.item,self.target,lambda _:None,self.stop)
        self.assertEqual(fetch.call_count,1)


if __name__=='__main__':unittest.main()
