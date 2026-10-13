import unittest
from unittest.mock import Mock
import test_scene
import test_fui_screens
from core.environment_director import EnvironmentDirector


class OperationFifthAudit(unittest.TestCase):
    setUpClass=classmethod(test_scene.SceneTests.setUpClass.__func__)
    setUp=test_fui_screens.AllSettingsPagesTests.setUp
    tearDown=test_fui_screens.AllSettingsPagesTests.tearDown

    def test_pending_operation_remains_visible_without_expiry(self):
        self.window._operation_event('app_control:open','running')
        self.window._operation_event('app_control:open','pending')
        self.assertTrue(self.window._execution.isVisible())
        self.assertFalse(self.window._execution_settle.isActive())

    def test_other_tool_completion_cannot_erase_current_operation(self):
        self.window._operation_event('app_control:open','running')
        self.window._operation_event('weather_report','finished')
        self.assertEqual(self.window._environment.operation,'running')
        self.assertEqual(self.window._environment.operation_name,'app_control')

    def test_finished_operation_emits_completion_cue(self):
        self.window._operation_event('app_control:open','running')
        self.window._operation_event('app_control:open','finished')
        self.assertEqual(self.window._environment.cue['kind'],'resolved')

    def test_unknown_operation_state_does_not_report_resolved(self):
        self.window.hud.semantic_cue=Mock()
        self.window._operation_event('app_control','invalid-state')
        self.window.hud.semantic_cue.assert_not_called()

    def test_powershell_operation_is_visible_in_execution_panel(self):
        self.window._operation_event('powershell_control','running')
        self.assertTrue(self.window._execution.isVisible())
        self.assertIn('PowerShell',self.window._execution.status.text())

    def test_finishing_foreground_restores_other_running_tool(self):
        self.window._operation_event('app_control:open','running')
        self.window._operation_event('file_processor:read','running')
        self.window._operation_event('file_processor:read','finished')
        self.assertEqual(self.window._environment.operation_name,'app_control')
        self.assertEqual(self.window._environment.operation,'running')
        self.assertIn('EM ANDAMENTO',self.window._execution.status.text())
        self.assertFalse(self.window._execution_settle.isActive())

    def test_cancellation_does_not_emit_success_cue(self):
        self.window.hud.semantic_cue=Mock()
        self.window._operation_event('app_control','cancelled')
        self.window.hud.semantic_cue.assert_called_once_with('settle')

    def test_late_completion_after_cancellation_is_ignored_but_new_run_is_allowed(self):
        self.window._operation_event('app_control:open','running')
        self.window._operation_event('app_control:open','cancelled')
        self.window.hud.semantic_cue=Mock()
        self.window._operation_event('app_control:open','finished')
        self.window.hud.semantic_cue.assert_not_called()
        self.window._operation_event('app_control:open','running')
        self.assertEqual(self.window._environment.operation,'running')


class MediaFifthAudit(unittest.TestCase):
    def test_invalid_media_item_cannot_crash_callback(self):
        director=EnvironmentDirector()
        director.media_update({'item':['invalid'],'is_playing':True})
        self.assertIsNone(director.media)

    def test_infinite_duration_is_rejected(self):
        director=EnvironmentDirector()
        director.media_update({'item':{'duration_ms':float('inf')}})
        self.assertIsNone(director.media)

    def test_string_false_is_not_playing(self):
        director=EnvironmentDirector()
        director.media_update({'item':{'duration_ms':1000},'is_playing':'false'})
        self.assertFalse(director.media['playing'])

    def test_nonfinite_audio_level_does_not_light_up_core(self):
        director=EnvironmentDirector()
        self.assertEqual(director.payload(level=float('nan'))['level'],0)
