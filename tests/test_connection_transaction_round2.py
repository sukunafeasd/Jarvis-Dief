"""Failed connection saves preserve the previous profile and entered token."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from memory import config_manager as config
from ui import PluginSettingsOverlay


class ConnectionTransactionTests(unittest.TestCase):
    def fixture(self):
        field=Mock()
        owner=SimpleNamespace(
            _gather=lambda ns: {'access_token':'synthetic-new','voice_id':'new'},
            _widgets={('fish_audio','access_token'):field},
            parentWidget=lambda:None)
        return owner,field

    def test_invalid_profile_does_not_change_token_or_clear_input(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'profile.json'
            path.write_text('{broken')
            owner,field=self.fixture()
            with patch.object(config,'CONFIG_FILE',path),patch('core.integration_tokens.write') as write:
                with self.assertRaises(ValueError):PluginSettingsOverlay._save_ns(owner,'fish_audio')
                write.assert_not_called()
            field.clear.assert_not_called()
            self.assertEqual(path.read_text(),'{broken')

    def test_failed_secret_write_restores_exact_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'profile.json'
            previous=b'{"plugin_config":{"fish_audio":{"voice_id":"old"}},"keep":true}'
            path.write_bytes(previous)
            owner,field=self.fixture()
            with patch.object(config,'CONFIG_FILE',path),patch('core.integration_tokens.write',side_effect=OSError('fixture')):
                with self.assertRaises(OSError):PluginSettingsOverlay._save_ns(owner,'fish_audio')
            field.clear.assert_not_called()
            self.assertEqual(path.read_bytes(),previous)

    def test_success_clears_input_only_after_both_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'profile.json'
            owner,field=self.fixture()
            def check(*args):
                self.assertEqual(config.get_plugin_config('fish_audio')['voice_id'],'new')
                field.clear.assert_not_called()
            with patch.object(config,'CONFIG_FILE',path),patch('core.integration_tokens.write',side_effect=check) as write:
                PluginSettingsOverlay._save_ns(owner,'fish_audio')
                write.assert_called_once_with('fish_audio',{'token':'synthetic-new'})
                self.assertEqual(config.get_plugin_config('fish_audio')['access_token'],'')
            field.clear.assert_called_once()
