import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from core.factory_defaults import initialize,ROOT
import launch


class FactoryTests(unittest.TestCase):
    def test_first_run_has_no_identity_credentials_or_connections(self):
        template=(ROOT/'config/defaults.json').read_text(encoding='utf-8')
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'config').mkdir();(root/'config/defaults.json').write_text(template,encoding='utf-8')
            self.assertTrue(initialize(root))
            value=json.loads((root/'config/api_keys.json').read_text(encoding='utf-8'))
            for key in ('user_name','city','news_interests','gemini_api_key'):self.assertEqual(value[key],'')
            self.assertEqual(value['plugin_config'],{})
            self.assertTrue(all(value['plugins_enabled'].values()))
            self.assertEqual(value['hud_style'],'core');self.assertFalse(value['reduce_motion'])
            self.assertEqual(list((root/'config').glob('token*')),[])

    def test_existing_personal_settings_are_not_replaced(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'config').mkdir();path=root/'config/api_keys.json';path.write_text('{"user_name":"Teste"}')
            self.assertFalse(initialize(root));self.assertEqual(json.loads(path.read_text())['user_name'],'Teste')

    def test_launcher_requires_elevation_before_installation(self):
        with patch('core.elevation.require_admin',return_value=False),patch.object(launch,'prepare') as prepare:
            launch.main();prepare.assert_not_called()

    def test_existing_environment_is_reused(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);path=root/'.venv/Scripts/python.exe';path.parent.mkdir(parents=True);path.touch()
            with patch('launch.os.name','nt'),patch('launch.venv.EnvBuilder') as builder:
                self.assertEqual(launch.prepare(root),path);builder.assert_not_called()
