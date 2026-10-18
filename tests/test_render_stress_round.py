"""Real local WebGL state churn, pixel probes and resource budgets."""
from io import BytesIO
from pathlib import Path
import tempfile
import unittest
from PIL import Image,ImageStat
import test_refresh_visual

OUTPUT=Path(tempfile.mkdtemp(prefix='dief-render-stress-'))


class RenderStressTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=test_refresh_visual.RefreshVisualTests.asyncSetUp
    asyncTearDown=test_refresh_visual.RefreshVisualTests.asyncTearDown

    async def test_twelve_cold_renderer_pages_initialize_without_javascript_errors(self):
        for index in range(12):
            page=await self.browser.new_page(viewport={'width':800,'height':600})
            errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
            try:
                document='presentation.html' if index%2==0 else 'index.html'
                await page.goto(self.url+'/'+document)
                await page.wait_for_function('typeof window.updateCore==="function" || Boolean(document.body.dataset.error)',timeout=60000)
                self.assertEqual(errors,[],(index,errors))
                self.assertTrue(await page.evaluate('typeof window.updateCore==="function"'))
                await page.evaluate('window.updateCore({kind:"weather",temperature:23,visible:true,motion:"reduced"})')
                await page.wait_for_function('document.body.dataset.ready==="true"',timeout=60000)
                self.assertFalse(await page.evaluate('Boolean(document.body.dataset.error)'))
            finally:await page.close()

    async def test_repeated_core_modes_resize_and_visibility_do_not_grow_resources(self):
        await self.page.goto(self.url+'/index.html')
        await self.page.wait_for_function('document.body.dataset.ready==="true"')
        await self.page.evaluate('updateCore({motion:"reduced",visible:true})')
        await self.page.evaluate('''()=>{
            for(const mode of ['assistant','analysis','execution','focus','exploration']){
                updateCore({phase:'speaking',level:.5,motion:'reduced',visible:true});
                updateEnvironment({mode});
            }
            updateCore({phase:'idle',level:0,motion:'reduced',visible:true});
            updateEnvironment({mode:'assistant'});
        }''')
        baseline=await self.page.evaluate('hologramDiagnostics()')
        for width,height in ((1366,768),(800,600),(390,844)):
            await self.page.set_viewport_size({'width':width,'height':height})
            result=await self.page.evaluate('''()=>{
                const phases=['idle','listening','thinking','executing','speaking'];
                const modes=['assistant','analysis','execution','focus','exploration'];
                for(let i=0;i<200;i++){
                    updateCore({phase:phases[i%5],level:(i%10)/10,motion:'reduced',visible:i%9!==0});
                    updateEnvironment({mode:modes[i%5]});
                }
                updateCore({phase:'idle',level:0,motion:'reduced',visible:true});
                updateEnvironment({mode:'assistant'});
                return hologramDiagnostics();
            }''')
            self.assertTrue(result['coreVisible']);self.assertEqual(result['geometries'],baseline['geometries'])
            self.assertEqual(result['textures'],baseline['textures'])
            shot=await self.page.screenshot(path=str(OUTPUT/f'core-{width}.png'),omit_background=True)
            pixels=Image.open(BytesIO(shot)).convert('RGBA')
            self.assertGreater(sum(pixel[3]>30 for pixel in pixels.get_flattened_data()),500)
        self.assertEqual(self.errors,[])

    async def test_ultron_repeated_activation_remains_world_fixed_and_reduced_motion_stops(self):
        await self.page.goto(self.url+'/space.html')
        await self.page.wait_for_function('document.body.dataset.ready==="true"',timeout=60000)
        await self.page.evaluate('updateCore({motion:"reduced"})')
        initial=await self.page.evaluate('ultronDiagnostics()')
        for width,height in ((1366,768),(390,844)):
            await self.page.set_viewport_size({'width':width,'height':height})
            for index in range(20):
                await self.page.evaluate('i=>updateUltron({state:{phase:i%2?"idle":"active",telemetry:{cpu_percent:i},findings:[]},result:{mode:"diagnostic"}})',index)
            await self.page.evaluate('updateUltron({state:{phase:"active",telemetry:{cpu_percent:23},findings:[]},result:{mode:"diagnostic"}});advanceUltron({elapsed:.2,cues:["CPU em 23 por cento."]})')
            state=await self.page.evaluate('ultronDiagnostics()')
            self.assertEqual(state['worldPosition'],initial['worldPosition'])
            self.assertEqual(state['worldScale'],initial['worldScale'])
            self.assertEqual(state['aperture'],1)
            self.assertLessEqual(state['geometries'],initial['geometries']+16)
            frames=state['frames'];await self.page.wait_for_timeout(300)
            self.assertEqual((await self.page.evaluate('ultronDiagnostics()'))['frames'],frames)
            self.assertIn('23%',await self.page.locator('#ultron-projection').inner_text())
            self.assertEqual(await self.page.locator('.ultron-reading').evaluate('el=>getComputedStyle(el).animationName'),'none')
            shot=await self.page.screenshot(path=str(OUTPUT/f'ultron-{width}.png'))
            self.assertGreater(max(ImageStat.Stat(Image.open(BytesIO(shot)).convert('RGB')).stddev),5)
            before_resize=await self.page.evaluate('ultronDiagnostics().frames')
            await self.page.set_viewport_size({'width':width-20,'height':height})
            await self.page.wait_for_function('count=>ultronDiagnostics().frames>count',arg=before_resize)
            after_resize=await self.page.evaluate('ultronDiagnostics().frames')
            await self.page.wait_for_timeout(200)
            self.assertEqual(await self.page.evaluate('ultronDiagnostics().frames'),after_resize)
        self.assertEqual(self.errors,[])


if __name__=='__main__':
    print('Capturas:',OUTPUT,flush=True);unittest.main()
