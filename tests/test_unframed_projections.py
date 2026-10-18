import unittest
from pathlib import Path
import test_refresh_visual

BASE=Path(__file__).resolve().parents[1]
OUTPUT=BASE/'validation/unframed-projections'


class ProjectionTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=test_refresh_visual.RefreshVisualTests.asyncSetUp
    asyncTearDown=test_refresh_visual.RefreshVisualTests.asyncTearDown

    async def prepare(self):
        OUTPUT.mkdir(parents=True,exist_ok=True)
        await self.page.goto(self.url+'/presentation.html')
        await self.page.wait_for_function('typeof window.updateCore==="function"')

    async def test_surface_policy_keeps_live_weather_unframed_and_pins_and_refresh_glass(self):
        await self.prepare()
        cases=[({'kind':'weather','code':61,'temperature':23},'projection'),
               ({'kind':'weather','code':61,'temperature':23,'compact':True,'framed':True},'card'),
               ({'kind':'gmail','compact':True,'framed':True},'card'),
               ({'kind':'status','refreshTransaction':True},'card'),
               ({'kind':'news'},'embedded'),({'kind':'gmail'},'projection'),
               ({'kind':'calendar'},'projection'),({'kind':'search'},'projection')]
        for model,expected in cases:
            await self.page.evaluate('m=>window.updateCore(m)',model)
            await self.page.wait_for_timeout(120)
            self.assertEqual(await self.page.evaluate('document.body.dataset.surface'),expected)
            if expected=='projection':
                style=await self.page.evaluate('''() => ({body:getComputedStyle(document.body).backgroundImage,
                    frame:getComputedStyle(document.querySelector('main'),'::before').display,
                    border:getComputedStyle(document.querySelector('main')).borderLeftWidth})''')
                self.assertEqual(style,{'body':'none','frame':'none','border':'0px'})
        self.assertEqual(self.errors,[])

    async def test_each_semantic_icon_moves_with_stable_adjacent_labels(self):
        await self.prepare()
        await self.page.set_viewport_size({'width':680,'height':440})
        for kind in ('gmail','whatsapp','calendar','tasks','search','files','memory','system'):
            model={'kind':kind,'title':'Demonstracao','text':'Informacao de teste','count':2,
                   'cpu_percent':35,'ram_percent':62,'gpu_percent':40,
                   'items':[{'title':'Registro de demonstracao','detail':'Conteudo sintetico'}]}
            await self.page.evaluate('m=>window.updateCore(m)',model)
            await self.page.wait_for_timeout(1800)
            bounds=await self.page.locator('#symbol-space').bounding_box()
            labels=await self.page.locator('#summary').bounding_box()
            self.assertLessEqual(bounds['x']+bounds['width'],labels['x'])
            before=await self.page.locator('#scene').screenshot()
            await self.page.wait_for_timeout(450)
            self.assertNotEqual(before,await self.page.locator('#scene').screenshot(),kind)
            self.assertEqual(labels,await self.page.locator('#summary').bounding_box(),kind)
            await self.page.evaluate("document.documentElement.style.background=\"#03070a url('./assets/deep-space.png') center/cover\"")
            await self.page.screenshot(path=str(OUTPUT/(kind+'.png')))
            await self.page.evaluate("document.documentElement.style.background='transparent'")
        self.assertEqual(self.errors,[])

    async def test_long_communications_fit_desktop_mobile_and_reading(self):
        await self.prepare()
        for width,height in ((900,420),(600,420),(390,844)):
            await self.page.set_viewport_size({'width':width,'height':height})
            model={'kind':'gmail','title':'Mensagens importantes','reading':True,
                   'items':[{'title':'Assunto importante com texto extenso para validar leitura na tela',
                             'detail':'Mensagem de demonstracao. '*100}],'motion':'reduced'}
            await self.page.evaluate('m=>window.updateCore(m)',model)
            await self.page.wait_for_timeout(2200)
            self.assertFalse(await self.page.evaluate('document.documentElement.scrollWidth>innerWidth'))
            bounds=await self.page.locator('#details').bounding_box()
            self.assertLessEqual(bounds['x']+bounds['width'],width)
            self.assertLessEqual(bounds['y']+bounds['height'],height)
            self.assertGreater(bounds['height'],50)
            await self.page.screenshot(path=str(OUTPUT/f'gmail-reading-{width}.png'))
        self.assertEqual(self.errors,[])

    async def test_paused_icon_pixels_freeze_and_compact_icon_still_moves(self):
        await self.prepare()
        model={'kind':'whatsapp','title':'Teste','items':[{'title':'Contato','detail':'Mensagem sintetica'}]}
        await self.page.evaluate('m=>window.updateCore(m)',model)
        await self.page.wait_for_timeout(1800)
        await self.page.evaluate('window.cancelPresentation()')
        await self.page.wait_for_timeout(300)
        before=await self.page.locator('#scene').screenshot()
        await self.page.wait_for_timeout(350)
        self.assertEqual(before,await self.page.locator('#scene').screenshot())
        await self.page.evaluate('m=>window.updateCore(m)',{**model,'compact':True,'framed':True,'presentationId':'pin-test'})
        await self.page.set_viewport_size({'width':310,'height':180})
        await self.page.wait_for_timeout(2000)
        before=await self.page.locator('#scene').screenshot()
        await self.page.wait_for_timeout(500)
        self.assertNotEqual(before,await self.page.locator('#scene').screenshot())
        self.assertEqual(self.errors,[])

    async def test_explicit_full_motion_overrides_os_but_reduced_still_freezes(self):
        await self.prepare()
        await self.page.emulate_media(reduced_motion='reduce')
        model={'kind':'gmail','title':'Teste','items':[]}
        await self.page.evaluate('m=>window.updateCore(m)',model)
        await self.page.wait_for_timeout(1200)
        first=await self.page.evaluate('window.holographicMotionDiagnostics().time')
        await self.page.wait_for_timeout(200)
        self.assertEqual(first,await self.page.evaluate('window.holographicMotionDiagnostics().time'))
        await self.page.evaluate('m=>window.updateCore(m)',{**model,'motion':'full'})
        await self.page.wait_for_timeout(400)
        self.assertGreater(await self.page.evaluate('window.holographicMotionDiagnostics().time'),first)
        await self.page.evaluate('m=>window.updateCore(m)',{**model,'motion':'reduced'})
        await self.page.wait_for_timeout(200)
        first=await self.page.evaluate('window.holographicMotionDiagnostics().time')
        await self.page.wait_for_timeout(250)
        self.assertEqual(first,await self.page.evaluate('window.holographicMotionDiagnostics().time'))

    async def test_system_rows_do_not_overlap_on_short_panels(self):
        await self.prepare()
        for width,height in ((900,300),(390,700),(390,400)):
            await self.page.set_viewport_size({'width':width,'height':height})
            await self.page.evaluate("window.updateCore({kind:'system',cpu_percent:35,ram_percent:50,uptime:'2h',process_count:12})")
            await self.page.wait_for_timeout(300)
            metrics=await self.page.locator('#metrics').bounding_box()
            details=await self.page.locator('#details').bounding_box()
            self.assertLessEqual(metrics['y']+metrics['height'],details['y'])
            if height<500 and width<431:
                self.assertEqual(await self.page.evaluate("getComputedStyle(document.querySelector('main')).overflowY"),'auto')
                footer=await self.page.locator('footer').bounding_box()
                if footer:self.assertLessEqual(details['y']+details['height'],footer['y'])
                else:self.assertFalse(await self.page.locator('#source').is_visible())
            else:self.assertLessEqual(details['y']+details['height'],height)
