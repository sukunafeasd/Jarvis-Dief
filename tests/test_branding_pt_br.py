import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock,patch
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication
from core.branding import StarButton,build_icon
from core.elevation_dialog import ElevationDialog
from core.locale_pt_br import state_label


class BrandingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])

    def test_multisize_icon_has_alpha_and_original_palette(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as folder:
            target=Path(folder)/'dief-jarvis.ico'
            self.assertTrue(build_icon(target))
            with Image.open(target) as icon:
                self.assertTrue({(16,16),(32,32),(256,256)}<=icon.ico.sizes())
            with Image.open(target.with_suffix('.png')) as png:
                self.assertEqual(png.getpixel((0,0))[3],0)
                self.assertEqual(png.size,(256,256))

    def test_qt_application_identity_and_inherited_window_icon(self):
        from core.branding import initialize_application,NAME
        from PyQt6.QtWidgets import QDialog
        with patch('core.app_identity.register_windows_identity',return_value=True) as register:
            initialize_application(self.app)
            register.assert_called_once()
        self.assertEqual(self.app.applicationName(),NAME)
        self.assertEqual(self.app.applicationDisplayName(),NAME)
        self.assertFalse(self.app.windowIcon().isNull())
        dialog=QDialog();self.assertFalse(dialog.windowIcon().isNull());dialog.close()

    def test_native_process_identity_is_registered(self):
        from core import app_identity
        with patch.object(app_identity.ctypes.windll.shell32,'SetCurrentProcessExplicitAppUserModelID',return_value=0) as register:
            self.assertTrue(app_identity.register_windows_identity())
            register.assert_called_once_with('DIEF.JARVIS.Desktop')

    def test_distinct_star_buttons_keep_keyboard_and_tooltip(self):
        buttons=[StarButton('Configurações',5),StarButton('Controles',4)]
        for button in buttons:
            button.show();self.app.processEvents()
            QTest.keyClick(button,Qt.Key.Key_Space)
            self.assertTrue(button.isChecked());self.assertEqual(button.accessibleName(),button.toolTip())
        self.assertNotEqual(buttons[0].grab().toImage(),buttons[1].grab().toImage())
        for button in buttons:button.close()

    def test_elevation_cancel_keeps_gate_and_success_closes(self):
        restart=Mock(side_effect=[False,True])
        dialog=ElevationDialog(restart);dialog.show();self.app.processEvents()
        self.assertFalse(dialog.background.isNull())
        dialog.elevate();self.assertTrue(dialog.isVisible());self.assertTrue(dialog.continue_button.isEnabled())
        self.assertIn('não foi concedida',dialog.notice.text())
        dialog.elevate();self.assertFalse(dialog.isVisible());self.assertFalse(dialog.timer.isActive())
        self.assertEqual(restart.call_count,2)

    def test_admin_gate_does_not_start_app_after_dialog(self):
        from core import elevation
        with patch.object(elevation,'is_admin',return_value=False),patch('core.elevation_dialog.ElevationDialog') as dialog:
            self.assertFalse(elevation.require_admin());dialog.return_value.exec.assert_called_once()

    def test_dialog_framing_small_and_large(self):
        dialog=ElevationDialog(lambda:False)
        for width,height in ((580,560),(960,720)):
            dialog.resize(width,height);dialog.show();self.app.processEvents()
            for widget in (dialog.hologram,dialog.notice,dialog.continue_button):
                self.assertTrue(dialog.rect().contains(widget.mapTo(dialog,widget.rect().bottomRight())))
            dialog.grab().save(str(Path(__file__).resolve().parents[1]/'validation'/f'admin-dief-jarvis-{width}.png'))
        dialog.close();self.assertFalse(dialog.timer.isActive())

    def test_portuguese_state_labels_do_not_change_protocol_ids(self):
        self.assertEqual(state_label('thinking'),'Analisando')
        self.assertEqual(state_label('speaking'),'Falando')
        root=Path(__file__).resolve().parents[1]
        for name in ('login','app'):
            html=(root/'dashboard'/'static'/f'{name}.html').read_text(encoding='utf-8')
            self.assertIn('lang="pt-BR"',html)
            self.assertIn('DIEF JARVIS',html)
            self.assertNotIn('>CONNECT<',html)
        self.assertIn('jarvis_token',(root/'dashboard/static/app.html').read_text(encoding='utf-8'))

    def test_translation_preserves_tool_names_and_enum_contract(self):
        from tools.localize_pt_br import migrate
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'example.py'
            path.write_text('TOOL = {"name": "open_app", "action": "open", "message": "No application name provided."}\n',encoding='utf-8')
            self.assertEqual(migrate(path),1)
            namespace={};exec(path.read_text(encoding='utf-8'),namespace)
            self.assertEqual(namespace['TOOL']['name'],'open_app')
            self.assertEqual(namespace['TOOL']['action'],'open')
            self.assertEqual(namespace['TOOL']['message'],'Informe o nome do aplicativo.')
            self.assertEqual(migrate(path),0)

    def test_hologram_animation_and_text_glyphs(self):
        from PyQt6.QtGui import QFontMetrics
        dialog=ElevationDialog(lambda:False);dialog.show();self.app.processEvents()
        metrics=QFontMetrics(dialog.notice.font())
        self.assertTrue(all(metrics.inFont(letter) for letter in 'PermissãoDIEFJARVIS'))
        first=dialog.grab().toImage()
        with patch('core.elevation_dialog.time.monotonic',return_value=dialog.started+6):
            dialog.update();self.app.processEvents();second=dialog.grab().toImage()
        self.assertNotEqual(first,second)
        self.assertEqual(dialog._background_size,dialog.size())
        cached=dialog._background_scaled.cacheKey()
        dialog.update();self.app.processEvents()
        self.assertEqual(cached,dialog._background_scaled.cacheKey())
        output=Path(__file__).resolve().parents[1]/'validation/admin-finish.png'
        self.assertTrue(dialog.grab().save(str(output)))
        dialog.close()
        self.assertFalse(dialog.timer.isActive())
        dialog.show();self.app.processEvents()
        self.assertTrue(dialog.timer.isActive())
        dialog.close()
