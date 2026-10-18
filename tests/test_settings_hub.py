import json
import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock,patch
from PyQt6.QtWidgets import QApplication
import ui
from core.settings_hub import SettingsHub
from core.profile import read_profile

class SettingsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])
        cls.app.setStyle('Fusion')

    def test_profile_and_settings_are_connected_without_exposing_key(self):
        with tempfile.TemporaryDirectory() as folder:
            config=Path(folder)/"config.json"
            config.write_text(json.dumps({"gemini_api_key":"test-secret","city":"São Paulo"}),encoding="utf-8")
            with patch.object(ui,"API_FILE",config):
                window=ui.MainWindow(str(ui.BASE_DIR/"core/face_model.obj"))
                window.on_voice_change=Mock(); window.on_text_command=Mock()
                hub=SettingsHub(window,config,ui.C)
                self.assertEqual(hub.tabs.count(),6)
                self.assertEqual(hub.navigation.count(),6)
                profile_page=hub.tabs.widget(hub.page_indices['profile']).widget()
                self.assertTrue(profile_page.isAncestorOf(hub.visual))
                self.assertTrue(profile_page.isAncestorOf(hub.brief))
                self.assertFalse(hasattr(window,'_ctrl_btn'))
                self.assertTrue(window.windowFlags() & ui.Qt.WindowType.FramelessWindowHint)
                hub.city.setText("Porto Alegre"); hub.name.setText("Dief");hub.interests.setPlainText("Ciência e tecnologia");hub.count.setValue(3)
                with patch("memory.config_manager.save_hud_style"),patch("memory.config_manager.save_voice"):
                    hub.save()
                saved=json.loads(config.read_text(encoding="utf-8"))
                self.assertEqual(saved["city"],"Porto Alegre")
                self.assertEqual(saved["gemini_api_key"],"test-secret")
                with patch("core.profile.CONFIG",config):
                    public=read_profile()
                self.assertNotIn("gemini_api_key",public)
                self.assertEqual(public["news_count"],3)
                window.on_voice_change.assert_called_once()
                window._show_manifestation({"kind":"tasks","title":"TAREFAS","count":1,"items":[{"id":1,"title":"Exemplo"}]})
                request={"action":"move","value":"left","done":__import__('threading').Event()}
                window._apply_interface_request(request)
                self.assertTrue(request["result"]["ok"])
                self.assertEqual(window._scene_position,"left")
                window._avatar_interaction('touch',.5,.5)
                self.assertFalse(window._muted)
                self.assertTrue(window._resting)
                self.assertEqual(window.hud.state,'SLEEPING')
                window._avatar_interaction('touch',.5,.5)
                self.assertFalse(window._muted)
                self.assertFalse(window._resting)
                clock_before=window._clock_lbl.pos()
                window._avatar_interaction('move',.1,.3)
                self.assertIsNotNone(window._avatar_anchor)
                self.assertEqual(window._clock_lbl.pos(),clock_before)
                hub.showFullScreen();self.app.processEvents()
                self.assertTrue(hub.isFullScreen())
                self.assertEqual(window.hud.toolTip(),'')
                from core.settings_style import SETTINGS_STYLE
                old_style=hub.styleSheet()
                ui.retheme_all_widgets({'PRI':'#776397'},{'PRI':'#ff0000'})
                self.assertEqual(hub.styleSheet(),old_style)
                self.assertEqual(hub.styleSheet(),SETTINGS_STYLE)
                hub.grab().save(str(ui.BASE_DIR/"validation/settings-hub.png"))
                hub.close();window.close();hub.deleteLater();window.deleteLater();self.app.processEvents()

    def test_invalid_profile_numbers_fall_back(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"config.json";path.write_text('{"news_count":"invalid","presentation_hold":null}')
            with patch("core.profile.CONFIG",path):
                profile=read_profile()
            self.assertEqual(profile["news_count"],5)
            self.assertEqual(profile["presentation_hold"],15)

    def test_settings_pages_remain_readable_and_tools_open_inside_hub(self):
        from PyQt6.QtWidgets import QWidget, QVBoxLayout
        with tempfile.TemporaryDirectory() as folder:
            config=Path(folder)/'config.json';config.write_text('{}')
            with patch.object(ui,'API_FILE',config):
                window=ui.MainWindow(str(ui.BASE_DIR/'core/face_model.obj'))
                hub=SettingsHub(window,config,ui.C)
                try:
                    hub.show()
                    for width,height in ((800,600),(1366,768),(1920,1080)):
                        hub.resize(width,height);self.app.processEvents()
                        for index in range(hub.navigation.count()):
                            hub.navigation.setCurrentRow(index);self.app.processEvents()
                            self.assertEqual(hub.section_title.text(),hub.navigation.currentItem().text())
                            self.assertTrue(hub.rect().contains(hub.navigation.mapTo(hub,hub.navigation.rect().bottomRight())))
                            if index in (0,1,4):
                                hub.grab().save(str(ui.BASE_DIR/f'validation/settings-{index}-{width}.png'))
                    def tool():
                        panel=QWidget(window.centralWidget());layout=QVBoxLayout(panel)
                        layout.addWidget(ui.QLabel('Ferramenta de teste'));panel.show()
                    hub.navigation.setCurrentRow(4)
                    window.show();self.app.processEvents();hub.showFullScreen();self.app.processEvents()
                    hub.open_overlay(tool);self.app.processEvents()
                    self.assertIs(hub.tabs.currentWidget(),hub._detail_page)
                    self.assertTrue(hub.isAncestorOf(hub._detail_overlay))
                    self.assertTrue(hub.isFullScreen())
                    hub._leave_detail();self.app.processEvents();self.assertEqual(hub.tabs.currentIndex(),4)
                    hub.open_overlay(window._open_plugin_manager);self.app.processEvents()
                    self.assertTrue(hub.isAncestorOf(window._plugin_manager_overlay))
                    self.assertTrue(hub.isFullScreen())
                    hub._leave_detail();self.app.processEvents()
                finally:
                    hub.close();window.close();hub.deleteLater();window.deleteLater();self.app.processEvents()

    def test_ai_key_save_never_echoes_secret(self):
        with tempfile.TemporaryDirectory() as folder:
            config=Path(folder)/'config.json';config.write_text('{}')
            with patch.object(ui,'API_FILE',config):
                window=ui.MainWindow(str(ui.BASE_DIR/'core/face_model.obj'));window.on_voice_change=Mock()
                hub=SettingsHub(window,config,ui.C)
                try:
                    hub.ai_key.setText('test-only-secret');hub.save_ai_key()
                    self.assertEqual(json.loads(config.read_text())['gemini_api_key'],'test-only-secret')
                    self.assertEqual(hub.ai_key.text(),'')
                    self.assertNotIn('test-only-secret',hub.ai_notice.text())
                    self.assertEqual(hub.ai_key.echoMode(),hub.ai_key.EchoMode.Password)
                    window.on_voice_change.assert_called_once()
                finally:
                    hub.close();window.close();hub.deleteLater();window.deleteLater();self.app.processEvents()

    def test_fixed_dark_theme_and_animation_lifecycle(self):
        from PyQt6.QtCore import QAbstractAnimation
        from PyQt6.QtGui import QPalette
        with tempfile.TemporaryDirectory() as folder:
            config=Path(folder)/'config.json';config.write_text('{"reduce_motion":true}')
            with patch.object(ui,'API_FILE',config):
                window=ui.MainWindow(str(ui.BASE_DIR/'core/face_model.obj'))
                hub=SettingsHub(window,config,ui.C)
                try:
                    hub.resize(1366,768);hub.show();self.app.processEvents()
                    pixel=hub.grab().toImage().pixelColor(1201,701)
                    self.assertLess(max(pixel.red(),pixel.green(),pixel.blue()),80)
                    self.assertGreaterEqual(pixel.blue(),pixel.red())
                    self.assertEqual(hub.palette().color(QPalette.ColorRole.Text).name(),'#edfaff')
                    self.assertEqual(hub._entrance.state(),QAbstractAnimation.State.Stopped)
                    config.write_text('{"reduce_motion":false}')
                    hub.animate_entry()
                    self.assertEqual(hub._entrance.state(),QAbstractAnimation.State.Running)
                    hub.hide();self.app.processEvents()
                    self.assertEqual(hub._entrance.state(),QAbstractAnimation.State.Stopped)
                finally:
                    hub.close();window.close();hub.deleteLater();window.deleteLater();self.app.processEvents()

    def test_gmail_settings_keep_secret_hidden_and_test_selected_account(self):
        from core import gmail_connection as gmail
        with tempfile.TemporaryDirectory() as folder:
            config=Path(folder)/'config.json';config.write_text('{}')
            with patch.object(ui,'API_FILE',config), patch.object(gmail,'CREDENTIALS',Path(folder)/'client.json'), patch.object(gmail,'TOKEN',Path(folder)/'token.bin'), patch.object(gmail,'expected_account',return_value='wanted@example.com'), patch('memory.config_manager.save_plugin_config') as preferences:
                window=ui.MainWindow(str(ui.BASE_DIR/'core/face_model.obj'))
                hub=SettingsHub(window,config,ui.C)
                try:
                    hub.gmail_client.setText('test.apps.googleusercontent.com')
                    hub.gmail_secret.setText('dummy-secret')
                    self.assertTrue(hub.save_gmail_credentials())
                    self.assertEqual(hub.gmail_secret.text(),'')
                    self.assertEqual(hub.gmail_secret.echoMode(),hub.gmail_secret.EchoMode.Password)
                    preferences.assert_called_with('gmail_control',{'expected_email':'wanted@example.com'})
                    with patch.object(hub,'_connection_worker') as worker, patch.object(gmail,'verify',return_value=(True,'verified')) as verify:
                        hub.check_gmail();worker.call_args.args[0]()
                        verify.assert_called_once_with('wanted@example.com')
                    hub.navigation.setCurrentRow(4);hub.showFullScreen();self.app.processEvents()
                    hub.grab().save(str(ui.BASE_DIR/'validation/gmail-connections.png'))
                finally:
                    hub.close();window.close();hub.deleteLater();window.deleteLater();self.app.processEvents()

    def test_face_touch_only_hits_projected_mesh(self):
        from PyQt6.QtCore import QPointF, QPoint
        from PyQt6.QtTest import QTest
        hud=ui.HudCanvas(str(ui.BASE_DIR/"core/face_model.obj"))
        hud.resize(700,650);hud.hud_style="face"
        callback=Mock();hud.interaction.connect(callback)
        self.assertFalse(hud._hits_hologram(QPointF(5,5)))
        cx,cy,r=hud._face_geometry()
        self.assertTrue(hud._hits_hologram(QPointF(cx,cy)))
        QTest.mouseClick(hud,ui.Qt.MouseButton.LeftButton,pos=QPoint(5,5))
        callback.assert_not_called()
        QTest.mouseClick(hud,ui.Qt.MouseButton.LeftButton,pos=QPoint(int(cx),int(cy)))
        self.assertEqual(callback.call_args.args[0],"touch")
        callback.reset_mock();hud.resting=True;hud._rest_visibility=.14
        cx,cy,r=hud._face_geometry()
        QTest.mouseClick(hud,ui.Qt.MouseButton.LeftButton,pos=QPoint(int(cx),int(cy)))
        self.assertEqual(callback.call_args.args[0],"touch")
        hud.close();hud.deleteLater();self.app.processEvents()
