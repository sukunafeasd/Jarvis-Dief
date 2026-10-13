import asyncio
import functools
import hashlib
import threading
import unittest
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


class RefreshVisualTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        from playwright.async_api import async_playwright
        self.server=ThreadingHTTPServer(('127.0.0.1',0),functools.partial(QuietHandler,directory=str(BASE/'core/spatial')))
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.pw=await async_playwright().start()
        edge=Path('C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe')
        self.browser=await self.pw.chromium.launch(headless=True,args=['--enable-unsafe-swiftshader','--use-angle=swiftshader'],**({'executable_path':str(edge)} if edge.exists() else {}))
        self.page=await self.browser.new_page(viewport={'width':1200,'height':900})
        self.errors=[];self.page.on('pageerror',lambda error:self.errors.append(str(error)))
        self.url=f'http://127.0.0.1:{self.server.server_port}'

    async def asyncTearDown(self):
        await self.browser.close();await self.pw.stop()
        self.server.shutdown();self.server.server_close();self.thread.join(timeout=2)

    async def test_status_layout_updates_without_second_hologram_or_overlap(self):
        await self.page.goto(self.url+'/presentation.html')
        await self.page.wait_for_function('typeof window.updateCore === "function"')
        model={'kind':'status','id':'daily-refresh','title':'ATUALIZANDO MEU CONTEXTO','completed':2,'total':6,
               'source':'Consultas reais · 14:00','narrationDriven':False,
               'items':[{'title':name,'detail':'Consulta concluída' if i<2 else 'Consultando fonte','status':'ok' if i<2 else 'working'} for i,name in enumerate(['Notícias','Agenda local','Tarefas locais','Clima','Sistema','Gmail'])]}
        for width,height in ((1200,900),(640,480)):
            await self.page.set_viewport_size({'width':width,'height':height})
            await self.page.evaluate('value=>window.updateCore(value)',model)
            await self.page.wait_for_timeout(200)
            self.assertEqual(await self.page.locator('.check-row').count(),6)
            summary=await self.page.locator('#summary').bounding_box()
            details=await self.page.locator('#details').bounding_box()
            footer=await self.page.locator('footer').bounding_box()
            self.assertLessEqual(summary['y']+summary['height'],details['y'])
            self.assertLessEqual(details['y']+details['height'],footer['y'])
            sizes = await self.page.locator('#details').evaluate('el=>({scroll:el.scrollHeight,height:el.clientHeight,rows:[...el.children].map(row=>row.getBoundingClientRect().height)})')
            self.assertLessEqual(sizes['scroll'], sizes['height']+1, f'{width}x{height}: {sizes}')
            await self.page.screenshot(path=str(BASE/f'validation/context-refresh-{width}.png'))
        model['items'][2].update(status='warning',detail='Indisponível nesta atualização');model['completed']=3
        await self.page.evaluate('value=>window.updateCore(value)',model)
        self.assertEqual(await self.page.locator('.check-row[data-state="warning"]').count(),1)
        self.assertIn('3 / 6',await self.page.locator('#summary').inner_text())
        self.assertEqual(self.errors,[])
        await self.page.set_viewport_size({'width':1200,'height':900})
        await self.page.goto(self.url+'/index.html')
        await self.page.wait_for_function('typeof window.updateCore === "function"')
        await self.page.evaluate('window.updateCore({phase:"thinking",color:"#54d5d1",visible:true,projection:true,level:0})')
        await self.page.evaluate("url=>{const frame=document.createElement('iframe');frame.id='projection';frame.src=url;frame.style.cssText='position:absolute;left:15%;top:15%;width:70%;height:70%;border:0;background:transparent';document.body.append(frame);}",self.url+'/presentation.html')
        await self.page.wait_for_function("typeof document.querySelector('#projection').contentWindow.updateCore === 'function'")
        projected = self.page.frame(url=self.url+'/presentation.html')
        await projected.wait_for_function('typeof window.updateCore === "function"')
        await projected.evaluate('value=>window.updateCore(value)',model)
        await self.page.wait_for_timeout(500)
        composite=await self.page.screenshot(path=str(BASE/'validation/context-refresh-in-core.png'))
        from PIL import Image
        from io import BytesIO
        image=Image.open(BytesIO(composite)).convert('RGB')
        self.assertEqual(image.getpixel((186,141)),image.getpixel((175,141)))
        await self.page.evaluate("document.documentElement.style.background='#090d16'")
        await self.page.screenshot(path=str(BASE/'validation/context-refresh-dark-core.png'))

    async def test_primary_core_is_nonblank_and_moves_during_boot(self):
        await self.page.goto(self.url+'/index.html')
        await self.page.wait_for_function('typeof window.updateCore === "function"')
        await self.page.evaluate('window.updateCore({phase:"booting",color:"#54d5d1",visible:true,level:0,resting:false})')
        await self.page.wait_for_timeout(600)
        first=await self.page.locator('canvas').screenshot()
        await self.page.wait_for_timeout(500)
        second=await self.page.locator('canvas').screenshot()
        from PIL import Image
        from io import BytesIO
        pixels=Image.open(BytesIO(second)).convert('RGB')
        self.assertGreater(sum(max(pixel)-min(pixel)>25 for pixel in list(pixels.getdata())),100)
        self.assertNotEqual(hashlib.sha256(first).digest(),hashlib.sha256(second).digest())
        await self.page.screenshot(path=str(BASE/'validation/boot-core.png'))
        self.assertEqual(self.errors,[])
