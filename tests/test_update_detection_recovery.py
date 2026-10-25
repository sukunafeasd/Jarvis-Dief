import unittest
import tempfile
import json
from pathlib import Path
import urllib.error
from unittest.mock import patch,Mock
from core import distribution
from core.update_watch import UpdateWatch


class UpdateDetectionRecoveryTests(unittest.TestCase):
    def test_diagnostic_preserves_cause_without_sensitive_exception_text(self):
        from core.update_diagnostics import record_failure
        with tempfile.TemporaryDirectory() as folder:
            error=urllib.error.HTTPError('https://private/?token=secret',429,'secret',{},None)
            self.assertEqual(record_failure(folder,'lookup',error,'2.0.0'),'http')
            path=Path(folder)/'logs/last-update-error.json'
            record=json.loads(path.read_text())
            self.assertEqual(record['http_status'],429)
            self.assertNotIn('secret',path.read_text())
            record_failure(folder,'install',TimeoutError('secret'),'2.0.0','2.1.0')
            self.assertEqual(json.loads(path.read_text())['category'],'timeout')

    def test_api_rate_limit_uses_official_signed_asset(self):
        body={'version':'2.1.0',**{k:{'name':k+'.zip'} for k in ('application','runtime','launcher')}}
        error=urllib.error.HTTPError('https://api.github.com',403,'rate limited',{},None)
        with patch.object(distribution,'request_json',side_effect=[error,{'signed':'value'}]) as request, \
             patch.object(distribution,'verified_manifest',return_value=body) as verify:
            result=distribution.latest_release()
        verify.assert_called_once_with({'signed':'value'})
        self.assertEqual(request.call_args.args[0],
            'https://github.com/sukunafeasd/Jarvis-Dief/releases/latest/download/release.json')
        self.assertIn('/releases/download/v2.1.0/',result['application']['url'])

    def test_invalid_signature_does_not_trigger_alternative_trust(self):
        info={'assets':[{'name':'release.json','browser_download_url':
            'https://github.com/sukunafeasd/Jarvis-Dief/releases/download/v2.1.0/release.json'}]}
        with patch.object(distribution,'request_json',side_effect=[info,{}]) as request, \
             patch.object(distribution,'verified_manifest',side_effect=ValueError('invalid signature')):
            with self.assertRaisesRegex(ValueError,'invalid signature'):distribution.latest_release()
        self.assertEqual(request.call_count,2)

    def test_missing_repository_is_not_treated_as_rate_limit(self):
        error=urllib.error.HTTPError('https://api.github.com',404,'not found',{},None)
        with patch.object(distribution,'request_json',side_effect=error) as request:
            with self.assertRaises(urllib.error.HTTPError):distribution.latest_release()
        self.assertEqual(request.call_count,1)

    def test_temporary_failure_retries_soon_without_parallel_queries(self):
        watch=UpdateWatch('2.0.0',fetch=Mock())
        watch.busy=True;watch.next_check=1800
        watch.results.put(None)
        self.assertIsNone(watch.tick(now=100))
        self.assertEqual(watch.next_check,130)
        self.assertIsNone(watch.tick(now=129))
        watch.fetch.assert_not_called()
        watch.busy=True
        self.assertIsNone(watch.tick(now=140))
        watch.fetch.assert_not_called()

    def test_backoff_is_bounded_and_success_restores_normal_interval(self):
        watch=UpdateWatch('2.0.0')
        for n in range(8):
            watch.results.put(None);watch.tick(now=100)
            self.assertLessEqual(watch.next_check,400)
        watch.results.put({'version':'2.1.0'})
        self.assertEqual(watch.tick(now=100)['version'],'2.1.0')
        self.assertEqual(watch.failures,0)
        self.assertEqual(watch.next_check,1900)


if __name__=='__main__':unittest.main()
