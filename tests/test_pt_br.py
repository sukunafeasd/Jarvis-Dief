import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from PyQt6.QtCore import QLocale
from PyQt6.QtGui import QFontDatabase
from PyQt6.QtWidgets import QApplication, QLabel, QPushButton
import ui
import main
from actions import web_search


class PortugueseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        # The offscreen Qt plugin does not discover Windows' installed fonts.
        fonts = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
        for name in ("cour.ttf", "courbd.ttf", "segoeui.ttf", "seguiemj.ttf"):
            if (fonts / name).exists():
                QFontDatabase.addApplicationFont(str(fonts / name))

    def test_initial_setup_labels_and_submission(self):
        overlay = ui.SetupOverlay()
        labels = [label.text() for label in overlay.findChildren(QLabel)]
        self.assertIn("DIEF JARVIS", labels)
        self.assertIn("CHAVE DE API DO GEMINI", labels)
        self.assertIn("SISTEMA OPERACIONAL", labels)
        received = []
        overlay.done.connect(lambda key, system: received.append((key, system)))
        overlay._key_input.setText("test-key-not-a-real-secret")
        overlay._sel("windows")
        overlay._submit()
        self.assertEqual(received, [("test-key-not-a-real-secret", "windows")])
        overlay.resize(440, 420)
        overlay.show()
        self.app.processEvents()
        output = Path(__file__).resolve().parents[1] / 'validation/setup-finish.png'
        self.assertTrue(overlay.grab().save(str(output)))
        overlay.close()

    def test_live_voice_language_and_tool_contracts(self):
        runner = main.JarvisLive.__new__(main.JarvisLive)
        registry = Mock()
        registry.get_tool_declarations.return_value = []
        runner._action_registry = runner._plugin_registry = registry
        runner._resume_handle = None
        runner._enhanced_live = runner._tuned_live = False
        with patch.object(main, "load_memory", return_value={
            "identity": {"language": {"value": "English"}}
        }):
            config = runner._build_config()
        self.assertIn("Brazilian Portuguese (pt-BR)", config.system_instruction)
        self.assertIn("Override historical language preferences", config.system_instruction)
        self.assertIsNone(config.speech_config.language_code)
        self.assertEqual(config.realtime_input_config.activity_handling, main.types.ActivityHandling.NO_INTERRUPTION)
        self.assertIn(config.speech_config.voice_config.prebuilt_voice_config.voice_name,
                      main.__dict__["get_voice"].__globals__["AVAILABLE_VOICES"])
        names = {item.name for item in config.tools[0].function_declarations}
        self.assertIn("save_memory", names)
        self.assertIn("screen_process", names)

    def test_native_dialog_locale(self):
        self.assertEqual(ui.PT_BR.name(), "pt_BR")
        QLocale.setDefault(ui.PT_BR)
        self.assertEqual(QLocale().name(), "pt_BR")

    def test_reconfiguration_preserves_preferences(self):
        with tempfile.TemporaryDirectory() as folder:
            config = Path(folder) / "config.json"
            config.write_text(json.dumps({
                "assistant_name": "Mark", "voice_name": "Kore", "ui_color": "#00ff00"
            }), encoding="utf-8")
            fake = Mock()
            fake._overlay = None
            with patch.object(ui, "API_FILE", config):
                ui.MainWindow._on_setup_done(fake, "fake-test-key", "windows")
            saved = json.loads(config.read_text(encoding="utf-8"))
            self.assertEqual(saved["assistant_name"], "Mark")
            self.assertEqual(saved["voice_name"], "Kore")
            self.assertEqual(saved["ui_color"], "#00ff00")
            self.assertEqual(saved["language"], "pt-BR")
            self.assertEqual(saved["os_system"], "windows")

    def test_news_keeps_sources_and_translates_heading(self):
        result = web_search._format_news("ciência", [{
            "title": "Nova pesquisa brasileira", "source": "Fonte",
            "url": "https://example.com/news", "snippet": "Resumo da notícia."
        }])
        self.assertIn("Últimas notícias", result)
        self.assertIn("https://example.com/news", result)
        self.assertIn("Nova pesquisa brasileira", result)

    def test_full_window_and_screenshots(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(ui, "API_FILE", Path(folder) / "config.json"):
                window = ui.MainWindow(str(ui.BASE_DIR / "core" / "face_model.obj"))
                window.show()
                self.app.processEvents()
                labels = [label.text() for label in window.findChildren(QLabel)]
                self.assertIn("◈ SISTEMA", labels)
                self.assertIn("▸ COMANDOS", labels)
                self.assertIn("▸ ATIVIDADE", labels)
                self.assertFalse(window._left_panel.isVisible())
                self.assertFalse(window._right_panel.isVisible())
                self.assertFalse(window._content_panel.isVisible())
                self.assertFalse(window._command_bar.isVisible())
                self.assertEqual(window._input.placeholderText(), "Digite um comando ou pergunta…")
                window._apply_state("LISTENING")
                self.assertEqual(window.hud.state, "LISTENING")
                output = ui.BASE_DIR / "validation"
                output.mkdir(exist_ok=True)
                self.assertTrue(window.grab().save(str(output / "pt-br-configuracao.png")))
                if window._overlay:
                    window._overlay.hide()
                window._toggle_drawer(True)
                self.app.processEvents()
                self.assertTrue(window.grab().save(str(output / "pt-br-configuracoes.png")))
                buttons = window._quick_drawer.findChildren(QPushButton)
                for button in buttons:
                    self.assertLessEqual(button.fontMetrics().horizontalAdvance(button.text()),
                                         button.width() - 6, button.text())
                window._toggle_drawer(False)
                window._toggle_controls(True)
                self.app.processEvents()
                self.assertFalse(hasattr(window,'_ctrl_drawer'))
                self.assertFalse(hasattr(window,'_ctrl_btn'))
                self.assertTrue(window._settings_hub.isVisible())
                self.assertTrue(window._settings_hub.grab().save(str(output / "pt-br-perfil.png")))
                window.close()
                window.deleteLater()
                self.app.processEvents()


if __name__ == "__main__":
    unittest.main()
