import unittest
from pathlib import Path
import test_refresh_visual

BASE = Path(__file__).resolve().parents[1]
OUTPUT = BASE / 'validation/holographic-motion'


class HolographicMotionTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = test_refresh_visual.RefreshVisualTests.asyncSetUp
    asyncTearDown = test_refresh_visual.RefreshVisualTests.asyncTearDown

    async def prepare(self):
        OUTPUT.mkdir(parents=True, exist_ok=True)
        self.page.on('console', lambda message: self.errors.append(message.text)
            if message.type=='error' and ('Shader Error' in message.text or 'VALIDATE_STATUS' in message.text) else None)
        await self.page.goto(self.url+'/presentation.html')
        await self.page.wait_for_function('typeof window.holographicMotionDiagnostics === "function"')

    async def test_frame_and_symbols_move_without_moving_text_or_leaking(self):
        await self.prepare()
        await self.page.set_viewport_size({'width':540,'height':700})
        model={'kind':'weather','title':'CLIMA DE TESTE','city':'Cidade de teste',
            'code':61,'temperature':19,'condition':'Chuva','motion':'full'}
        await self.page.evaluate('m=>window.updateCore(m)',model)
        await self.page.wait_for_timeout(3000)
        measure='''() => ['summary','details','metrics'].map(id=>{
          const r=document.getElementById(id).getBoundingClientRect(); return [r.x,r.y,r.width,r.height];})'''
        first_bounds=await self.page.evaluate(measure)
        first=await self.page.locator('canvas').screenshot()
        raw_first=await self.page.evaluate('document.getElementById("scene").toDataURL()')
        first_diag=await self.page.evaluate('window.holographicMotionDiagnostics()')
        await self.page.wait_for_timeout(650)
        second=await self.page.locator('canvas').screenshot()
        raw_second=await self.page.evaluate('document.getElementById("scene").toDataURL()')
        self.assertNotEqual(first,second)
        self.assertEqual(first_bounds,await self.page.evaluate(measure))
        from io import BytesIO
        import base64
        from PIL import Image, ImageChops
        a=Image.open(BytesIO(base64.b64decode(raw_first.split(',')[1]))).convert('RGBA')
        b=Image.open(BytesIO(base64.b64decode(raw_second.split(',')[1]))).convert('RGBA')
        edge=ImageChops.difference(a.crop((0,0,540,20)),b.crop((0,0,540,20)))
        self.assertTrue(edge.convert('RGB').getbbox() or edge.getchannel('A').getbbox())
        self.assertTrue(first_diag['rig']);self.assertEqual(first_diag['rings'],2)
        self.assertGreater(first_diag['drawCalls'],5);self.assertLess(first_diag['drawCalls'],65)
        for index in range(24):
            await self.page.evaluate('m=>window.updateCore(m)',{**model,'temperature':index})
        await self.page.wait_for_timeout(200)
        final=await self.page.evaluate('window.holographicMotionDiagnostics()')
        self.assertEqual(first_diag['geometries'],final['geometries'])
        await self.page.screenshot(path=str(OUTPUT/'weather-motion.png'))
        self.assertEqual(self.errors,[])

    async def test_motion_freezes_for_reduced_hidden_and_interrupted_states(self):
        await self.prepare()
        model={'kind':'whatsapp','title':'DEMONSTRACAO','items':[{'title':'Contato de teste','detail':'Texto de teste'}]}
        await self.page.evaluate('m=>window.updateCore(m)',model)
        await self.page.wait_for_timeout(900)
        await self.page.evaluate('window.cancelPresentation()')
        await self.page.wait_for_timeout(100)
        frozen=await self.page.evaluate('window.holographicMotionDiagnostics().time')
        await self.page.wait_for_timeout(200)
        self.assertEqual(frozen,await self.page.evaluate('window.holographicMotionDiagnostics().time'))
        await self.page.evaluate('window.updateCore({visible:false})')
        await self.page.wait_for_timeout(150)
        first=await self.page.locator('canvas').screenshot()
        await self.page.wait_for_timeout(200)
        self.assertEqual(first,await self.page.locator('canvas').screenshot())
        await self.page.evaluate('m=>window.updateCore(m)',{**model,'motion':'reduced'})
        await self.page.wait_for_timeout(3000)
        first=await self.page.locator('canvas').screenshot()
        await self.page.wait_for_timeout(250)
        self.assertEqual(first,await self.page.locator('canvas').screenshot())
        self.assertEqual(await self.page.evaluate('window.holographicMotionDiagnostics().panelTime'),0)
        self.assertEqual(self.errors,[])

    async def test_embedded_news_has_no_extra_hologram_and_dismissal_finishes(self):
        await self.prepare()
        await self.page.evaluate("window.updateCore({kind:'news',title:'Noticias',narrationDriven:true,items:[{title:'Primeira noticia de teste'},{title:'Segunda noticia de teste'}]})")
        await self.page.evaluate('window.advancePresentation({elapsed:4,cues:[]})')
        await self.page.wait_for_timeout(150)
        self.assertFalse(await self.page.evaluate('window.holographicMotionDiagnostics().rig'))
        self.assertEqual(await self.page.locator('body').get_attribute('data-secondary-core'),'false')
        self.assertEqual(await self.page.locator('.record.selected').get_attribute('data-index'),'0')
        await self.page.evaluate("window.narratePresentation('Segunda noticia.')")
        self.assertEqual(await self.page.locator('.record.selected').get_attribute('data-index'),'1')
        await self.page.evaluate('window.dismissPresentation()')
        await self.page.wait_for_function('getComputedStyle(document.body).opacity==="0"',timeout=2000)
        self.assertEqual(await self.page.evaluate('getComputedStyle(document.body).opacity'),'0')
        await self.page.evaluate('window.updateCore({visible:true})')
        self.assertEqual(await self.page.evaluate('getComputedStyle(document.body).opacity'),'1')
        self.assertEqual(await self.page.evaluate('document.querySelector("main").style.opacity'),'1')
        await self.page.evaluate('window.dismissPresentation()')
        await self.page.wait_for_timeout(270)
        self.assertEqual(await self.page.evaluate('getComputedStyle(document.body).opacity'),'0')
        await self.page.evaluate("window.updateCore({kind:'gmail',title:'Gmail',motion:'reduced',items:[]})")
        self.assertEqual(await self.page.evaluate('getComputedStyle(document.body).opacity'),'1')
        self.assertEqual(self.errors,[])

    async def test_library_orbits_and_breathing_continue_after_assembly(self):
        OUTPUT.mkdir(parents=True, exist_ok=True)
        await self.page.goto(self.url+'/visual_library.html')
        await self.page.wait_for_function('typeof window.updateCore === "function"')
        for motion in ('orbitar','respirar'):
            await self.page.evaluate('''animation=>window.updateCore({visible:true,reduced:false,elements:[{
                id:"simbolo",animation,parts:[{primitive:"orb"},{primitive:"ring",slot:"orbita"}],
                colors:["#32dfff","#ff5368"],scale:1,visible:true,revealed:true,
                bounds:{x:250,y:200,width:240,height:180}}]})''',motion)
            await self.page.wait_for_timeout(1800)
            first=await self.page.locator('canvas').screenshot()
            await self.page.wait_for_timeout(500)
            self.assertNotEqual(first,await self.page.locator('canvas').screenshot())
            self.assertTrue(await self.page.evaluate('window.visualDiagnostics().scheduled'))
        await self.page.screenshot(path=str(OUTPUT/'library-motion.png'))
        await self.page.evaluate('window.updateCore({visible:false})')
        self.assertFalse(await self.page.evaluate('window.visualDiagnostics().scheduled'))
        self.assertEqual(self.errors,[])


class NativeHolographicMotionTests(unittest.TestCase):
    def test_native_lights_stop_for_hidden_reduced_and_proxy_panels(self):
        import os
        os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtTest import QTest
        from core.hud_glass import HudGlassFrame
        from core.workspace_panels import WorkspacePanel
        from core.settings_style import SettingsSurface
        app=QApplication.instance() or QApplication([])
        frame=HudGlassFrame(); frame.resize(320,150);frame.show();QTest.qWait(100)
        self.assertGreater(frame.lightPhase,0)
        frame.showMinimized();QTest.qWait(60)
        self.assertNotEqual(frame._light.state(),frame._light.State.Running)
        frame.showNormal();QTest.qWait(60)
        self.assertEqual(frame._light.state(),frame._light.State.Running)
        cache=frame._plate.cacheKey(); frame.hide();before=frame.lightPhase;QTest.qWait(100)
        self.assertEqual(before,frame.lightPhase)
        frame.set_motion_reduced(True);frame.show();QTest.qWait(70)
        self.assertEqual(frame.lightPhase,0);self.assertEqual(cache,frame._plate.cacheKey())
        panel=WorkspacePanel(None);panel.resize(520,430)
        self.assertNotEqual(panel.surface._light.state(),panel.surface._light.State.Running)
        panel.show_panel(reduced=False);QTest.qWait(100)
        self.assertEqual(panel.surface._light.state(),panel.surface._light.State.Running)
        panel.close_panel();self.assertNotEqual(panel.surface._light.state(),panel.surface._light.State.Running)
        settings=SettingsSurface(None);settings._config=lambda:{'reduce_motion':False};settings.show();QTest.qWait(100)
        self.assertEqual(settings._ambient.state(),settings._ambient.State.Running)
        settings._config=lambda:{'reduce_motion':True};settings.animate_entry()
        self.assertNotEqual(settings._ambient.state(),settings._ambient.State.Running)
        for widget in (frame,panel,settings):widget.close();widget.deleteLater()
        app.processEvents()
