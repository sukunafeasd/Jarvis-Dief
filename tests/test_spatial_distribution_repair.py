import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from core.distribution import prepare_spatial_access
from tools.prepare_public_release import audit


class SpatialDistributionRepairTests(unittest.TestCase):
    def test_release_rejects_missing_three_dependency(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError, 'three.module.js'):
                audit(Path(folder), [])

    def test_access_grant_targets_only_public_scene_and_current_user(self):
        with tempfile.TemporaryDirectory() as folder:
            application = Path(folder)
            scene = application / 'core' / 'spatial'
            scene.mkdir(parents=True)
            with patch('core.distribution.subprocess.run', return_value=SimpleNamespace(stdout=b'"user","S-1-5-21-10-20-30-1001"')) as run:
                prepare_spatial_access(application)
            commands = [call.args[0] for call in run.call_args_list]
            self.assertEqual(commands[0], ['whoami.exe', '/user', '/fo', 'csv', '/nh'])
            self.assertEqual(commands[1], ['icacls.exe', str(scene), '/grant', '*S-1-5-21-10-20-30-1001:(OI)(CI)(RX)', '/T', '/Q'])

    def test_missing_identity_never_changes_access(self):
        with tempfile.TemporaryDirectory() as folder:
            application = Path(folder)
            (application / 'core' / 'spatial').mkdir(parents=True)
            with patch('core.distribution.subprocess.run', return_value=SimpleNamespace(stdout=b'invalid')) as run:
                with self.assertRaises(RuntimeError):
                    prepare_spatial_access(application)
            self.assertEqual(run.call_count, 1)
