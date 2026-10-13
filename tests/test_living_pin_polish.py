import unittest
from pathlib import Path
import test_refresh_visual

BASE=Path(__file__).resolve().parents[1]
OUTPUT=BASE/'validation/living-pins'


class LivingPolishTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=test_refresh_visual.RefreshVisualTests.asyncSetUp
    asyncTearDown=test_refresh_visual.RefreshVisualTests.asyncTearDown

    async def prepare(self):
        OUTPUT.mkdir(parents=True,exist_ok=True)
        await self.page.goto(self.url+'/presentation.html')
        await self.page.wait_for_function('typeof window.updateCore==="function"')

    async def test_sources_group_in_header_not_distant_footer(self):
        await self.prepare()
        for width,height in ((680,440),(390,700)):
            await self.page.set_viewport_size({'width':width,'height':height})
            for kind in ('tasks','calendar','gmail','whatsapp','search','files','memory','system','data'):
                await self.page.evaluate('m=>window.updateCore(m)',{'kind':kind,'title':'Demonstracao',
                    'source':'Fonte local de demonstracao','items':[],'motion':'reduced'})
                self.assertEqual(await self.page.locator('#metadata').inner_text(),'Fonte local de demonstracao')
                self.assertTrue(await self.page.locator('#metadata').is_visible())
                self.assertFalse(await self.page.locator('#source').is_visible())
                meta=await self.page.locator('#metadata').bounding_box()
                header=await self.page.locator('header').bounding_box()
                self.assertGreaterEqual(meta['y'],header['y']);self.assertLessEqual(meta['y']+meta['height'],header['y']+header['height'])
        await self.page.evaluate("window.updateCore({kind:'weather',code:61,temperature:23,city:'Cidade',observed:'12:00'})")
        self.assertIn('Open-Meteo',await self.page.locator('#metadata').inner_text())
        self.assertFalse(await self.page.locator('#source').is_visible())
        self.assertEqual(self.errors,[])

    async def test_compact_icons_move_and_native_wrapper_has_no_inner_box(self):
        await self.prepare()
        await self.page.set_viewport_size({'width':286,'height':140})
        for kind in ('weather','tasks','calendar','gmail','whatsapp','files','memory','system'):
            await self.page.evaluate('m=>window.updateCore(m)',{'kind':kind,'title':'Teste','compact':True,'framed':True,
                'temperature':23,'condition':'Chuva','city':'Cidade','code':61,'count':2,'cpu_percent':35,'ram_percent':60,
                'items':[{'title':'Titulo de teste','detail':'Exemplo breve'}],'motion':'full'})
            await self.page.wait_for_timeout(1700)
            first=await self.page.locator('#scene').screenshot()
            await self.page.wait_for_timeout(450)
            self.assertNotEqual(first,await self.page.locator('#scene').screenshot(),kind)
            self.assertFalse(await self.page.locator('#metadata').is_visible())
            self.assertFalse(await self.page.locator('#source').is_visible())
            self.assertEqual(await self.page.evaluate('getComputedStyle(document.body).backgroundColor'),'rgba(0, 0, 0, 0)')
            self.assertFalse(await self.page.evaluate('document.documentElement.scrollWidth>innerWidth'))
            await self.page.screenshot(path=str(OUTPUT/(kind+'-compact.png')))
        self.assertEqual(self.errors,[])

    async def test_pointer_only_affects_icon_and_freezes_on_cancel(self):
        await self.prepare()
        await self.page.set_viewport_size({'width':680,'height':440})
        model={'kind':'whatsapp','title':'Teste','items':[{'title':'Contato','detail':'Exemplo'}],'motion':'full'}
        await self.page.evaluate('m=>window.updateCore(m)',model)
        await self.page.wait_for_timeout(1800)
        bounds=await self.page.locator('#symbol-space').bounding_box()
        text=await self.page.locator('#summary').bounding_box()
        await self.page.mouse.move(bounds['x']+bounds['width']*.85,bounds['y']+bounds['height']*.5)
        await self.page.wait_for_timeout(600)
        self.assertGreater(await self.page.evaluate('window.holographicMotionDiagnostics().pointerEnergy'),.5)
        self.assertEqual(text,await self.page.locator('#summary').bounding_box())
        await self.page.evaluate('window.cancelPresentation()')
        await self.page.wait_for_timeout(150)
        tilt=await self.page.evaluate('window.holographicMotionDiagnostics().tilt')
        await self.page.mouse.move(670,430);await self.page.wait_for_timeout(300)
        self.assertEqual(tilt,await self.page.evaluate('window.holographicMotionDiagnostics().tilt'))
        await self.page.evaluate('m=>window.updateCore(m)',{**model,'motion':'reduced'})
        await self.page.wait_for_timeout(250)
        self.assertEqual(await self.page.evaluate('window.holographicMotionDiagnostics().pointerEnergy'),0)
        self.assertEqual(await self.page.evaluate('window.holographicMotionDiagnostics().tilt'),[0,0])
        self.assertEqual(self.errors,[])


class NativeRepaintTests(unittest.TestCase):
    def test_settings_bottom_conductor_is_repainted(self):
        import os
        os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
        from unittest.mock import patch
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtCore import QPoint
        from core.settings_style import SettingsSurface
        app=QApplication.instance() or QApplication([])
        surface=SettingsSurface(None);surface.resize(900,620)
        try:
            with patch.object(SettingsSurface,'update') as update:
                surface.lightPhase=.5
                region=update.call_args.args[0]
                self.assertTrue(region.contains(QPoint(450,614)))
                self.assertTrue(region.contains(QPoint(892,310)))
        finally:
            surface.close();surface.deleteLater();app.processEvents()
