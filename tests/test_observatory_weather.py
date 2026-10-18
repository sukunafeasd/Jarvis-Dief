"""Real renderer checks for the pinned weather layout and hidden core resize."""
import base64
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from PIL import Image
import test_refresh_visual

OUTPUT=Path(tempfile.mkdtemp(prefix='dief-observatory-weather-'))


class ObservatoryWeatherTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=test_refresh_visual.RefreshVisualTests.asyncSetUp
    asyncTearDown=test_refresh_visual.RefreshVisualTests.asyncTearDown

    async def test_weather_metrics_forecast_assets_and_motion_at_pin_sizes(self):
        await self.page.goto(self.url+'/presentation.html')
        await self.page.wait_for_function('typeof updateCore === "function"')
        model={'kind':'weather','framed':True,'compact':True,'city':'Porto Alegre, RS',
               'condition':'Chuva','temperature':20.4,'code':61,'humidity':92,'wind':12,'rain':85,
               'narrationDriven':False,'forecast':[
                   {'date':f'2026-10-{15+i}','max':23+i,'min':18,'code':code,'rain':20*i}
                   for i,code in enumerate((61,2,0,61))]}
        await self.page.evaluate('m=>updateCore(m)',model)
        for width,height in ((296,164),(320,180),(400,250),(296,140),(200,120)):
            await self.page.set_viewport_size({'width':width,'height':height})
            await self.page.wait_for_timeout(350)
            boxes=await self.page.evaluate('''() => {
                const selectors=['#summary','#symbol-space','#metrics','#details'];
                return Object.fromEntries(selectors.map(s=>{const e=document.querySelector(s);
                  return [s,getComputedStyle(e).display==='none'?null:e.getBoundingClientRect().toJSON()]}));
            }''')
            for name,box in boxes.items():
                if not box:continue
                self.assertGreaterEqual(box['top'],0,(width,height,name,box))
                self.assertLessEqual(box['bottom'],height+1,(width,height,name,box))
                self.assertGreaterEqual(box['left'],0)
                self.assertLessEqual(box['right'],width)
            if boxes['#metrics'] and boxes['#details']:
                self.assertLessEqual(boxes['#metrics']['bottom'],boxes['#details']['top'])
            if boxes['#metrics']:
                self.assertEqual(await self.page.locator('.metric strong').all_text_contents(),['85%','12 km/h','92%'])
            self.assertTrue(await self.page.locator('.forecast-icon').evaluate_all('imgs=>imgs.length===4 && imgs.every(i=>i.complete && i.naturalWidth>0)'))
            await self.page.screenshot(path=str(OUTPUT/f'weather-{width}x{height}.png'))
        await self.page.set_viewport_size({'width':296,'height':164})
        await self.page.wait_for_timeout(300)
        first=await self.page.locator('canvas').screenshot()
        await self.page.wait_for_timeout(500)
        self.assertNotEqual(first,await self.page.locator('canvas').screenshot())
        raw=await self.page.evaluate('document.querySelector("canvas").toDataURL()')
        pixels=Image.open(BytesIO(base64.b64decode(raw.split(',')[1]))).convert('RGBA')
        self.assertGreater(sum(p[3]>50 for p in pixels.get_flattened_data()),100)
        await self.page.evaluate('m=>updateCore({...m,motion:"reduced"})',model)
        await self.page.wait_for_timeout(300)
        first=await self.page.evaluate('document.querySelector("canvas").toDataURL()')
        await self.page.wait_for_timeout(300)
        self.assertEqual(first,await self.page.evaluate('document.querySelector("canvas").toDataURL()'))
        self.assertEqual(self.errors,[])

    async def test_core_recovers_from_zero_sized_preview(self):
        messages=[]
        self.page.on('console',lambda msg:messages.append(msg.text))
        await self.page.goto(self.url+'/presentation.html')
        await self.page.evaluate('''() => {const f=document.createElement('iframe');f.id='preview-core';
            f.src='./index.html';f.style.cssText='position:fixed;top:0;left:0;width:320px;height:280px;border:0';document.body.append(f);}''')
        await self.page.wait_for_function('typeof document.querySelector("#preview-core").contentWindow.updateCore === "function"')
        frame=self.page.frame(url=self.url+'/index.html')
        await frame.wait_for_function('typeof updateCore === "function"')
        await frame.evaluate('updateCore({visible:true,phase:"idle",color:"#ff303b"})')
        await self.page.wait_for_timeout(300)
        await self.page.locator('#preview-core').evaluate('e=>{e.style.width="0px";e.style.height="0px"}')
        await self.page.wait_for_timeout(250)
        await self.page.locator('#preview-core').evaluate('e=>{e.style.width="320px";e.style.height="280px"}')
        await self.page.wait_for_timeout(400)
        first=await frame.locator('canvas').screenshot()
        await self.page.wait_for_timeout(300)
        self.assertNotEqual(first,await frame.locator('canvas').screenshot())
        self.assertFalse(any('INVALID_FRAMEBUFFER' in message for message in messages),messages)
        self.assertEqual(self.errors,[])


if __name__=='__main__':
    print('Capturas:',OUTPUT,flush=True)
    unittest.main()
