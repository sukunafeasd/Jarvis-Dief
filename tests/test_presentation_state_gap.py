import ast
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from core.presentation_clock import PresentationClock


class PresentationStateGapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Test the real UI state handler without starting audio, Qt or accounts.
        path=Path(__file__).resolve().parents[1]/'ui.py'
        tree=ast.parse(path.read_text(encoding='utf-8'))
        window=next(node for node in tree.body if isinstance(node,ast.ClassDef) and node.name=='MainWindow')
        method=next(node for node in window.body if isinstance(node,ast.FunctionDef) and node.name=='_apply_state')
        namespace={'_read_full_config':lambda:{'presentation_hold':15}}
        exec(compile(ast.Module(body=[method],type_ignores=[]),str(path),'exec'),namespace)
        cls.apply_state=staticmethod(namespace['_apply_state'])

    def window(self):
        clock=PresentationClock();clock.advance(.5)
        clock.enqueue('Proximo trecho',at=1)
        return SimpleNamespace(_resting=False,hud=SimpleNamespace(state='SPEAKING',speaking=True),
            _ultron_clock=PresentationClock(),_presentation_clock=clock,
            _visual_scene=Mock(),_ui_sounds=Mock(),_settle_timer=Mock(),
            _content_spatial=Mock(),_pinned=False,_refresh_lock=None,_set_news_phase=Mock(),
            _presentation={'narration_active':True,'audio_started':True,'completed':False,'model':{}})

    def assert_unfinished(self,window):
        self.assertTrue(window._presentation['narration_active'])
        self.assertTrue(window._presentation['audio_started'])
        self.assertFalse(window._presentation['completed'])
        window._content_spatial.page().runJavaScript.assert_not_called()
        window._visual_scene.finish.assert_not_called()
        window._settle_timer.start.assert_not_called()
        window._set_news_phase.assert_not_called()

    def assert_finished(self,window):
        self.assertFalse(window._presentation['narration_active'])
        self.assertFalse(window._presentation['audio_started'])
        self.assertTrue(window._presentation['completed'])
        window._content_spatial.page().runJavaScript.assert_called_once_with(
            'window.finishPresentation && window.finishPresentation()')
        window._visual_scene.finish.assert_called_once()
        window._settle_timer.start.assert_called_once_with(15000)
        window._set_news_phase.assert_called_once_with('settled')

    def test_network_gap_keeps_visuals_unfinished_until_listening(self):
        window=self.window()
        pending=list(window._presentation_clock.pending)
        self.apply_state(window,'THINKING')
        self.assertFalse(window.hud.speaking)
        self.assertEqual(window.hud.state,'THINKING')
        self.assert_unfinished(window)
        self.assertEqual(window._presentation_clock.elapsed,.5)
        self.assertEqual(list(window._presentation_clock.pending),pending)
        self.apply_state(window,'THINKING')
        self.assert_unfinished(window)
        self.apply_state(window,'LISTENING')
        self.assert_finished(window)
        self.apply_state(window,'LISTENING')
        self.assert_finished(window)

    def test_next_audio_segment_during_gap_continues_same_presentation(self):
        window=self.window();presentation=window._presentation
        self.apply_state(window,'THINKING')
        self.apply_state(window,'SPEAKING')
        self.assertIs(window._presentation,presentation)
        self.assertTrue(window.hud.speaking)
        self.assert_unfinished(window)
        window._settle_timer.stop.assert_called_once()
        window._presentation_clock.advance(.5)
        self.assertEqual(window._presentation_clock.elapsed,1)
        self.apply_state(window,'THINKING')
        self.assert_unfinished(window)
        self.apply_state(window,'LISTENING')
        self.assert_finished(window)

    def test_direct_end_still_finishes_and_intermediate_news_does_not_settle(self):
        window=self.window();self.apply_state(window,'LISTENING')
        self.assert_finished(window)
        window=self.window();window._presentation['model']['newsLast']=False
        self.apply_state(window,'THINKING');self.assert_unfinished(window)
        self.apply_state(window,'LISTENING')
        self.assertTrue(window._presentation['narration_active'])
        self.assertFalse(window._presentation['audio_started'])
        self.assertFalse(window._presentation['completed'])
        window._content_spatial.page().runJavaScript.assert_called_once()
        window._visual_scene.finish.assert_called_once()
        window._settle_timer.start.assert_not_called()

    def test_waiting_for_first_audio_or_inactive_narration_does_not_finish(self):
        for key in ('audio_started','narration_active'):
            with self.subTest(key=key):
                window=self.window();window._presentation[key]=False
                window.hud.state='THINKING';window.hud.speaking=False
                self.apply_state(window,'LISTENING')
                self.assertFalse(window._presentation['completed'])
                window._content_spatial.page().runJavaScript.assert_not_called()
                window._settle_timer.start.assert_not_called()

    def test_visual_scene_alone_finishes_after_gap(self):
        window=self.window();window._presentation=None
        self.apply_state(window,'THINKING')
        window._visual_scene.finish.assert_not_called()
        self.apply_state(window,'LISTENING')
        window._visual_scene.finish.assert_called_once()

    def test_pinned_and_refresh_locked_presentations_do_not_start_dismissal(self):
        for key,value in (('_pinned',True),('_refresh_lock','refresh')):
            with self.subTest(key=key):
                window=self.window();setattr(window,key,value)
                self.apply_state(window,'THINKING');self.apply_state(window,'LISTENING')
                self.assertTrue(window._presentation['completed'])
                window._settle_timer.start.assert_not_called()


if __name__=='__main__':unittest.main()
