import unittest
import test_scene
import test_fui_screens


class OperationSixthAudit(unittest.TestCase):
    setUpClass = classmethod(test_scene.SceneTests.setUpClass.__func__)
    setUp = test_fui_screens.AllSettingsPagesTests.setUp
    tearDown = test_fui_screens.AllSettingsPagesTests.tearDown

    def test_manifestation_preserves_pending_operation(self):
        self.window._operation_event('app_control:open', 'pending')
        self.window._show_manifestation({'kind': 'weather', 'temperature': 19})
        self.assertTrue(self.window._execution.isVisible())
        self.assertFalse(self.window._execution_settle.isActive())

    def test_operation_update_preserves_reveal_progress(self):
        self.window._operation_event('app_control:open', 'running')
        panel = self.window._execution
        panel._progress = .65
        panel.proxy.setOpacity(.65)
        self.window._operation_event('app_control:open', 'pending')
        self.assertEqual(panel._progress, .65)
        self.assertEqual(panel.proxy.opacity(), .65)

    def test_reduced_motion_finishes_existing_reveal(self):
        panel = self.window._execution
        panel.show_panel(False)
        panel.show_panel(True)
        self.assertFalse(panel._reveal.isActive())
        self.assertEqual(panel.proxy.opacity(), 1)

    def test_confirmed_success_has_explicit_label(self):
        self.window._execution.record('app_control:open', 'success')
        self.assertIn('CONCLU', self.window._execution.status.text())

    def test_finished_does_not_claim_confirmed_success(self):
        self.window._execution.record('app_control:open', 'finished')
        self.assertIn('ETAPA ENCERRADA', self.window._execution.status.text())

    def test_completed_and_done_have_explicit_labels(self):
        for state in ('completed', 'done'):
            self.window._execution.record('app_control:open', state)
            self.assertIn('CONCLU', self.window._execution.status.text())
