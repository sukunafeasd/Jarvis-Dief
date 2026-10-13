import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from core import gmail_connection as gmail


class GmailIdentityTests(unittest.TestCase):
    def test_briefing_inbox_count_does_not_read_message_headers(self):
        with patch.object(gmail,'_service') as service,patch.object(gmail,'status',return_value={'account_email':'test@example.com'}):
            service.return_value.users.return_value.labels.return_value.get.return_value.execute.return_value={'messagesUnread':17,'messagesTotal':40}
            result=gmail.inbox_summary()
            self.assertEqual(result['inbox_unread'],17)
            service.return_value.users.return_value.messages.assert_not_called()
    def credentials(self):
        from google.oauth2.credentials import Credentials
        return Credentials(token='dummy-token', refresh_token='dummy-refresh',
                           token_uri='https://oauth2.googleapis.com/token',
                           client_id='test.apps.googleusercontent.com', client_secret='dummy', scopes=gmail.SCOPES)

    def test_manual_oauth_configuration_and_public_client_id(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(gmail, 'CREDENTIALS', Path(folder)/'client.json'):
            gmail.configure_credentials('test.apps.googleusercontent.com', 'dummy-secret')
            self.assertEqual(gmail.credential_client_id(), 'test.apps.googleusercontent.com')
            value = json.loads(gmail.CREDENTIALS.read_text())['installed']
            self.assertEqual(value['token_uri'], 'https://oauth2.googleapis.com/token')
            before = gmail.CREDENTIALS.read_bytes()
            with self.assertRaises(ValueError):
                gmail.configure_credentials('ordinary-api-key', 'dummy')
            self.assertEqual(gmail.CREDENTIALS.read_bytes(), before)

    def test_verified_account_survives_refresh_without_plaintext(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(gmail, 'TOKEN', Path(folder)/'token.bin'), patch('core.gmail_connection._monitoring', return_value=False):
            credentials = self.credentials()
            gmail._save(credentials, 'test@example.com')
            self.assertNotIn(b'test@example.com', gmail.TOKEN.read_bytes())
            gmail._save(gmail._load())
            self.assertEqual(gmail.status()['account_email'], 'test@example.com')
            other = self.credentials()
            other._refresh_token = 'different-refresh'
            gmail._save(other)
            self.assertEqual(gmail.status()['account_email'], '')

    def test_wrong_google_account_does_not_replace_existing_connection(self):
        with patch.object(gmail, 'CREDENTIALS', Mock()), patch('google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file') as flow, patch.object(gmail, '_build_service') as service, patch.object(gmail, '_save') as save:
            flow.return_value.run_local_server.return_value = self.credentials()
            service.return_value.users.return_value.getProfile.return_value.execute.return_value = {'emailAddress': 'other@example.com'}
            ok, message = gmail.connect('wanted@example.com')
            self.assertFalse(ok)
            self.assertIn('Não substituí', message)
            save.assert_not_called()
            self.assertEqual(flow.return_value.run_local_server.call_args.kwargs['login_hint'], 'wanted@example.com')

    def test_matching_account_is_saved_only_after_google_verifies(self):
        with patch.object(gmail, 'CREDENTIALS', Mock()), patch('google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file') as flow, patch.object(gmail, '_build_service') as service, patch.object(gmail, '_save') as save:
            credentials = self.credentials()
            flow.return_value.run_local_server.return_value = credentials
            service.return_value.users.return_value.getProfile.return_value.execute.return_value = {'emailAddress': 'wanted@example.com'}
            self.assertTrue(gmail.connect('wanted@example.com')[0])
            save.assert_called_once_with(credentials, 'wanted@example.com')

    def test_verify_reports_actual_account_not_typed_address(self):
        credentials = self.credentials()
        with patch.object(gmail, '_service') as service, patch.object(gmail, '_load', return_value=credentials), patch.object(gmail, '_save') as save:
            service.return_value.users.return_value.getProfile.return_value.execute.return_value = {'emailAddress': 'actual@example.com'}
            ok, message = gmail.verify('typed@example.com')
            self.assertFalse(ok)
            self.assertIn('actual@example.com', message)
            save.assert_called_once_with(credentials, 'actual@example.com')

    def test_invalid_email_does_not_save_preferences(self):
        with patch('memory.config_manager.save_plugin_config') as save:
            with self.assertRaises(ValueError):
                gmail.save_expected_account('not an email')
            save.assert_not_called()
