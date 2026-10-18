"""Isolated offscreen scene lifecycle regressions; no host or providers."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from PyQt6.QtWidgets import QApplication, QWidget

from core.presentation_clock import PresentationClock
from core.visual_scene import VisualSceneController


class VisualModeResumeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.config = patch.dict(sys.modules, {'ui': SimpleNamespace(_read_full_config=lambda: {})})
        self.config.start()
        self.addCleanup(self.config.stop)
        self.window = QWidget()
        self.window.resize(1200, 800)
        self.window._scene_stage = QWidget(self.window)
        self.window._scene_stage.setGeometry(0, 0, 1200, 800)
        self.window._scene_stage.show()
        self.window._center_split = QWidget(self.window)
        self.window._center_split.setGeometry(420, 220, 350, 380)
        for name in ('_content_panel', '_terminal', '_execution', '_command_bar'):
            setattr(self.window, name, Mock(isVisible=lambda: False))
        self.window._pin_previews = {}
        self.window._resting = False
        self.window._forge_controller = None
        self.window._ultron_payload = None
        self.window._presentation_clock = PresentationClock()
        self.window.show()
        self.app.processEvents()
        self.scene = VisualSceneController(self.window)
        self.scene.apply({'action': 'compose', 'elements': [{
            'id': 'message', 'text': 'Uma mensagem importante para continuar lendo.', 'pinned': True}]})

    def tearDown(self):
        self.scene.clear_all()
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()

    def enter_mode(self, mode):
        if mode == 'forge':
            self.window._forge_controller = SimpleNamespace(active=True)
        else:
            self.window._ultron_payload = {'state': {'phase': mode}}
        self.scene.layer.hide()

    def leave_mode(self):
        self.window._forge_controller = None
        self.window._ultron_payload = {'state': {'phase': 'idle'}}

    def finish_writing(self):
        for _ in range(30):
            self.scene.tick()
        item = self.scene.items['message']
        self.assertEqual(item['chars'], len(item['text']))
        self.assertFalse(self.scene.timer.isActive())

    def test_modes_keep_native_and_webgl_scene_hidden_on_reflow_and_expiry(self):
        self.scene.view = Mock(failed=False)
        for mode in ('forge', 'scanning', 'active'):
            with self.subTest(mode=mode):
                self.enter_mode(mode)
                before = self.scene.items['message']['chars']
                self.scene.reflow(force=True)
                self.scene.tick()
                self.scene.expire()
                self.assertFalse(self.scene.layer.isVisible())
                self.assertFalse(self.scene.labels['message'].isVisible())
                self.assertFalse(self.scene.view.sync.call_args.args[0]['visible'])
                self.assertFalse(self.scene.snapshot()['elements'][0]['visible'])
                self.assertEqual(self.scene.items['message']['chars'], before)
                self.assertFalse(self.scene.timer.isActive())
                self.leave_mode()

    def test_return_from_mode_restarts_only_unfinished_writing(self):
        for mode in ('forge', 'active'):
            with self.subTest(mode=mode):
                self.enter_mode(mode)
                self.scene.tick()
                self.assertFalse(self.scene.timer.isActive())
                self.leave_mode()
                self.scene.reflow()
                self.assertTrue(self.scene.timer.isActive())
        self.finish_writing()
        self.scene.reflow()
        self.assertFalse(self.scene.timer.isActive())

    def test_hidden_window_resumes_partial_text_on_reflow(self):
        self.window.hide()
        self.scene.tick()
        before = self.scene.items['message']['chars']
        self.assertFalse(self.scene.timer.isActive())
        self.window.show()
        self.scene.reflow()
        self.assertEqual(self.scene.items['message']['chars'], before)
        self.assertTrue(self.scene.timer.isActive())
        self.finish_writing()

    def test_minimized_window_resumes_partial_text_on_reflow(self):
        self.window.showMinimized()
        self.app.processEvents()
        self.scene.tick()
        self.assertFalse(self.scene.timer.isActive())
        self.window.showNormal()
        self.app.processEvents()
        self.scene.reflow()
        self.assertTrue(self.scene.timer.isActive())
        self.finish_writing()

    def test_reflow_never_resumes_cancelled_or_finished_clock(self):
        for state in ('cancelled', 'finished', 'clock_cancelled'):
            with self.subTest(state=state):
                self.scene.cancelled = False
                self.scene.clock.reset()
                if state == 'cancelled':
                    self.scene.cancel()
                elif state == 'finished':
                    self.scene.clock.finish()
                else:
                    self.scene.clock.cancel()
                before = self.scene.items['message']['chars']
                self.scene.layer.hide()
                self.scene.reflow()
                self.scene.tick()
                self.assertFalse(self.scene.timer.isActive())
                self.assertEqual(self.scene.items['message']['chars'], before)
                self.assertEqual(self.scene.clock.finished, state == 'finished')
                self.assertEqual(self.scene.clock.cancelled, state != 'finished')

    def test_hidden_pending_cue_pauses_timer_and_restarts_when_visible(self):
        self.scene.apply({'action': 'compose', 'elements': [{
            'id': 'message', 'text': 'Texto ligado a fala.', 'cue': 'mensagem', 'pinned': True}]})
        self.window.hide()
        self.scene.tick()
        self.assertFalse(self.scene.timer.isActive())
        self.window.show()
        self.scene.reflow()
        self.assertTrue(self.scene.timer.isActive())
        self.assertFalse(self.scene.items['message']['revealed'])


if __name__ == '__main__':
    unittest.main()
