"""Offline shutdown and suspension regressions, with no devices or providers."""
import threading
import unittest
from core.bounded_work import BoundedWork
from tests import test_connection_sound_lifecycle as sound_tests


class PoolShutdownTests(unittest.TestCase):
    def test_cancel_callback_can_reenter_pool_without_deadlocking_close(self):
        pool=BoundedWork(workers=1,capacity=2,name='Round6')
        running=threading.Event();release=threading.Event();notified=threading.Event()
        def work():running.set();release.wait(3);return 'finished'
        first=pool.submit(work)
        self.assertTrue(running.wait(1))
        queued=pool.submit(lambda:self.fail('Queued work started after close'))
        def cancelled(future):
            try:pool.submit(lambda:None)
            except RuntimeError:notified.set()
        queued.add_done_callback(cancelled)
        closer=threading.Thread(target=pool.close,daemon=True)
        try:
            closer.start();closer.join(timeout=1)
            self.assertFalse(closer.is_alive(),'Cancellation callback deadlocked the pool lock')
            self.assertTrue(notified.wait(1));self.assertTrue(queued.cancelled())
        finally:release.set()
        self.assertEqual(first.result(timeout=2),'finished')
        pool.close()
        with self.assertRaises(RuntimeError):pool.submit(lambda:None)


class SoundShutdownTests(unittest.TestCase):
    setUpClass=classmethod(sound_tests.SoundLifecycleTests.setUpClass.__func__)
    director=sound_tests.SoundLifecycleTests.director

    def test_hidden_panel_blocks_late_cues_until_show(self):
        value=self.director();value.scene(visible=True)
        value.stop()
        self.assertFalse(value.ambient_timer.isActive())
        for effect in value.effects.values():effect.reset_mock()
        self.assertFalse(value.play('click'))
        value.voice(False);value.set_muted(False);value.media({'is_playing':False})
        for effect in value.effects.values():effect.play.assert_not_called()
        value.scene(visible=True)
        self.assertTrue(value.ambient_timer.isActive())
        self.assertTrue(value.play('click'))

    def test_close_is_terminal_even_when_late_scene_or_voice_events_arrive(self):
        value=self.director();value.scene(visible=True);value.close()
        for effect in value.effects.values():effect.reset_mock()
        value.scene(visible=True);value.voice(False);value.set_muted(False)
        value.media({'is_playing':False});value.ambient_timer.timeout.emit()
        self.assertFalse(value.play('refresh-complete'))
        self.assertFalse(value.ambient_timer.isActive())
        for effect in value.effects.values():effect.play.assert_not_called()

    def test_minimizing_stops_active_cues_and_timer_then_resumes_ambience(self):
        value=self.director();value.scene(visible=True);value.play('click')
        for effect in value.effects.values():effect.reset_mock()
        value.scene(visible=False)
        for effect in value.effects.values():effect.stop.assert_called()
        self.assertFalse(value.ambient_timer.isActive())
        self.assertFalse(value.play('click'))
        value.scene(visible=True)
        value.effects['ambient'].play.assert_called_once()
