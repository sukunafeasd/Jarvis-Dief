import hashlib
import unittest
import test_refresh_visual


class VisualContinuityTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = test_refresh_visual.RefreshVisualTests.asyncSetUp
    asyncTearDown = test_refresh_visual.RefreshVisualTests.asyncTearDown

    async def test_space_moves_on_desktop_and_small_window_and_suspends_when_hidden(self):
        await self.page.goto(self.url + '/space.html')
        await self.page.wait_for_function("document.body.dataset.ready === 'true'",timeout=60000)
        for width, height in [(1920, 1080), (640, 480)]:
            await self.page.set_viewport_size({'width': width, 'height': height})
            await self.page.evaluate("window.updateCore({visible:true,motion:'full'})")
            await self.page.wait_for_timeout(600)
            first = await self.page.locator('canvas:not(#ultron-canvas)').screenshot()
            # Frequent state synchronization must not starve the render scheduler.
            await self.page.evaluate("async()=>{for(let i=0;i<30;i++){window.updateCore({visible:true});await new Promise(r=>setTimeout(r,20));}}")
            second = await self.page.locator('canvas:not(#ultron-canvas)').screenshot()
            self.assertNotEqual(hashlib.sha256(first).digest(), hashlib.sha256(second).digest())
            await self.page.screenshot(path=str(test_refresh_visual.BASE / f'validation/space-motion-{width}.png'))
            from PIL import Image, ImageStat
            from io import BytesIO
            image = Image.open(BytesIO(second)).convert('RGB')
            self.assertGreater(max(ImageStat.Stat(image).stddev), 5)
            self.assertGreater((await self.page.evaluate('window.spaceDiagnostics()'))['drawCalls'], 0)
        await self.page.evaluate('window.updateCore({visible:false})')
        frames = (await self.page.evaluate('window.spaceDiagnostics()'))['frames']
        await self.page.wait_for_timeout(300)
        self.assertEqual((await self.page.evaluate('window.spaceDiagnostics()'))['frames'], frames)
        await self.page.evaluate("window.updateCore({visible:true,motion:'reduced'})")
        await self.page.wait_for_timeout(200)
        first = await self.page.locator('canvas:not(#ultron-canvas)').screenshot()
        await self.page.wait_for_timeout(300)
        second = await self.page.locator('canvas:not(#ultron-canvas)').screenshot()
        self.assertEqual(first, second)
        self.assertEqual(self.errors, [])

    async def test_news_tracks_spoken_focus_after_clock_origin_and_has_no_buttons(self):
        await self.page.goto(self.url + '/presentation.html')
        await self.page.wait_for_function('typeof window.updateCore === "function"')
        await self.page.evaluate("document.documentElement.style.background='#090d16'")
        await self.page.evaluate("window.updateCore({presentationId:1,kind:'news',title:'NOTICIAS',narrationDriven:true,audioOrigin:25,items:[{title:'Pesquisa brasileira descobre molecula',detail:'Resumo da pesquisa'},{title:'Satelite observa o clima',detail:'Resumo do satelite'}]})")
        self.assertEqual(await self.page.locator('button,[role=button]').count(), 0)
        await self.page.evaluate("window.advancePresentation({elapsed:26,cues:['Primeira noticia: pesquisa brasileira descobre molecula.']})")
        await self.page.wait_for_timeout(500)
        await self.page.evaluate('window.advancePresentation({elapsed:28,cues:[]})')
        self.assertIn('Pesquisa brasileira', await self.page.locator('.selected h2').inner_text())
        await self.page.wait_for_timeout(600)
        self.assertEqual(await self.page.locator('.selected').get_attribute('data-index'), '0')
        await self.page.evaluate("window.advancePresentation({elapsed:32,cues:['Segunda noticia: satelite observa o clima.']})")
        self.assertEqual(await self.page.locator('.selected').get_attribute('data-index'), '1')
        await self.page.evaluate('window.advancePresentation({elapsed:35,cues:[]})')
        await self.page.wait_for_timeout(300)
        await self.page.screenshot(path=str(test_refresh_visual.BASE / 'validation/news-speech-continuity.png'))
        await self.page.evaluate('window.dismissPresentation()')
        self.assertEqual(await self.page.locator('main').evaluate('el=>el.style.opacity'), '0')
        self.assertEqual(self.errors, [])
