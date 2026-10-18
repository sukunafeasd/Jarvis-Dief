"""Storage migration and disconnect regressions, with synthetic data only."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class StorageTests(unittest.TestCase):
    def test_document_adapters_refuse_new_private_data_folder(self):
        from core import local_data,extension_suite,file_library
        with tempfile.TemporaryDirectory() as directory:
            private=Path(directory)/'private';private.mkdir()
            path=private/'synthetic.md';path.write_text('not readable by document tools')
            with patch.object(local_data,'ROOT',private):
                with self.assertRaises(ValueError):file_library.safe_path(path)
                with self.assertRaises(ValueError):extension_suite.run('markitdown',{'action':'read','path':str(path)})

    def test_save_before_first_load_prepares_legacy_migration(self):
        from core import local_data
        from memory import config_manager as config
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);legacy=root/'old/config/api_keys.json'
            legacy.parent.mkdir(parents=True);legacy.write_text('{"existing":true}')
            target=root/'new/api_keys.json'
            with patch.object(config,'BASE_DIR',root/'old'),patch.object(config,'CONFIG_FILE',target),patch.object(config,'DEFAULT_CONFIG_FILE',target),patch.object(local_data,'ROOT',root/'new'),patch.object(local_data,'ALLOW_LEGACY',True):
                config.save_voice('Charon')
                self.assertTrue(json.loads(target.read_text())['existing'])
                self.assertTrue(legacy.exists())

    def test_migration_preserves_original_and_does_not_overwrite_new_data(self):
        from core import local_data
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);legacy=root/'legacy.json';legacy.write_text('{"synthetic":1}')
            with patch.object(local_data,'ROOT',root/'new'),patch.object(local_data,'ALLOW_LEGACY',True):
                target=local_data.migrate(legacy,'profile.json')
                self.assertEqual(json.loads(target.read_text()),{'synthetic':1})
                local_data.atomic_write(target,b'{"synthetic":2}')
                self.assertEqual(local_data.migrate(legacy,'profile.json'),target)
                self.assertEqual(json.loads(target.read_text()),{'synthetic':2})
                self.assertEqual(json.loads(legacy.read_text()),{'synthetic':1})

    def test_isolated_profile_never_copies_legacy_credentials(self):
        from core import local_data
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);legacy=root/'legacy.json';legacy.write_text('{"synthetic":1}')
            with patch.object(local_data,'ROOT',root/'new'),patch.object(local_data,'ALLOW_LEGACY',False):
                self.assertFalse(local_data.migrate(legacy,'profile.json').exists())

    def test_token_removal_prevents_legacy_resurrection(self):
        from core import integration_tokens as tokens
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);legacy=root/'old';private=root/'new'
            with patch.object(tokens,'ROOT',legacy):tokens.write('synthetic',{'token':'fake-value'})
            with patch.object(tokens,'ROOT',private),patch.object(tokens,'DEFAULT_ROOT',private),patch.object(tokens,'LEGACY_ROOT',legacy),patch.object(tokens,'ALLOW_LEGACY',True):
                self.assertEqual(tokens.read('synthetic'),{'token':'fake-value'})
                tokens.remove('synthetic')
                self.assertEqual(tokens.read('synthetic'),{})
                self.assertTrue((legacy/'token_synthetic.bin').exists())

    def test_plugin_save_preserves_other_settings_and_refuses_corrupt_json(self):
        from memory import config_manager as config
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'profile.json';path.write_text('{"existing":true}')
            with patch.object(config,'CONFIG_FILE',path):
                config.save_plugin_config('synthetic',{'enabled':True})
                self.assertTrue(json.loads(path.read_text())['existing'])
                path.write_text('{broken')
                with self.assertRaises(ValueError):config.save_plugin_config('synthetic',{'enabled':False})
                self.assertEqual(path.read_text(),'{broken')


if __name__=='__main__':unittest.main()
