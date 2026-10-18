import unittest
from unittest.mock import Mock
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
import test_scene
import test_fui_screens
import test_refresh_visual


class EighthBridgeAudit(unittest.TestCase):
    setUpClass=classmethod(test_scene.SceneTests.setUpClass.__func__)
    setUp=test_fui_screens.AllSettingsPagesTests.setUp
    tearDown=test_fui_screens.AllSettingsPagesTests.tearDown

    def test_f11_toggles_from_child_input(self):
        self.window.showFullScreen()
        QTest.keyClick(self.window._content_display,Qt.Key.Key_F11)
        self.assertFalse(self.window.isFullScreen())
        QTest.qWait(180)
        QTest.keyClick(self.window._content_display,Qt.Key.Key_F11)
        self.assertTrue(self.window.isFullScreen())

    def test_news_without_narration_still_fuses_when_core_available(self):
        self.window.hud.hud_style='core'
        self.window.hud._spatial_core=Mock(failed=False,_loaded=True)
        self.window._content_spatial=Mock(failed=False,_loaded=True)
        try:
            self.window._show_manifestation({'kind':'news','items':[{'title':'Teste'}],'narrationDriven':False})
            self.assertIsNotNone(self.window.hud.news_content)
            self.assertEqual(self.window.hud.news_content['mode'],'settled')
            self.assertTrue(self.window._content_spatial.sync.call_args.args[0]['newsFusion'])
        finally:
            self.window.hud._spatial_core=None
            self.window._content_spatial=None


class EighthVisualAudit(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=test_refresh_visual.RefreshVisualTests.asyncSetUp
    asyncTearDown=test_refresh_visual.RefreshVisualTests.asyncTearDown

    async def test_staged_core_does_not_flash_before_entrance(self):
        await self.page.goto(self.url+'/index.html?staged=1')
        await self.page.wait_for_function('typeof window.hologramDiagnostics === "function"')
        before=await self.page.evaluate('window.hologramDiagnostics()')
        self.assertTrue(before['coreVisible'])
        self.assertEqual(before['travel'],24)
        await self.page.evaluate('window.updateEnvironment({staging:false,entrance:{at:Date.now(),duration:4300,cancelAt:null}})')
        await self.page.wait_for_timeout(150)
        first=await self.page.evaluate('window.hologramDiagnostics()')
        await self.page.wait_for_timeout(500)
        second=await self.page.evaluate('window.hologramDiagnostics()')
        self.assertTrue(second['coreVisible'])
        self.assertGreater(first['travel'],second['travel'])
        self.assertGreater(second['travel'],15)
        self.assertEqual(self.errors,[])

    async def test_updates_do_not_restart_frame_scheduler(self):
        await self.page.goto(self.url+'/index.html')
        await self.page.wait_for_function('typeof window.hologramDiagnostics === "function"')
        before=await self.page.evaluate('window.hologramDiagnostics().framesRendered')
        await self.page.evaluate('window.flood=setInterval(()=>window.updateCore({phase:"idle",level:Math.random()*.01}),2)')
        await self.page.wait_for_timeout(600)
        await self.page.evaluate('clearInterval(window.flood)')
        after=await self.page.evaluate('window.hologramDiagnostics().framesRendered')
        self.assertGreater(after-before,2)
        self.assertLess(after-before,25)
