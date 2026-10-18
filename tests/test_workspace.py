import hashlib
import unittest
from unittest.mock import Mock
from pathlib import Path
from PyQt6.QtGui import QImage, QColor
from PyQt6.QtCore import Qt
import test_scene
import test_refresh_visual


class WorkspaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtGui import QFontDatabase,QFont
        cls.app=QApplication.instance() or QApplication([])
        for name in ('segoeui.ttf','consola.ttf'):
            path=Path('C:/Windows/Fonts')/name
            if path.exists():QFontDatabase.addApplicationFont(str(path))
        cls.app.setFont(QFont('Segoe UI',10))
    setUp=test_scene.SceneTests.setUp
    tearDown=test_scene.SceneTests.tearDown
    command=test_scene.SceneTests.command

    def test_terminal_is_on_demand_and_has_real_perspective(self):
        self.assertFalse(self.window._terminal.isVisible())
        self.assertTrue(self.command('open','terminal')['ok'])
        self.assertTrue(self.window._terminal.isVisible())
        self.assertNotEqual(self.window._terminal.proxy.transform().m13(),0)
        self.assertTrue(self.command('close_terminal')['ok'])
        self.assertFalse(self.window._terminal.isVisible())

    def test_terminal_message_uses_existing_channel_and_plain_text(self):
        self.window._open_terminal()
        self.window.on_text_command=Mock()
        self.window._terminal_send('<b>Mensagem de teste</b>')
        import time
        for _ in range(30):
            if self.window.on_text_command.called:break
            time.sleep(.01)
        self.window.on_text_command.assert_called_once_with('<b>Mensagem de teste</b>')
        self.assertIn('<b>Mensagem de teste</b>',self.window._terminal.transcript.toPlainText())

    def photo(self):
        path=Path(self.folder.name)/'photo.png'
        image=QImage(640,400,QImage.Format.Format_RGB32);image.fill(QColor('#529287'));image.save(str(path))
        return path

    def test_photo_request_waits_and_pins_selected_image(self):
        self.assertTrue(self.command('request_image')['ok'])
        self.assertTrue(self.window._pending_image_pin)
        self.assertEqual(len(self.window._pin_previews),0)
        path=self.photo();self.window._terminal_attach(str(path))
        self.assertEqual(self.window._drop_zone.current_file(),str(path))
        identifier=self.window._terminal.attachment_id
        self.assertIn('photo:'+identifier,self.window._pin_previews)
        self.assertFalse(self.window._pending_image_pin)
        self.assertFalse(self.window._pin_previews['photo:'+identifier]['label'].pixmap().isNull())
        self.assertFalse(self.command('pin_image','C:/arbitrary-file.png')['ok'])
        self.assertTrue(self.command('unpin','photo:'+identifier)['ok'])

    def test_plain_attachment_is_not_pinned_as_photo(self):
        path=Path(self.folder.name)/'text.txt';path.write_text('Synthetic test data',encoding='utf-8')
        self.command('request_image');self.window._terminal_attach(str(path))
        self.assertTrue(self.window._pending_image_pin)
        self.assertEqual(len(self.window._pin_previews),0)
        self.assertFalse(self.window._terminal.pin_button.isEnabled())
        self.window._terminal_attach(str(path.parent))
        self.assertEqual(len(self.window._attachments),1)

    def test_operation_panel_shows_real_states_not_fake_progress(self):
        self.window._operation_event('app_control','running')
        self.assertTrue(self.window._execution.isVisible())
        self.assertIn('EM ANDAMENTO',self.window._execution.status.text())
        self.window._operation_event('app_control','uncertain')
        self.assertIn('SEM CONFIRMAÇÃO',self.window._execution.status.text())
        self.assertTrue(self.window._execution_settle.isActive())
        self.command('clear');self.assertFalse(self.window._execution.isVisible())
        self.assertFalse(self.window._execution_settle.isActive())

    def test_panels_photo_and_avatar_fit_and_capture(self):
        self.window.resize(1600,900);self.app.processEvents()
        self.window.hud.hud_style='face'
        self.window._ensure_space();self.window._open_terminal()
        self.window._terminal.add_line('Você: Fixe esta foto aqui.')
        self.window._terminal.add_line('Jarvis: Claro. A foto está fixada no painel.')
        self.window._terminal_attach(str(test_scene.ui.BASE_DIR/'core/spatial/assets/deep-space.png'))
        self.command('pin_image')
        self.window._operation_event('app_control','running')
        self.window._operation_event('app_control','finished')
        self.window._layout_scene(False);self.app.processEvents()
        for panel in (self.window._terminal,self.window._execution):
            panel._progress=1;panel.proxy.setOpacity(1);panel._fit();panel._reveal.stop()
            self.assertTrue(self.window._scene_stage.rect().contains(panel.geometry()))
            self.assertFalse(panel.geometry().intersects(self.window._center_split.geometry()))
        self.assertFalse(self.window._terminal.geometry().intersects(self.window._execution.geometry()))
        for pin in self.window._pin_previews.values():
            self.assertFalse(pin['widget'].geometry().intersects(self.window._terminal.geometry()),str((pin['widget'].geometry(),self.window._terminal.geometry())))
        self.window.grab().save(str(test_scene.ui.BASE_DIR/'validation/space-workspace-face.png'))
        self.window.hud.hud_style='core';self.window.hud.update();self.app.processEvents()
        self.window.grab().save(str(test_scene.ui.BASE_DIR/'validation/space-workspace-core.png'))


class SpaceVisualTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=test_refresh_visual.RefreshVisualTests.asyncSetUp
    asyncTearDown=test_refresh_visual.RefreshVisualTests.asyncTearDown

    async def test_music_scene_renders_playback_pause_without_errors(self):
        await self.page.goto(self.url+'/space.html')
        await self.page.wait_for_function("document.body.dataset.ready==='true'",timeout=60000)
        for playing in (True,False):
            await self.page.evaluate("playing=>window.updateCore({mode:'assistant',media:{playing,progress:20000,duration:180000,at:Date.now()}})",playing)
            frames=await self.page.evaluate('window.spaceDiagnostics().frames')
            await self.page.wait_for_function('before=>window.spaceDiagnostics().frames>before',arg=frames,timeout=15000)
            self.assertGreater(await self.page.evaluate('window.spaceDiagnostics().frames'),frames)
        self.assertEqual(self.errors,[])

    async def test_space_texture_movement_resize_and_pause(self):
        await self.page.goto(self.url+'/space.html')
        await self.page.wait_for_function("document.body.dataset.ready==='true'",timeout=60000)
        for width,height in ((1600,900),(640,480),(390,844)):
            await self.page.set_viewport_size({'width':width,'height':height})
            await self.page.wait_for_timeout(300)
            first=await self.page.locator('canvas:not(#ultron-canvas)').screenshot()
            await self.page.wait_for_timeout(600)
            second=await self.page.locator('canvas:not(#ultron-canvas)').screenshot()
            self.assertNotEqual(hashlib.sha256(first).digest(),hashlib.sha256(second).digest())
            await self.page.screenshot(path=str(test_refresh_visual.BASE/f'validation/space-{width}.png'))
            stats=await self.page.evaluate('window.spaceDiagnostics()')
            self.assertEqual(stats['stars'],1500)
            # The background now contains the solar system, not just two star/photo layers.
            self.assertEqual(stats['budget']['drawCalls'],32)
            self.assertLessEqual(stats['drawCalls'],stats['budget']['drawCalls'])
            self.assertLessEqual(stats['lights'],2)
            from PIL import Image
            import io
            pixels=Image.open(io.BytesIO(second)).convert('RGB')
            self.assertGreater(sum(max(pixel)>25 for pixel in pixels.getdata()),200)
        await self.page.evaluate("window.updateCore({motion:'reduced'})")
        first=await self.page.locator('canvas:not(#ultron-canvas)').screenshot();await self.page.wait_for_timeout(300)
        self.assertEqual(first,await self.page.locator('canvas:not(#ultron-canvas)').screenshot())
        await self.page.evaluate("window.updateCore({visible:false,motion:'full'})")
        frames=await self.page.evaluate('window.spaceDiagnostics().frames');await self.page.wait_for_timeout(300)
        self.assertEqual(frames,await self.page.evaluate('window.spaceDiagnostics().frames'))
        self.assertEqual(self.errors,[])
