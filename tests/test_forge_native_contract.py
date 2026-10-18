"""Real Qt native contract. One isolated subprocess supplies all assertions.

FORJA_NATIVE_REPORT may point to the report from an explicitly requested prior
run. Otherwise this suite runs the native harness; it requires a Windows desktop.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.name == 'nt', 'Real Windows QtWebEngine validation')
class ForgeNativeContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        report_path = os.environ.get('FORJA_NATIVE_REPORT')
        if not report_path:
            env = dict(os.environ)
            env.pop('QT_QPA_PLATFORM', None)
            result = subprocess.run([sys.executable, str(ROOT / 'tools/validate_forja_native.py')],
                                    cwd=ROOT, env=env, capture_output=True, text=True, timeout=180)
            summaries = []
            for line in result.stdout.splitlines():
                try:
                    value = json.loads(line)
                    if isinstance(value, dict) and value.get('report'):
                        summaries.append(value)
                except ValueError:
                    pass
            if not summaries:
                raise AssertionError('Native harness produced no report: ' + result.stderr[-4000:])
            report_path = summaries[-1]['report']
        cls.report_path = Path(report_path)
        cls.report = json.loads(cls.report_path.read_text(encoding='utf-8'))
        cls.checks = {item['name']: item for item in cls.report['checks']}

    def require(self, *names):
        for name in names:
            with self.subTest(contract=name, report=str(self.report_path)):
                self.assertIn(name, self.checks, 'Scenario was blocked before this contract could run')
                self.assertTrue(self.checks[name]['passed'], self.checks[name].get('detail'))

    def test_real_renderer_ready_camera_and_black_panel_sequence(self):
        self.require('native_boot', 'enter_request_ready', 'full_stage_actual_core',
                     'all_black_stage', 'white_light_panel_sequence')

    def test_readonly_hashed_animated_artifact_and_no_qt_access(self):
        self.require('fixture_hash', 'fixture_read_only', 'fixture_sandbox_header',
                     'snapshot_fixture_projection', 'fixture_pixels_animate', 'artifact_no_qt_or_parent_access')

    def test_focused_f11_and_native_commands(self):
        self.require('f11_focused_view', 'f11_restore_and_resize', 'native_command_hash')

    def test_exit_restores_persistent_pins_health_and_geometry(self):
        self.require('pins_fixture_persisted', 'pins_hidden_in_forge', 'exit_request_normal',
                     'pins_restored_persistent', 'ordinary_visibility_restored', 'native_geometry_restored',
                     'core_health_after_exit', 'preview_disposed_after_exit')

    def test_repeat_reduced_and_timed_cancel(self):
        self.require('repeat_reduced_entry', 'repeat_snapshot_and_preview', 'repeat_reduced_exit',
                     'timed_cancel_events', 'cancel_no_late_callbacks', 'cancel_pins_restored')

    def test_no_native_callback_exceptions_or_real_runtime_commands(self):
        self.assertEqual(self.report['exceptions'], [])
        self.assertEqual(self.report.get('runtime_calls', []), [])


if __name__ == '__main__':
    unittest.main()
