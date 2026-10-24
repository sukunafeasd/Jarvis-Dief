import json
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch,Mock
from types import SimpleNamespace
from contextlib import ExitStack
from PyQt6.QtWidgets import QApplication
from PyQt6.QtTest import QTest
from core.environment_director import EnvironmentDirector
from core.opening_veil import OpeningVeil
import ui


class LocalOpeningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])

    def setUp(self):
        self.folder=tempfile.TemporaryDirectory()
        self.config=Path(self.folder.name)/'profile.json'
        self.config.write_text(json.dumps({'hud_style':'core'}))
        self.stack=ExitStack()
        self.stack.enter_context(patch.object(ui,'API_FILE',self.config))
        self.stack.enter_context(patch('memory.config_manager.CONFIG_FILE',self.config))
        self.stack.enter_context(patch.object(ui.MainWindow,'_verify_saved_connections'))
        self.window=ui.MainWindow(str(ui.BASE_DIR/'core/face_model.obj'))
        self.window.show();QTest.qWait(20)

    def tearDown(self):
        self.window.close();self.window.deleteLater();self.app.processEvents()
        self.stack.close();self.folder.cleanup()

    def test_setup_suppresses_hologram_and_does_not_consume_entrance(self):
        self.assertTrue(self.window._overlay.isVisible())
        self.assertFalse(self.window._center_split.isVisible())
        self.window._start_environment()
        self.assertFalse(self.window._environment.started)
        self.assertIsNone(self.window._environment.entrance)

    def test_setup_completion_starts_entrance_once(self):
        self.window._on_setup_done('synthetic-local-test','windows')
        self.window._ensure_space()
        self.assertTrue(self.window._center_split.isVisible())
        self.assertIsNone(self.window._overlay)
        self.assertTrue(self.window._environment.started)
        first=dict(self.window._environment.entrance)
        self.window._prepare_initial_scene();self.window._start_environment()
        self.assertEqual(first,self.window._environment.entrance)

    def test_first_setup_creates_private_parent_directory(self):
        target=Path(self.folder.name)/'fresh/data/profile.json'
        with patch.object(ui,'API_FILE',target):
            self.window._on_setup_done('synthetic-local-test','windows')
        self.assertEqual(json.loads(target.read_text())['os_system'],'windows')
        self.assertIsNone(self.window._overlay)

    def test_setup_write_failure_remains_visible_and_does_not_start_scene(self):
        with patch('core.local_data.atomic_write',side_effect=OSError('synthetic')):
            self.window._on_setup_done('synthetic-local-test','windows')
        self.assertTrue(self.window._overlay.isVisible())
        self.assertTrue(self.window._overlay.save_status.text())
        self.assertFalse(self.window._center_split.isVisible())

    def test_face_mode_waits_for_background_initialization(self):
        self.window._on_setup_done('synthetic-local-test','windows')
        self.window.hud.hud_style='face'
        self.window._start_environment()
        self.assertFalse(self.window._environment.started)
        self.window._ensure_space()
        self.assertTrue(self.window._environment.started)

    def test_veil_tracks_stage_after_fullscreen_and_restore(self):
        self.window._opening_veil=OpeningVeil(self.window._scene_stage)
        for width,height in ((1920,1080),(1200,800),(900,600)):
            self.window.resize(width,height);QTest.qWait(20)
            self.window._layout_scene()
            self.assertEqual(self.window._opening_veil.geometry(),self.window._scene_stage.rect())

    def test_visible_veil_still_resizes_during_fade(self):
        veil=OpeningVeil(self.window._scene_stage)
        self.window._opening_veil=veil
        veil.setGeometry(self.window._scene_stage.rect());veil.show();veil.release()
        self.window.resize(1300,820);self.app.processEvents();self.window._layout_scene()
        self.assertTrue(veil.released)
        self.assertEqual(veil.geometry(),self.window._scene_stage.rect())

    def test_connection_does_not_resize_core_during_camera_entrance(self):
        self.window._on_setup_done('synthetic-local-test','windows')
        self.window._ensure_space()
        before=self.window._center_split.geometry()
        self.window._connection_changed(True,'Test')
        self.assertEqual(before,self.window._center_split.geometry())

    def test_reconfiguration_hides_existing_core(self):
        self.window._on_setup_done('synthetic-local-test','windows')
        self.window._show_setup();self.window._layout_scene()
        self.assertFalse(self.window._center_split.isVisible())
        self.assertTrue(self.window._overlay.isVisible())

    def test_delay_preserves_full_camera_travel_and_reduced_motion(self):
        director=EnvironmentDirector(lambda:1000)
        director.start(delay=400)
        self.assertEqual(director.entrance['at'],1400)
        reduced=EnvironmentDirector(lambda:1000);reduced.start(True,delay=400)
        self.assertEqual(reduced.entrance['at'],1000)
        self.assertEqual(reduced.entrance['duration'],0)

    def test_camera_waits_for_preparation_cover_to_leave(self):
        veil=OpeningVeil(self.window._scene_stage)
        self.window._opening_veil=veil
        veil.setGeometry(self.window._scene_stage.rect());veil.show()
        self.window._on_setup_done('synthetic-local-test','windows')
        self.window._ensure_space()
        self.assertTrue(veil.released)
        self.assertFalse(self.window._environment.started)
        QTest.qWait(350)
        self.assertFalse(veil.isVisible())
        self.assertTrue(self.window._environment.started)

    def test_render_failure_cancels_cover_release_instead_of_exposing_fallback(self):
        veil=OpeningVeil(self.window._scene_stage)
        veil.setGeometry(self.window._scene_stage.rect());veil.show();veil.release()
        veil.fail();QTest.qWait(350)
        self.assertTrue(veil.isVisible());self.assertFalse(veil.released)
        self.assertFalse(veil.timer.isActive())

    def test_webgl_failure_uses_native_scene_instead_of_error_cover(self):
        space=SimpleNamespace(hide=Mock())
        core=SimpleNamespace(hide=Mock())
        owner=SimpleNamespace(_scene_fallback_active=False,_space_view=space,
            hud=SimpleNamespace(_spatial_core=core),_log=Mock())
        ui.MainWindow._activate_scene_fallback(owner)
        self.assertTrue(owner._scene_fallback_active)
        space.hide.assert_called_once()
        core.hide.assert_called_once()
        owner._log.append_log.assert_called_once()

    def test_failed_preparation_never_emits_ready_even_with_stale_ready_flag(self):
        from core.spatial_view import SpatialCoreView
        owner=SimpleNamespace(_alive=lambda:True,failed=False,_ready=False,_created=0,
            _fail=Mock(),ready=Mock())
        SpatialCoreView._health_result(owner,{'ready':'true','error':'webgl'})
        owner._fail.assert_called_once();owner.ready.emit.assert_not_called()
        self.assertFalse(owner._ready)
