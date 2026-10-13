import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from PyQt6.QtWidgets import QApplication
import ui
from core.action_loader import discover_actions


class SceneTests(unittest.TestCase):
    def test_information_and_pins_have_no_close_buttons(self):
        from PyQt6.QtWidgets import QPushButton
        self.window._show_manifestation({'kind':'weather','temperature':19,'title':'CLIMA'})
        self.assertEqual(self.window._content_panel.findChildren(QPushButton), [])
        self.command('pin')
        self.assertEqual(self.window._pin_previews['weather']['widget'].findChildren(QPushButton), [])

    def test_audio_clock_advances_without_any_information_visible(self):
        self.window._advance_presentation(.4)
        self.window._show_manifestation({'kind':'tasks','count':1,'title':'TAREFAS','items':[]})
        self.assertAlmostEqual(self.window._presentation_clock.elapsed,.4)

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.mock_config = patch.object(ui, "API_FILE", Path(self.folder.name) / "config.json")
        self.mock_config.start()
        self.window = ui.MainWindow(str(ui.BASE_DIR / "core/face_model.obj"))
        self.window.show()
        self.app.processEvents()
        self.window._overlay.hide()

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()
        self.mock_config.stop()
        self.folder.cleanup()

    def command(self, action, value="", setting=""):
        request = {"action": action, "value": value, "setting": setting, "done": threading.Event()}
        self.window._apply_interface_request(request)
        self.assertTrue(request["done"].is_set())
        return request["result"]

    def test_idle_is_empty(self):
        self.assertFalse(self.window._left_panel.isVisible())
        self.assertFalse(self.window._right_panel.isVisible())
        self.assertFalse(self.window._content_panel.isVisible())
        self.assertFalse(self.window._metric_tmr.isActive())
        self.window.grab().save(str(ui.BASE_DIR / "validation/scene-idle.png"))

    def test_news_focus_clear_and_return(self):
        self.window._show_content("NOTÍCIAS — exemplo de teste", "1. Pesquisa brasileira\nDetalhes da primeira notícia.\n\n2. Segundo assunto\nOutra fonte.")
        self.app.processEvents()
        self.assertTrue(self.window._content_panel.isVisible())
        self.assertGreater(self.window._content_panel.x(), self.window.hud.x())
        self.assertEqual(len(self.window._presentation["items"]), 2)
        self.assertTrue(self.command("focus", "2")["ok"])
        self.assertEqual(self.window._presentation["focus"], 1)
        self.assertFalse(self.command("focus", "999")["ok"])
        self.window.grab().save(str(ui.BASE_DIR / "validation/scene-news.png"))
        self.assertTrue(self.command("clear")["ok"])
        self.assertFalse(self.window._content_panel.isVisible())
        self.assertTrue(self.command("return")["ok"])
        self.assertTrue(self.window._content_panel.isVisible())
        self.assertEqual(self.window._presentation["focus"], 1)

    def test_color_does_not_recolor_background_or_text(self):
        fixed = {name: getattr(ui.C, name) for name in ("BG", "TEXT", "WHITE", "PANEL", "BORDER")}
        old = ui.current_palette()
        try:
            self.assertTrue(self.command("color", "#ff5577")["ok"])
            for name, color in fixed.items():
                self.assertEqual(getattr(ui.C, name), color)
            self.assertFalse(self.command("color", "javascript:alert(1)")["ok"])
        finally:
            for name, color in old.items():
                setattr(ui.C, name, color)

    def test_pin_has_visible_restore_control(self):
        self.window._show_manifestation({'kind':'system','title':'SISTEMA','cpu_percent':15})
        self.assertTrue(self.command("pin")["ok"])
        self.assertTrue(self.window._pin_previews['system']['widget'].isVisible())
        self.assertIn('15%',self.window._pin_previews['system']['label'].text())
        self.assertFalse(self.window._content_panel.isVisible())
        self.window._restore_pin()
        self.assertTrue(self.window._content_panel.isVisible())
        self.assertTrue(self.command("unpin")["ok"])
        self.assertFalse(self.window._pin_button.isVisible())

    def test_weather_and_calendar_pins_keep_data_and_separate_bounds(self):
        self.window._show_manifestation({'kind':'weather','title':'CLIMA','temperature':19,'condition':'Chuva','city':'Porto Alegre'})
        self.assertTrue(self.command('pin')['ok'])
        self.window._show_manifestation({'kind':'calendar','title':'AGENDA','items':[{'id':4,'title':'Reunião','due':'2026-10-12'}]})
        self.assertTrue(self.command('pin')['ok'])
        weather=self.window._pin_previews['weather']
        calendar=self.window._pin_previews['calendar']
        self.assertIn('19°',weather['label'].text())
        self.assertFalse(weather['widget'].geometry().intersects(calendar['widget'].geometry()))
        self.assertLess(weather['widget'].x(),calendar['widget'].x())
        self.window._expand_pin('weather')
        self.assertEqual(self.window._presentation['model']['temperature'],19)
        self.assertTrue(self.command('unpin','calendar')['ok'])
        self.assertIn('weather',self.window._pin_previews)

    def test_communications_are_above_lowered_avatar(self):
        self.window._show_manifestation({'kind':'gmail','title':'GMAIL','items':[{'title':'Assunto','detail':'Remetente'}]})
        self.window._layout_scene(False)
        self.assertLess(self.window._content_panel.y(),self.window._center_split.y())
        self.assertGreater(self.window._content_panel.width(),self.window._scene_stage.width()*.75)

    def test_projection_is_short_and_never_intercepts_input(self):
        from PyQt6.QtCore import Qt
        from PyQt6.QtTest import QTest
        self.window._show_manifestation({'kind':'weather','title':'CLIMA','temperature':19,'code':61})
        trace=self.window._projection_trace
        self.assertTrue(trace.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents))
        self.assertTrue(trace.timer.isActive())
        QTest.qWait(740)
        self.assertFalse(trace.timer.isActive())
        self.assertFalse(trace.isVisible())
        self.command('pin')
        self.assertTrue(trace.timer.isActive())
        self.window._cancel_presentation()
        self.assertFalse(trace.timer.isActive())

    def test_reduced_motion_never_starts_projection_trace(self):
        with patch.object(ui,'_read_full_config',return_value={'reduce_motion':True}):
            self.window._show_manifestation({'kind':'tasks','title':'TAREFAS','count':1,'items':[{'title':'Teste'}]})
            self.assertFalse(self.window._projection_trace.timer.isActive())
            self.command('pin')
            self.assertFalse(self.window._projection_trace.timer.isActive())

    def test_history_is_bounded(self):
        for i in range(30):
            self.window._show_content(str(i), "Dados de teste")
        self.assertLessEqual(len(self.window._presentation_history), 8)
        self.assertTrue(self.command("inspect")["ok"])
        self.assertFalse(self.command("open", "unknown")["ok"])
        self.assertFalse(self.command("setting", "UnknownVoice", "voice")["ok"])

    def test_interface_tool_is_discovered(self):
        registry = discover_actions(ui.BASE_DIR / "actions", logger=lambda _: None)
        self.assertTrue(registry.has("interface_control"))


if __name__ == "__main__":
    unittest.main()
