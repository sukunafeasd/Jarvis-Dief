import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import builtins
import math
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication,QLabel,QPushButton
from core.fui_geometry import core_lines,chamfer_points
from core.hud_glass import HudGlassFrame
from core.settings_style import SettingsSurface
from core.elevation_dialog import ElevationDialog
import test_scene

BASE=Path(__file__).resolve().parents[1]
OUTPUT=BASE/'validation/all-screens'


class FuiScreenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])
        cls.app.setStyle('Fusion');OUTPUT.mkdir(parents=True,exist_ok=True)

    def test_geometry_is_original_bounded_and_moves(self):
        first,vertices=core_lines(0);second,_=core_lines(5)
        self.assertNotEqual(first,second);self.assertEqual(len(first),len(second))
        self.assertLess(len(first),1100);self.assertEqual(len(vertices),104)
        for a,b,_ in second:
            self.assertTrue(all(math.isfinite(v) and abs(v)<1.15 for v in (*a,*b)))
        self.assertEqual(len(chamfer_points(660,440)),16)

    def test_core_painter_finishes_without_callback_exceptions(self):
        from PyQt6.QtGui import QPixmap,QPainter,QColor
        from PyQt6.QtCore import QPointF
        from core.fui_paint import paint_core
        for seconds in (0,1,7):
            image=QPixmap(360,360);image.fill(QColor('#050d12'))
            painter=QPainter(image)
            try:paint_core(painter,QPointF(180,180),100,seconds)
            finally:painter.end()
            self.assertFalse(image.isNull())

    def test_admin_material_is_cached_animated_and_suspends_minimized(self):
        admin=ElevationDialog(lambda:False);admin.resize(720,620);admin.show();QTest.qWait(80)
        first=admin.grab().toImage();cache=admin._plate.cacheKey()
        QTest.qWait(150);second=admin.grab().toImage()
        self.assertNotEqual(first,second);self.assertEqual(cache,admin._plate.cacheKey())
        for width,height in ((580,560),(960,720)):
            admin.resize(width,height);QTest.qWait(50)
            for button in admin.findChildren(QPushButton):
                self.assertTrue(admin.rect().contains(button.geometry()))
            admin.grab().save(str(OUTPUT/f'admin-{width}.png'))
        admin.showMinimized();QTest.qWait(30);self.assertFalse(admin.timer.isActive())
        admin.showNormal();QTest.qWait(30);self.assertTrue(admin.timer.isActive())
        admin.close();self.assertFalse(admin.timer.isActive());admin.deleteLater()

    def test_settings_material_cache_and_reduced_motion(self):
        surface=SettingsSurface(None);surface.resize(900,620);surface._config=lambda:{'reduce_motion':False}
        surface.show();QTest.qWait(100);surface.grab();cache=surface._plate.cacheKey()
        surface.update();QTest.qWait(50);surface.grab();self.assertEqual(cache,surface._plate.cacheKey())
        self.assertGreater(surface.lightPhase,0)
        surface._config=lambda:{'reduce_motion':True};surface.animate_entry()
        self.assertEqual(surface.reveal,1);self.assertNotEqual(surface._ambient.state(),surface._ambient.State.Running)
        surface.hide();self.assertNotEqual(surface._entrance.state(),surface._entrance.State.Running)
        surface.close();surface.deleteLater()

    def test_entry_motion_preference_does_not_hide_information(self):
        admin=ElevationDialog(lambda:False,reduced=True);admin.show();QTest.qWait(40)
        first=admin.grab().toImage();QTest.qWait(120)
        self.assertEqual(first,admin.grab().toImage());self.assertFalse(admin.timer.isActive())
        self.assertTrue(admin.continue_button.isVisible());admin.close();admin.deleteLater()
        import tkinter as tk
        from core.fui_bootstrap import BootstrapSurface
        root=tk.Tk()
        try:
            surface=BootstrapSurface(root,reduced=True)
            before=surface.canvas.coords(surface.wires[0]);surface.animate(5)
            self.assertEqual(before,surface.canvas.coords(surface.wires[0]))
            surface.update_status('Arquivos','Dados de demonstração disponíveis','ok')
            self.assertEqual(surface.states['Arquivos'],'ok')
        finally:root.destroy()

    def test_initial_setup_controls_and_legacy_surfaces_share_glass(self):
        import ui
        for cls in (ui.SetupOverlay,ui.CustomizeOverlay,ui.PluginManagerOverlay,
                    ui.ConfirmBanner,ui.AudioDeviceOverlay,ui.MemoryOverlay,
                    ui.PluginSettingsOverlay,ui.RemoteKeyOverlay,ui.ClipboardPanel,ui._CameraPreview):
            self.assertTrue(issubclass(cls,HudGlassFrame),cls.__name__)
        setup=ui.SetupOverlay();setup.resize(460,420);setup.show();QTest.qWait(100)
        self.assertEqual(setup._key_input.echoMode(),ui.QLineEdit.EchoMode.Password)
        calls=[];setup.done.connect(lambda *args:calls.append(args))
        setup._submit();self.assertEqual(calls,[])
        setup._key_input.setText('synthetic-key-not-real');setup._submit();self.assertEqual(len(calls),1)
        setup._key_input.clear();setup.grab().save(str(OUTPUT/'initial-ai.png'))
        setup.close();self.assertNotEqual(setup._light.state(),setup._light.State.Running);setup.deleteLater()

    def test_tk_hud_does_not_require_pillow_or_qt_and_keeps_actual_states(self):
        import tkinter as tk
        from core.fui_bootstrap import BootstrapSurface
        original=builtins.__import__
        def optional_missing(name,*args,**kwargs):
            if name.startswith(('PIL','PyQt6')):raise ImportError('test dependency unavailable')
            return original(name,*args,**kwargs)
        root=tk.Tk();root.geometry('660x440');root.title('DIEF JARVIS · Teste visual')
        try:
            with patch('builtins.__import__',side_effect=optional_missing):surface=BootstrapSurface(root)
            self.assertIsNone(surface.photo)
            surface.update_status('Dependências','Pacote de teste indisponível','error')
            surface.update_status('Gmail','Conta de teste não conectada','pending')
            self.assertEqual(surface.states['Gmail'],'pending')
            self.assertEqual(surface.rows['Gmail'].cget('text'),'Conta de teste não conectada')
            first=surface.canvas.coords(surface.wires[0]);surface.animate(5)
            self.assertNotEqual(first,surface.canvas.coords(surface.wires[0]))
            count=len(surface.canvas.find_all())
            for i in range(10):surface.animate(i)
            self.assertEqual(count,len(surface.canvas.find_all()))
            root.update_idletasks()
            for label in surface.rows.values():
                self.assertLess(label.winfo_y()+label.winfo_height(),440)
        finally:root.destroy()


class AllSettingsPagesTests(unittest.TestCase):
    setUpClass=classmethod(test_scene.SceneTests.setUpClass.__func__)
    def setUp(self):
        self.visual_folder=tempfile.TemporaryDirectory()
        root=Path(self.visual_folder.name)
        self.patches=[patch('memory.config_manager.CONFIG_FILE',root/'profile.json'),
            patch('core.profile.CONFIG',root/'profile.json'),
            patch('core.integration_tokens.ROOT',root),
            patch('memory.memory_manager.MEMORY_PATH',root/'memory.json'),
            patch('core.gmail_connection.TOKEN',root/'gmail.bin'),
            patch('core.gmail_connection.CREDENTIALS',root/'oauth.json'),
            patch('core.whatsapp_web.PROFILE',root/'whatsapp')]
        for item in self.patches:item.start()
        test_scene.SceneTests.setUp(self)

    def tearDown(self):
        test_scene.SceneTests.tearDown(self)
        for item in reversed(self.patches):item.stop()
        self.visual_folder.cleanup()

    def test_all_six_pages_and_auxiliary_panels_keep_content_and_bounds(self):
        from core.settings_hub import SettingsHub
        import ui
        OUTPUT.mkdir(parents=True,exist_ok=True)
        hub=SettingsHub(self.window,ui.API_FILE,ui.C)
        try:
            hub.show()
            for width,height in ((1366,768),(800,600)):
                hub.resize(width,height)
                for key in hub.page_indices:
                    hub.open_page(key);QTest.qWait(80);hub._entrance.stop();hub.reveal=1
                    self.assertEqual(hub.tabs.count(),6)
                    self.assertTrue(hub.rect().contains(hub.navigation.mapTo(hub,hub.navigation.rect().bottomRight())))
                    hub.grab().save(str(OUTPUT/f'settings-{key}-{width}.png'))
            hub.open_page('connections');self.app.processEvents()
            for row in hub.findChildren(HudGlassFrame):self.assertTrue(row.property('independentTheme'))
            confirm=ui.ConfirmBanner('Ação de demonstração','Texto de teste, sem executar comandos.');confirm.show();QTest.qWait(80)
            confirm.grab().save(str(OUTPUT/'confirmation.png'));confirm.close()
        finally:hub.close();hub.deleteLater()
