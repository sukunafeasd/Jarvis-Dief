import unittest
from unittest.mock import MagicMock
import test_fui_screens
import test_scene


class EnvironmentUITests(unittest.TestCase):
    setUpClass = classmethod(test_scene.SceneTests.setUpClass.__func__)
    setUp = test_fui_screens.AllSettingsPagesTests.setUp
    tearDown = test_fui_screens.AllSettingsPagesTests.tearDown
    command = test_scene.SceneTests.command

    def test_exploration_moves_core_but_not_clock_and_preserves_cards(self):
        clock = self.window._clock_lbl.geometry()
        self.assertTrue(self.command('environment','Saturno')['ok'])
        self.window._layout_scene(False)
        self.assertGreater(self.window._center_split.x(), 0)
        self.assertEqual(clock, self.window._clock_lbl.geometry())
        self.window._show_manifestation({'kind':'weather','temperature':19,'title':'CLIMA'})
        self.window._layout_scene(False)
        bounds = self.window._content_panel.geometry()
        self.assertTrue(self.command('environment','foco')['ok'])
        self.window._layout_scene(False)
        self.assertEqual(bounds,self.window._content_panel.geometry())
        self.assertFalse(self.command('environment','raw GLSL')['ok'])

    def test_shared_payload_reading_rest_and_cancellation(self):
        self.window._on_setup_done('synthetic-environment-test','windows')
        self.window._ensure_space()
        space = MagicMock();space.failed=False
        self.window._space_view = space
        core = MagicMock();core.failed=False
        self.window.hud._spatial_core = core
        self.window._start_environment()
        self.window._sync_environment('speaking',.3)
        background = space.sync.call_args.args[0]
        hologram = core.sync_environment.call_args.args[0]
        self.assertEqual(background,hologram)
        self.assertEqual(background['phase'],'speaking')
        self.assertIsNone(background['entrance']['cancelAt'])
        self.window._show_manifestation({'kind':'gmail','title':'MENSAGENS','items':[]})
        self.window._sync_environment('speaking')
        self.assertEqual(space.sync.call_args.args[0]['mode'],'focus')
        self.window._cancel_presentation()
        self.assertEqual(self.window._environment.cue['kind'],'settle')
        self.window._show_manifestation({'kind':'weather','temperature':19,'title':'CLIMA'})
        self.window._environment.operation_event('running','gmail_control')
        self.window._sync_environment('executing')
        self.assertIsNone(space.sync.call_args.args[0]['target'])
        self.window._environment.operation_event('running','weather_report')
        self.window._sync_environment('executing')
        self.assertIsNotNone(space.sync.call_args.args[0]['target'])
        self.window.hud._spatial_core=None
        self.window._space_view=None

    def test_environment_is_available_to_assistant(self):
        from actions.interface_control import TOOL
        self.assertIn('environment',TOOL['parameters']['properties']['action']['enum'])
        snapshot = self.window.interface_snapshot()['environment']
        self.assertIn('saturno',snapshot['planets'])
        self.assertEqual(snapshot['requested_mode'],'auto')
        with unittest.mock.patch.object(self.window,'_sync_environment') as sync:
            self.window.hud._core_sync_at=-1
            self.window.hud._sync_spatial_core(1)
            sync.assert_called_once()
