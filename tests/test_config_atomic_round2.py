"""Strict configuration persistence using temporary files and no accounts."""
import os
import tempfile

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('DIEF_JARVIS_DATA_DIR', tempfile.mkdtemp(prefix='dief-config-atomic-'))

import json
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from memory import config_manager as config


class ConfigAtomicTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory(prefix='dief-config-case-')
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.path = self.root / 'preferences.json'
        context = patch.object(config, 'CONFIG_FILE', self.path)
        context.start()
        self.addCleanup(context.stop)

    def setters(self):
        return [
            lambda: config.save_api_keys('synthetic-key'),
            lambda: config.save_assistant_config('Assistant', 'Synthetic'),
            lambda: config.save_voice('Kore'),
            lambda: config.save_wake_word_enabled(True),
            lambda: config.save_push_to_talk_enabled(True),
            lambda: config.save_hud_style('core'),
            lambda: config.save_thinking_enabled(True),
            lambda: config.save_turn_tuning({'silence_ms': 700}),
            lambda: config.save_proactive_audio_enabled(False),
            lambda: config.save_media_resolution('high'),
            lambda: config.save_brief_enabled(False),
            lambda: config.save_input_device('Synthetic input'),
            lambda: config.save_output_device('Synthetic output'),
            lambda: config.save_plugin_config('synthetic', {'value': 1}),
            lambda: config.save_plugin_enabled('synthetic', False),
        ]

    def test_every_setter_preserves_corrupt_or_non_object_json(self):
        for raw in (b'{broken', b'[]', b'null', b'"text"', b'\xff', b'{"old":NaN}', b'{"voice_name":NaN}'):
            for index, save in enumerate(self.setters()):
                with self.subTest(raw=raw, setter=index):
                    self.path.write_bytes(raw)
                    with self.assertRaises(ValueError):
                        save()
                    self.assertEqual(self.path.read_bytes(), raw)
        self.assertEqual(list(self.root.glob('*.tmp')), [])

    def test_nested_invalid_config_is_preserved(self):
        cases = [
            ({'turn_tuning': []}, lambda: config.save_turn_tuning({'enabled': True})),
            ({'plugin_config': []}, lambda: config.save_plugin_config('synthetic', {})),
            ({'plugin_config': {'synthetic': []}}, lambda: config.save_plugin_config('synthetic', {})),
            ({'plugins_enabled': []}, lambda: config.save_plugin_enabled('synthetic', True)),
        ]
        for data, save in cases:
            with self.subTest(data=data):
                raw = json.dumps(data).encode()
                self.path.write_bytes(raw)
                with self.assertRaises(ValueError):
                    save()
                self.assertEqual(self.path.read_bytes(), raw)

    def test_non_object_reads_return_defaults_without_repairing_file(self):
        for raw in (b'[]', b'null', b'"text"', b'7', b'true'):
            with self.subTest(raw=raw):
                self.path.write_bytes(raw)
                with patch('core.local_data.atomic_write', side_effect=AssertionError('Read must not write')):
                    self.assertEqual(config.load_api_keys(), {})
                    self.assertIsNone(config.get_gemini_key())
                    self.assertFalse(config.is_configured())
                    self.assertEqual(config.get_assistant_name(), 'DIEF JARVIS')
                    self.assertEqual(config.get_user_name(), '')
                    self.assertEqual(config.get_voice(), config.DEFAULT_VOICE)
                    self.assertEqual(config.get_hud_style(), 'face')
                    self.assertEqual(config.get_input_device(), '')
                    self.assertEqual(config.get_output_device(), '')
                    self.assertEqual(config.get_plugin_config('synthetic'), {})
                    self.assertIs(config.get_plugin_enabled('synthetic'), True)
                with self.assertRaises(ValueError):
                    config.save_api_keys('synthetic-key')
                self.assertEqual(self.path.read_bytes(), raw)

    def test_invalid_plugin_flag_container_reads_defaults_without_writing(self):
        for value in ([], None, False, 7, 'invalid'):
            with self.subTest(value=value):
                raw = json.dumps({'plugins_enabled': value, 'keep': True}).encode()
                self.path.write_bytes(raw)
                with patch('core.local_data.atomic_write', side_effect=AssertionError('Read must not write')):
                    self.assertIs(config.get_plugin_enabled('synthetic'), True)
                with self.assertRaises(ValueError):
                    config.save_plugin_enabled('synthetic', False)
                self.assertEqual(self.path.read_bytes(), raw)
        raw = b'{"plugins_enabled":{"on":true,"off":false},"keep":true}'
        self.path.write_bytes(raw)
        self.assertIs(config.get_plugin_enabled('on'), True)
        self.assertIs(config.get_plugin_enabled('off'), False)
        self.assertIs(config.get_plugin_enabled('missing'), True)
        self.assertEqual(self.path.read_bytes(), raw)

    def test_concurrent_setters_keep_unrelated_fields_and_nested_updates(self):
        self.path.write_text('{"existing":{"keep":true}}', encoding='utf-8')
        saves = self.setters() + [
            lambda: config.save_turn_tuning({'prefix_ms': 200}),
            lambda: config.save_plugin_config('synthetic', {'other': 2}),
            lambda: config.save_plugin_enabled('another', True),
        ]
        barrier = threading.Barrier(len(saves))

        def run(save):
            barrier.wait(timeout=5)
            save()

        with ThreadPoolExecutor(max_workers=len(saves)) as executor:
            list(executor.map(run, saves))
        data = json.loads(self.path.read_text(encoding='utf-8'))
        expected = {
            'existing': {'keep': True}, 'gemini_api_key': 'synthetic-key',
            'assistant_name': 'Assistant', 'user_name': 'Synthetic', 'voice_name': 'Kore',
            'wake_word_enabled': True, 'push_to_talk_enabled': True, 'hud_style': 'core',
            'thinking_enabled': True, 'turn_tuning': {'silence_ms': 700, 'prefix_ms': 200},
            'proactive_audio': False, 'media_resolution': 'high', 'morning_brief_enabled': False,
            'input_device': 'Synthetic input', 'output_device': 'Synthetic output',
            'plugin_config': {'synthetic': {'value': 1, 'other': 2}},
            'plugins_enabled': {'synthetic': False, 'another': True},
        }
        self.assertEqual(data, expected)
        self.assertEqual(list(self.root.glob('*.tmp')), [])

    def test_mutation_and_plugin_writer_share_the_same_lock(self):
        entered = threading.Event()
        release = threading.Event()
        attempting = threading.Event()
        finished = threading.Event()

        def paused(data):
            entered.set()
            if not release.wait(timeout=3):
                raise TimeoutError('Synthetic gate')
            data['user_name'] = 'Synthetic'

        def plugin():
            attempting.set()
            config.save_plugin_config('synthetic', {'value': 1})
            finished.set()

        with ThreadPoolExecutor(max_workers=2) as executor:
            first = executor.submit(config.mutate_config, paused)
            try:
                self.assertTrue(entered.wait(timeout=1))
                second = executor.submit(plugin)
                self.assertTrue(attempting.wait(timeout=1))
                self.assertFalse(finished.wait(timeout=.05))
            finally:
                release.set()
            first.result(timeout=2)
            second.result(timeout=2)
        self.assertEqual(json.loads(self.path.read_text()), {
            'user_name': 'Synthetic', 'plugin_config': {'synthetic': {'value': 1}}})

    def test_failed_replace_preserves_original_and_cleans_temporary_file(self):
        raw = b'{"existing":true}'
        self.path.write_bytes(raw)
        with patch('core.local_data.os.replace', side_effect=OSError('Synthetic replace failure')):
            with self.assertRaises(OSError):
                config.save_voice('Kore')
        self.assertEqual(self.path.read_bytes(), raw)
        self.assertEqual(list(self.root.glob('*.tmp')), [])

    def test_custom_path_does_not_read_or_change_default_config(self):
        self.path.write_bytes(b'{default-invalid')
        custom = self.root / 'custom' / 'profile.json'
        config.save_api_keys('synthetic-key', path=custom)
        self.assertEqual(json.loads(custom.read_text()), {'gemini_api_key': 'synthetic-key'})
        self.assertEqual(self.path.read_bytes(), b'{default-invalid')


class ConfigKeyUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from PyQt6.QtWidgets import QLineEdit, QLabel
        folder = tempfile.TemporaryDirectory(prefix='dief-config-ui-')
        self.addCleanup(folder.cleanup)
        self.path = Path(folder.name) / 'custom.json'
        self.hub = SimpleNamespace(config_path=self.path, ai_key=QLineEdit('synthetic-key'),
                                   ai_notice=QLabel(), window=SimpleNamespace(on_voice_change=Mock()),
                                   _ai_check=None, check_ai=Mock())
        self.addCleanup(self.hub.ai_key.deleteLater)
        self.addCleanup(self.hub.ai_notice.deleteLater)

    def save(self):
        from core.settings_hub import SettingsHub
        SettingsHub.save_ai_key(self.hub)

    def test_failed_key_save_keeps_input_and_never_reconnects(self):
        for raw in (b'{broken', b'[]', b'\xff'):
            with self.subTest(raw=raw):
                self.path.write_bytes(raw)
                self.save()
                self.assertEqual(self.path.read_bytes(), raw)
                self.assertEqual(self.hub.ai_key.text(), 'synthetic-key')
                self.assertIn('salvar', self.hub.ai_notice.text())
                self.assertNotIn('synthetic-key', self.hub.ai_notice.text())
                self.hub.check_ai.assert_not_called()
                self.hub.window.on_voice_change.assert_not_called()
        self.path.write_bytes(b'{"keep":true}')
        with patch('core.local_data.atomic_write', side_effect=OSError('synthetic-key')):
            self.save()
        self.assertEqual(self.hub.ai_key.text(), 'synthetic-key')
        self.assertEqual(self.path.read_bytes(), b'{"keep":true}')
        self.hub.check_ai.assert_not_called()
        self.assertNotIn('synthetic-key', self.hub.ai_notice.text())

    def test_successful_key_save_uses_custom_path_and_then_clears_input(self):
        self.path.write_text('{"keep":true}', encoding='utf-8')
        default = self.path.parent / 'default.json'
        default.write_text('{"default":true}', encoding='utf-8')
        with patch.object(config, 'CONFIG_FILE', default):
            self.save()
        self.assertEqual(json.loads(self.path.read_text()), {'keep': True, 'gemini_api_key': 'synthetic-key'})
        self.assertEqual(json.loads(default.read_text()), {'default': True})
        self.assertEqual(self.hub.ai_key.text(), '')
        self.hub.check_ai.assert_called_once_with(reset_session=True)


if __name__ == '__main__':
    unittest.main()
