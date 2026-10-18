"""Settings transactions use only temporary stores and synthetic credentials."""
import json
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import tempfile
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch

from core import gmail_connection as gmail,local_data
from core.connection_states import ConnectionChecks
from core.settings_hub import SettingsHub
from memory import config_manager as config


class SettingsTransactionTests(unittest.TestCase):
    def setUp(self):
        folder=tempfile.TemporaryDirectory(prefix='dief-round5-')
        self.addCleanup(folder.cleanup)
        self.root=Path(folder.name)
        self.profile=self.root/'profile.json'
        self.credentials=self.root/'client.json'
        for target,name,value in ((config,'CONFIG_FILE',self.profile),
                                  (gmail,'CREDENTIALS',self.credentials),
                                  (gmail,'TOKEN',self.root/'unused-token.bin')):
            item=patch.object(target,name,value);item.start();self.addCleanup(item.stop)
        self.original=b'{"keep": true, "plugin_config":{"gmail_control":{"expected_email":"old@example.test"}}, "city":"old"}'
        self.profile.write_bytes(self.original)
        self.old_credentials=b'{"installed":{"client_id":"old.apps.googleusercontent.com","client_secret":"synthetic-old"}}'
        self.credentials.write_bytes(self.old_credentials)
        self.original_apply_identity=SettingsHub._apply_saved_identity
        self.identity=patch.object(SettingsHub,'_apply_saved_identity')
        self.apply_identity=self.identity.start();self.addCleanup(self.identity.stop)

    def field(self,value):
        field=Mock()
        field.text.return_value=value;field.toPlainText.return_value=value
        field.currentData.return_value=value;field.currentText.return_value=value
        field.value.return_value=value;field.isChecked.return_value=value
        return field

    def profile_hub(self):
        window=Mock();window.findChildren.return_value=[]
        hub=SimpleNamespace(config_path=self.profile,window=window,notice=Mock(),appearance_notice=Mock(),
                            selected_color='#12ABCD',_set_panel_sounds_muted=Mock(),animate_entry=Mock(),core_preview=Mock())
        values={'assistant_name':' Fixture Bot ','name':' Fixture User ','city':' New City ',
                'interests':' science ','speech_provider':'gemini','visual':'core','voice':'Kore',
                'count':3,'hold':20,'brief':False,'reduced':True,'panel_sounds_muted':True}
        for name,value in values.items():setattr(hub,name,self.field(value))
        return hub

    def gmail_hub(self):
        checks=ConnectionChecks();generation=checks.begin('gmail')
        checks.finish('gmail',generation,'connected','Previously verified')
        hub=SimpleNamespace(_connection_checks=checks,connection_notice=Mock(),
                            gmail_client=self.field('new.apps.googleusercontent.com'),
                            gmail_secret=self.field('synthetic-new'),gmail_email=self.field('new@example.test'),
                            connections_page=SimpleNamespace(_local_at=123),refresh=Mock(),_connection_worker=Mock())
        hub.save_gmail_credentials=lambda:SettingsHub.save_gmail_credentials(hub)
        return hub

    def assert_profile_not_applied(self,hub):
        self.apply_identity.assert_not_called()
        hub.window.on_voice_change.assert_not_called()
        hub.window._update_brief_btn.assert_not_called()
        hub._set_panel_sounds_muted.assert_not_called()
        hub.animate_entry.assert_not_called()
        hub.core_preview.sync_preview.assert_not_called()
        self.assertEqual(hub.notice.setText.call_args,hub.appearance_notice.setText.call_args)
        self.assertIn('salvar o perfil',hub.notice.setText.call_args.args[0])

    def test_profile_replace_failure_preserves_every_field_and_runtime(self):
        hub=self.profile_hub()
        with patch.object(local_data.os,'replace',side_effect=OSError('synthetic failure')):
            SettingsHub.save(hub)
        self.assertEqual(self.profile.read_bytes(),self.original)
        self.assertEqual(list(self.root.glob('*.tmp')),[])
        self.assert_profile_not_applied(hub)
        self.assertEqual(hub.city.text(),' New City ')

    def test_profile_failure_does_not_create_missing_store(self):
        self.profile.unlink();hub=self.profile_hub()
        with patch.object(local_data.os,'replace',side_effect=OSError('synthetic failure')):
            SettingsHub.save(hub)
        self.assertFalse(self.profile.exists())
        self.assert_profile_not_applied(hub)

    def test_profile_invalid_store_is_not_overwritten(self):
        for raw in (b'{broken',b'[]',b'\xff'):
            with self.subTest(raw=raw):
                self.profile.write_bytes(raw);hub=self.profile_hub()
                SettingsHub.save(hub)
                self.assertEqual(self.profile.read_bytes(),raw)
                self.assert_profile_not_applied(hub)

    def test_profile_commits_all_fields_once_before_runtime_and_reconnect(self):
        hub=self.profile_hub()
        default=self.root/'other-profile.json';default.write_bytes(b'{"other":true}')
        def applied(*args):
            saved=json.loads(self.profile.read_bytes())
            self.assertEqual(saved['voice_name'],'Kore')
            self.assertEqual(saved['assistant_name'],'Fixture Bot')
            self.assertEqual(saved['hud_style'],'core')
            self.assertEqual(saved['ui_color'],'#12abcd')
            hub.window.on_voice_change.assert_not_called()
        self.apply_identity.side_effect=applied
        with patch.object(config,'CONFIG_FILE',default), \
             patch.object(local_data,'atomic_write',wraps=local_data.atomic_write) as write, \
             patch.object(config,'save_hud_style',side_effect=AssertionError('redundant write')), \
             patch.object(config,'save_voice',side_effect=AssertionError('redundant write')):
            SettingsHub.save(hub)
        write.assert_called_once()
        self.assertEqual(write.call_args.args[0],self.profile)
        saved=json.loads(self.profile.read_bytes())
        for key,value in {'user_name':'Fixture User','city':'New City','news_interests':'science',
                          'news_count':3,'presentation_hold':20,'morning_brief_enabled':False,
                          'reduce_motion':True,'panel_sounds_muted':True,'speech_provider':'gemini','keep':True}.items():
            self.assertEqual(saved[key],value,key)
        self.assertEqual(saved['plugin_config'],json.loads(self.original)['plugin_config'])
        self.assertEqual(default.read_bytes(),b'{"other":true}')
        hub.window._apply_name_update.assert_not_called()
        hub.window.on_voice_change.assert_called_once_with()
        self.assertEqual(hub.window.hud.hud_style,'core')
        self.assertIn('salva',hub.appearance_notice.setText.call_args.args[0])

    def test_profile_failure_can_be_retried(self):
        hub=self.profile_hub()
        with patch.object(local_data,'atomic_write',side_effect=OSError('synthetic failure')):
            SettingsHub.save(hub)
        SettingsHub.save(hub)
        self.assertEqual(json.loads(self.profile.read_bytes())['city'],'New City')
        hub.window.on_voice_change.assert_called_once_with()

    def test_saved_identity_updates_ui_without_another_storage_callback(self):
        hub=self.profile_hub()
        ui=SimpleNamespace(current_palette=Mock(return_value={'PRI':'#000000'}),
                           apply_ui_accent=Mock(return_value=True),retheme_all_widgets=Mock())
        with patch.dict(sys.modules,{'ui':ui}):
            self.original_apply_identity(hub,'Fixture Bot','#12abcd')
        self.assertEqual(hub.window._assistant_name,'Fixture Bot')
        self.assertEqual(hub.window.hud._assistant_name,'FIXTURE BOT')
        self.assertEqual(hub.window._log._ai_name_lc,'fixture bot')
        hub.window._title_lbl.setText.assert_called_once_with('FIXTURE BOT')
        ui.apply_ui_accent.assert_called_once_with('#12abcd')
        ui.retheme_all_widgets.assert_called_once()
        hub.window._apply_name_update.assert_not_called()
        self.assertEqual(self.profile.read_bytes(),self.original)

    def assert_gmail_restored(self,hub):
        self.assertEqual(self.profile.read_bytes(),self.original)
        self.assertEqual(self.credentials.read_bytes(),self.old_credentials)
        hub.gmail_secret.clear.assert_not_called()
        hub._connection_worker.assert_not_called()
        self.assertEqual(hub._connection_checks.get('gmail')['state'],'connected')
        self.assertEqual(hub.connections_page._local_at,123)

    def test_gmail_expected_account_failure_restores_replaced_credentials(self):
        hub=self.gmail_hub()
        with patch.object(gmail,'save_expected_account',side_effect=OSError('synthetic failure')):
            SettingsHub.connect_gmail(hub)
        self.assert_gmail_restored(hub)
        self.assertNotIn('synthetic-new',hub.connection_notice.setText.call_args.args[0])

    def test_gmail_late_failure_restores_both_stores_exactly(self):
        hub=self.gmail_hub();save=gmail.save_expected_account
        def fail_after_write(email):
            save(email)
            self.assertEqual(config.get_plugin_setting('gmail_control','expected_email'),'new@example.test')
            raise OSError('synthetic failure after second write')
        with patch.object(gmail,'save_expected_account',side_effect=fail_after_write):
            self.assertFalse(SettingsHub.save_gmail_credentials(hub))
        self.assert_gmail_restored(hub)

    def test_gmail_invalid_profile_preserves_credentials_and_corrupt_bytes(self):
        self.original=b'{broken';self.profile.write_bytes(self.original)
        hub=self.gmail_hub()
        self.assertFalse(SettingsHub.save_gmail_credentials(hub))
        self.assert_gmail_restored(hub)

    def test_gmail_failed_initial_save_removes_new_credentials(self):
        self.credentials.unlink();hub=self.gmail_hub()
        with patch.object(gmail,'save_expected_account',side_effect=OSError('synthetic failure')):
            self.assertFalse(SettingsHub.save_gmail_credentials(hub))
        self.assertFalse(self.credentials.exists())
        self.assertEqual(self.profile.read_bytes(),self.original)
        hub.gmail_secret.clear.assert_not_called()

    def test_gmail_credentials_write_failure_preserves_expected_account(self):
        hub=self.gmail_hub()
        with patch.object(gmail,'atomic_write',side_effect=OSError('synthetic failure')):
            self.assertFalse(SettingsHub.save_gmail_credentials(hub))
        self.assert_gmail_restored(hub)

    def test_gmail_rollback_failure_is_explicit_and_attempts_other_restore(self):
        hub=self.gmail_hub();save=gmail.save_expected_account;write=local_data.atomic_write
        def fail_after_write(email):
            save(email)
            raise OSError('synthetic save failure')
        def fail_credential_restore(path,data):
            if path==self.credentials:raise OSError('synthetic rollback failure')
            write(path,data)
        with patch.object(gmail,'save_expected_account',side_effect=fail_after_write), \
             patch.object(local_data,'atomic_write',side_effect=fail_credential_restore):
            self.assertFalse(SettingsHub.save_gmail_credentials(hub))
        self.assertEqual(self.profile.read_bytes(),self.original)
        self.assertNotEqual(self.credentials.read_bytes(),self.old_credentials)
        self.assertIn('restaurar',hub.connection_notice.setText.call_args.args[0])
        self.assertIn('podem ter sido alteradas',hub.connection_notice.setText.call_args.args[0])
        self.assertEqual(hub._connection_checks.get('gmail')['state'],'error')
        hub.gmail_secret.clear.assert_not_called();hub.refresh.assert_called_once_with()

    def test_gmail_success_clears_input_after_both_writes_and_can_retry_failure(self):
        hub=self.gmail_hub()
        with patch.object(gmail,'save_expected_account',side_effect=OSError('synthetic failure')):
            self.assertFalse(SettingsHub.save_gmail_credentials(hub))
        save=gmail.save_expected_account
        def check(email):
            hub.gmail_secret.clear.assert_not_called()
            self.assertEqual(json.loads(self.credentials.read_bytes())['installed']['client_secret'],'synthetic-new')
            save(email)
        with patch.object(gmail,'save_expected_account',side_effect=check):
            self.assertTrue(SettingsHub.save_gmail_credentials(hub))
        self.assertEqual(config.get_plugin_setting('gmail_control','expected_email'),'new@example.test')
        hub.gmail_secret.clear.assert_called_once_with()
        self.assertEqual(hub._connection_checks.get('gmail'),{})
        hub.refresh.assert_called_once_with()

    def test_gmail_validation_failure_does_not_write(self):
        hub=self.gmail_hub();hub.gmail_email.text.return_value='invalid'
        self.assertFalse(SettingsHub.save_gmail_credentials(hub))
        self.assert_gmail_restored(hub)


if __name__=='__main__':
    unittest.main()
