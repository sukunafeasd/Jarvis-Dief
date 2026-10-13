import unittest
from unittest.mock import Mock
import test_scene
import test_fui_screens


class SecondAuditTests(unittest.TestCase):
    setUpClass=classmethod(test_scene.SceneTests.setUpClass.__func__)
    setUp=test_fui_screens.AllSettingsPagesTests.setUp
    tearDown=test_fui_screens.AllSettingsPagesTests.tearDown
    command=test_scene.SceneTests.command

    def test_move_pin_swaps_occupied_corner_and_reports_actual_slots(self):
        for kind in ('weather','calendar'):
            self.window._show_manifestation({'kind':kind,'title':kind,'items':[]})
            self.command('pin')
        self.assertTrue(self.command('move_pin','calendar','bottom_left')['ok'])
        self.window._layout_scene(False)
        self.assertEqual(self.window._pin_previews['calendar']['widget'].x(),12)
        self.assertGreater(self.window._pin_previews['weather']['widget'].x(),12)
        self.assertEqual(self.window._pin_previews['calendar'].get('slot'),0)
        self.assertEqual(self.window._pin_previews['weather'].get('slot'),1)

    def test_return_restores_previous_weather_period_with_same_title(self):
        self.window._show_manifestation({'kind':'weather','title':'CLIMA','period':'today','temperature':19})
        self.window._show_manifestation({'kind':'weather','title':'CLIMA','period':'tomorrow','temperature':25})
        self.assertTrue(self.command('return')['ok'])
        self.assertEqual(self.window._presentation['model']['period'],'today')

    def test_refresh_completed_scene_does_not_wait_for_new_speech(self):
        view=Mock(failed=False,_loaded=True)
        self.window._content_spatial=view
        self.window._show_manifestation({'kind':'gmail','title':'GMAIL','narrationDriven':True,'items':[{'title':'Teste'}]})
        self.window._apply_state('SPEAKING');self.window._advance_presentation(.1);self.window._apply_state('LISTENING')
        self.window._render_presentation()
        self.assertFalse(view.sync.call_args.args[0]['narrationDriven'])
        self.window._content_spatial=None

    def test_photo_request_terminal_stays_visible_with_information_on_small_window(self):
        self.window.resize(820,580);self.app.processEvents()
        self.command('request_image')
        self.window._show_manifestation({'kind':'weather','title':'CLIMA','temperature':19})
        self.window._layout_scene(False)
        self.assertTrue(self.window._terminal.isVisible())
        self.assertFalse(self.window._terminal.geometry().intersects(self.window._content_panel.geometry()))

    def test_four_pins_terminal_and_information_do_not_overlap(self):
        self.window.resize(820,580);self.app.processEvents()
        for kind in ('weather','calendar','tasks','system'):
            self.window._show_manifestation({'kind':kind,'title':kind,'items':[]})
            self.command('pin')
        self.command('request_image')
        self.window._show_manifestation({'kind':'gmail','title':'GMAIL','items':[{'title':'Teste'}]})
        self.window._layout_scene(False)
        self.assertTrue(self.window._terminal.isVisible())
        self.assertFalse(self.window._terminal.geometry().intersects(self.window._content_panel.geometry()))

    def test_execution_panel_internal_surface_fits_small_height(self):
        panel=self.window._execution
        panel.resize(300,180);panel.show();self.app.processEvents();panel._progress=1;panel._fit()
        rect=panel.mapFromScene(panel.proxy.sceneBoundingRect()).boundingRect()
        self.assertTrue(panel.viewport().rect().contains(rect),str(rect))

    def test_clear_resets_planet_and_environment_mode(self):
        self.command('environment','Saturno')
        self.assertTrue(self.command('clear')['ok'])
        self.assertIsNone(self.window._environment.planet)
        self.assertIsNone(self.window._environment.override)

    def test_entrance_waits_for_primary_hologram_to_be_ready(self):
        self.window.hud.hud_style='core'
        self.window._space_view=Mock(failed=False,_ready=True)
        self.window.hud._spatial_core=Mock(failed=False,_ready=False)
        self.window._start_environment()
        self.assertFalse(self.window._environment.started)
        self.window.hud._spatial_core._ready=True
        self.window._start_environment()
        self.assertTrue(self.window._environment.started)
        self.window.hud._spatial_core=None;self.window._space_view=None

    def test_hologram_loaded_without_presentation_cannot_crash_window(self):
        self.window._presentation=None
        self.window._content_spatial=Mock(failed=False,_loaded=True)
        self.window._render_presentation()
        self.window._content_spatial.sync.assert_not_called()
        self.window._content_spatial=None

    def test_environment_tool_returns_effective_mode_not_only_requested_mode(self):
        import json
        from actions.interface_control import interface_control
        player=Mock()
        player.control_interface.return_value={'ok':True,'screen':{'environment':{'requested_mode':'exploration','resolved_mode':'focus','renderer':'loading','planet':'saturn'}}}
        result=json.loads(interface_control({'action':'environment','value':'Saturno'},player))
        self.assertEqual(result['environment_result']['resolved_mode'],'focus')
        self.assertEqual(result['environment_result']['renderer'],'loading')

    def test_environment_tool_never_turns_failure_into_success(self):
        import json
        from actions.interface_control import interface_control
        player=Mock();player.control_interface.return_value={'ok':False,'error':'Modo invalido'}
        result=json.loads(interface_control({'action':'environment','value':'invalid'},player))
        self.assertFalse(result['ok']);self.assertNotIn('environment_result',result)
