import base64
import unittest
from io import BytesIO
from PIL import Image
import test_refresh_visual


class LivePinVisualTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=test_refresh_visual.RefreshVisualTests.asyncSetUp
    asyncTearDown=test_refresh_visual.RefreshVisualTests.asyncTearDown

    async def test_hidden_projection_stops_render_work_then_resumes_motion(self):
        await self.page.goto(self.url+'/presentation.html')
        await self.page.wait_for_function('typeof window.updateCore === "function"')
        await self.page.evaluate('window.updateCore({kind:"tasks",count:1,items:[{title:"Uma tarefa"}],motion:"full"})')
        await self.page.wait_for_timeout(300)
        await self.page.evaluate('window.updateCore({visible:false})')
        before=await self.page.evaluate('({time:document.body.dataset.animationTime,text:document.getElementById("details").innerText})')
        await self.page.wait_for_timeout(600)
        self.assertEqual(before,await self.page.evaluate('({time:document.body.dataset.animationTime,text:document.getElementById("details").innerText})'))
        await self.page.evaluate('window.updateCore({visible:true})')
        await self.page.wait_for_timeout(400)
        self.assertNotEqual(before['time'],await self.page.evaluate('document.body.dataset.animationTime'))
        self.assertEqual(self.errors,[])

    async def test_fused_news_keeps_spoken_selection_without_redundant_rendering(self):
        await self.page.goto(self.url+'/presentation.html')
        await self.page.wait_for_function('typeof window.updateCore === "function"')
        await self.page.evaluate('window.updateCore({kind:"news",presentationId:"fused",newsFusion:true,narrationDriven:true,items:[{title:"Primeira noticia"},{title:"Segunda noticia"}]})')
        before=await self.page.evaluate('document.body.dataset.animationTime')
        await self.page.wait_for_timeout(300)
        self.assertEqual(before,await self.page.evaluate('document.body.dataset.animationTime'))
        await self.page.evaluate('window.advancePresentation({elapsed:1,presentationId:"fused",cues:["Segunda noticia."]})')
        self.assertEqual(await self.page.locator('.selected').get_attribute('data-index'),'1')
        self.assertEqual(self.errors,[])

    async def test_motion_preference_is_observed_without_repeated_media_queries(self):
        await self.page.add_init_script('''window.mediaCalls=0;const original=window.matchMedia.bind(window);
            window.matchMedia=(...args)=>{window.mediaCalls++;return original(...args)};''')
        await self.page.goto(self.url+'/presentation.html')
        await self.page.wait_for_function('typeof window.updateCore === "function"')
        await self.page.evaluate('window.updateCore({kind:"weather",code:61,temperature:25,city:"Recife"})')
        await self.page.wait_for_timeout(300)
        before=await self.page.evaluate('window.mediaCalls')
        await self.page.wait_for_timeout(450)
        self.assertEqual(before,await self.page.evaluate('window.mediaCalls'))
        await self.page.emulate_media(reduced_motion='reduce')
        await self.page.wait_for_timeout(300)
        self.assertEqual(await self.page.evaluate('document.body.dataset.hudMotion'),'reduced')
        self.assertEqual(self.errors,[])

    async def test_live_meter_updates_without_rebuilding_or_stopping_hologram(self):
        await self.page.set_viewport_size({'width':340,'height':210})
        await self.page.goto(self.url+'/presentation.html')
        await self.page.wait_for_function('typeof window.updateCore === "function"')
        model={'kind':'system','compact':True,'framed':True,'cpu_percent':10,'ram_percent':25,
               'ram_used_gb':2,'ram_total_gb':8,'process_count':100,'uptime':'1h 0m','narrationDriven':False}
        await self.page.evaluate('m=>window.updateCore(m)',model)
        await self.page.wait_for_timeout(400)
        await self.page.evaluate('window.keptMetric=document.querySelector("#summary p")')
        first=await self.page.locator('#scene').screenshot()
        for value in (20,40,60):
            model.update(cpu_percent=value,rebuild=False)
            await self.page.evaluate('m=>window.updateCore(m)',model)
        self.assertTrue(await self.page.evaluate('window.keptMetric===document.querySelector("#summary p")'))
        self.assertIn('60%',await self.page.locator('#summary').inner_text())
        await self.page.wait_for_timeout(450)
        self.assertNotEqual(first,await self.page.locator('#scene').screenshot())
        raw=await self.page.evaluate('document.querySelector("canvas").toDataURL()')
        pixels=Image.open(BytesIO(base64.b64decode(raw.split(',')[1]))).convert('RGBA')
        self.assertGreater(sum(pixel[3]>50 for pixel in pixels.get_flattened_data()),100)
        self.assertEqual(self.errors,[])
