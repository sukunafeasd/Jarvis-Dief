import json
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QLabel, QFormLayout
from core.settings_hub import SettingsHub
from core.ui_sounds import SoundDirector, TONES


class PanelSoundPreferenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])

    def setUp(self):
        folder=tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root=Path(folder.name)
        self.config=self.root/'preferences.json'
        self.config.write_text('{}',encoding='utf-8')

    def director(self,backend=True,offscreen=False,cache_error=False):
        effect_class=Mock()
        effect_class.Loop.Infinite.value=-2
        def effect(parent):
            value=Mock()
            value.isPlaying.return_value=False
            return value
        effect_class.side_effect=effect
        with patch('core.ui_sounds.QSoundEffect',effect_class if backend else None), \
             patch.dict(os.environ,{'QT_QPA_PLATFORM':'offscreen' if offscreen else ''}), \
             patch('core.ui_sounds.QStandardPaths.writableLocation',return_value=str(self.root)), \
             patch('core.ui_sounds.cue_pcm',return_value=b'\x00\x00'), \
             patch('core.ui_sounds.Path.mkdir',side_effect=OSError('cache unavailable')) if cache_error else patch('core.ui_sounds.time.monotonic',return_value=100):
            value=SoundDirector(None,self.config)
        self.addCleanup(value.deleteLater)
        self.addCleanup(value.ambient_timer.stop)
        return value

    def test_startup_reads_persisted_preference_and_default_config_path(self):
        self.config.write_text('{"panel_sounds_muted":true}',encoding='utf-8')
        value=self.director()
        self.assertTrue(value.enabled)
        self.assertTrue(value.muted)
        self.assertEqual(set(value.effects),set(TONES))
        value.scene(visible=True)
        self.assertFalse(value.play('click'))
        for effect in value.effects.values():effect.play.assert_not_called()
        with patch('memory.config_manager.CONFIG_FILE',self.config):
            other=SoundDirector(None)
        self.addCleanup(other.deleteLater)
        self.addCleanup(other.ambient_timer.stop)
        self.assertTrue(other.muted)

    def test_invalid_or_missing_preference_is_safe_and_silent(self):
        for content in ('{}','[]','null','{"panel_sounds_muted":"false"}',
                        '{"gemini_api_key":"secret",invalid}',None,b'\xff'):
            with self.subTest(content=content),patch('builtins.print') as output:
                if content is None:self.config.unlink(missing_ok=True)
                elif isinstance(content,bytes):self.config.write_bytes(content)
                else:self.config.write_text(content,encoding='utf-8')
                value=self.director(offscreen=True)
                self.assertFalse(value.muted)
                output.assert_not_called()

    def test_mute_stops_every_effect_and_blocks_all_playback_paths(self):
        value=self.director()
        value.scene(visible=True,resting=True)
        self.assertTrue(value.play('warning'))
        value.speaking=True;value.music=True
        for effect in value.effects.values():effect.reset_mock()
        value.set_muted(True)
        self.assertTrue(value.enabled)
        self.assertTrue(value.visible)
        self.assertTrue(value.resting)
        self.assertTrue(value.speaking)
        self.assertTrue(value.music)
        self.assertIsNone(value.active_cue)
        for effect in value.effects.values():effect.stop.assert_called_once()
        for name in TONES:self.assertFalse(value.play(name))
        value.voice(False);value.media({'is_playing':False})
        value.scene(visible=True);value.ambient_timer.timeout.emit()
        for effect in value.effects.values():effect.play.assert_not_called()
        value.set_muted(False)
        value.effects['ambient'].play.assert_called_once()
        self.assertTrue(value.play('warning'))

    def test_unmute_respects_scene_voice_music_and_backend_capability(self):
        for state in ('hidden','voice','music'):
            with self.subTest(state=state):
                value=self.director();value.set_muted(True)
                value.visible=state!='hidden'
                value.speaking=state=='voice';value.music=state=='music'
                value.set_muted(False)
                value.effects['ambient'].play.assert_not_called()
        for options in ({'backend':False},{'offscreen':True},{'cache_error':True}):
            with self.subTest(options=options):
                value=self.director(**options)
                self.assertFalse(value.enabled)
                value.set_muted(True);value.set_muted(False)
                value.scene(visible=True)
                self.assertFalse(value.enabled)
                self.assertFalse(value.play('click'))

    def hub(self,sounds=True):
        window=QMainWindow()
        window.hud=SimpleNamespace(hud_style='core')
        window._muted=False
        window.voice=Mock();window.microphone=Mock();window.music=Mock()
        window._open_memory_panel=Mock()
        window._open_audio_devices=Mock()
        window._apply_name_update=Mock();window._update_brief_btn=Mock()
        window.on_voice_change=Mock()
        if sounds:window._ui_sounds=self.director()
        class ConnectionsStub(QWidget):
            def __init__(self,hub):
                super().__init__();self.body=self
        with patch('core.settings_connections.ConnectionsPage',ConnectionsStub), \
             patch.object(SettingsHub,'refresh'), \
             patch.object(SettingsHub,'animate_entry'):
            hub=SettingsHub(window,self.config,{})
        hub.timer.stop()
        self.addCleanup(window.deleteLater)
        self.addCleanup(hub.deleteLater)
        self.addCleanup(hub.close)
        return hub,window

    def save(self,hub):
        with patch('memory.config_manager.save_hud_style'), \
             patch('memory.config_manager.save_voice'), \
             patch.object(SettingsHub,'animate_entry'):
            hub.save()

    def test_profile_checkbox_applies_immediately_saves_merge_and_reopens(self):
        original={'gemini_api_key':'test-secret','plugin_config':{'example':{'token':'private'}},
                  'input_device':'mic','output_device':'speaker','morning_brief_enabled':False}
        self.config.write_text(json.dumps(original),encoding='utf-8')
        hub,window=self.hub()
        profile=hub.tabs.widget(hub.page_indices['profile']).widget()
        self.assertTrue(profile.isAncestorOf(hub.panel_sounds_muted))
        from core.settings_components import LightSwitch
        self.assertIsInstance(hub.panel_sounds_muted,LightSwitch)
        self.assertEqual(hub.panel_sounds_muted.accessibleName(),'Silenciar sons do painel')
        form=next(layout for layout in profile.findChildren(QFormLayout)
                  if layout.getWidgetPosition(hub.panel_sounds_muted)[0]>=0)
        label=form.labelForField(hub.panel_sounds_muted)
        self.assertIsNotNone(label)
        self.assertEqual([item.text() for item in label.findChildren(QLabel)
                          if item.objectName()=='fieldTitle'],['Silenciar sons do painel'])
        self.assertFalse(hub.panel_sounds_muted.isChecked())
        window._ui_sounds.scene(visible=True)
        hub.panel_sounds_muted.setChecked(True)
        self.assertTrue(window._ui_sounds.muted)
        window._ui_sounds.effects['ambient'].stop.assert_called()
        self.assertFalse(window._muted)
        window.on_voice_change.assert_not_called()
        for audio in (window.voice,window.microphone,window.music):self.assertEqual(audio.mock_calls,[])
        # Merge the latest file, including changes made after the dialog opened.
        original['later_preference']=42
        self.config.write_text(json.dumps(original),encoding='utf-8')
        from core.local_data import atomic_write
        with patch('core.local_data.atomic_write',wraps=atomic_write) as write:
            self.save(hub)
        write.assert_called_once()
        saved=json.loads(self.config.read_text(encoding='utf-8'))
        for key,value in original.items():self.assertEqual(saved[key],value)
        self.assertTrue(saved['panel_sounds_muted'])
        self.assertEqual(list(self.root.glob('*.tmp')),[])
        restored,other=self.hub()
        self.assertTrue(restored.panel_sounds_muted.isChecked())
        self.assertTrue(other._ui_sounds.muted)
        restored.panel_sounds_muted.setChecked(False)
        self.save(restored)
        self.assertFalse(json.loads(self.config.read_text())['panel_sounds_muted'])
        self.assertFalse(self.director().muted)

    def test_profile_works_without_director_and_failed_save_preserves_config(self):
        hub,window=self.hub(sounds=False)
        hub.panel_sounds_muted.setChecked(True)
        for content in ('{"gemini_api_key":"private",broken}', '[]'):
            with self.subTest(content=content):
                self.config.write_text(content,encoding='utf-8')
                self.save(hub)
                self.assertEqual(self.config.read_text(encoding='utf-8'),content)
                self.assertNotIn('private',hub.notice.text())
                self.assertIn('Não foi possível',hub.notice.text())
        self.config.write_text('{"gemini_api_key":"private"}',encoding='utf-8')
        with patch('core.local_data.atomic_write',side_effect=OSError('private')):
            self.save(hub)
        self.assertEqual(json.loads(self.config.read_text()),{'gemini_api_key':'private'})
        window.on_voice_change.assert_not_called()
        self.save(hub)
        self.assertTrue(json.loads(self.config.read_text())['panel_sounds_muted'])


if __name__=='__main__':unittest.main()
