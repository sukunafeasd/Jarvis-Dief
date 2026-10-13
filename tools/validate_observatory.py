"""Validacao visual local do observatorio, sem voz, contas ou dados pessoais."""
import asyncio
import base64
import functools
import io
import json
import sys
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from PIL import Image, ImageChops
from playwright.async_api import async_playwright

BASE = Path(__file__).resolve().parents[1]


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


async def main():
    output = BASE / 'validation/observatory'
    output.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(QuietHandler, directory=str(BASE/'core/spatial')))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    errors, results = [], []
    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True,
                executable_path='C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
                args=[] if '--hardware' in sys.argv else ['--enable-unsafe-swiftshader', '--use-angle=swiftshader'])
            context = await browser.new_context(viewport={'width':1366,'height':768},
                record_video_dir=str(output/'recording'),record_video_size={'width':1366,'height':768})
            page = await context.new_page()
            page.on('pageerror',lambda error:errors.append(str(error)))
            url = f'http://127.0.0.1:{server.server_port}'
            await page.goto(url+'/assets/')
            await page.set_content(f'''<style>html,body{{margin:0;background:#03060b;width:100%;height:100%;overflow:hidden}}
                iframe{{position:absolute;border:0;background:transparent}}#space{{inset:0;width:100%;height:100%}}
                #core{{left:0;top:0;width:100%;height:92%}}#clock{{position:absolute;top:18px;left:calc(50% - 90px);width:180px;text-align:center;font:14px 'Segoe UI';color:#b4ebf5;pointer-events:none}}
                #clock small{{display:block;margin-top:5px;color:#7bafbc}}</style>
                <iframe id="space" src="{url}/space.html"></iframe><iframe id="core" src="{url}/index.html"></iframe>
                <div id="clock">DIEF JARVIS<small>Observatório · demonstração visual</small></div>''')
            await page.wait_for_function('document.querySelector("#space").contentWindow.spaceDiagnostics && document.querySelector("#core").contentWindow.hologramDiagnostics')
            space = page.frame(url=url+'/space.html')
            core = page.frame(url=url+'/index.html')
            await space.wait_for_function('window.spaceDiagnostics().surfaceMaps.earth==="NASA" && window.spaceDiagnostics().surfaceMaps.moon==="NASA"')
            backend=await space.evaluate('()=>{const gl=document.querySelector("canvas").getContext("webgl2");const ext=gl.getExtension("WEBGL_debug_renderer_info");const value=ext?gl.getParameter(ext.UNMASKED_RENDERER_WEBGL):null;return {identified:Boolean(value),software:value?/swiftshader|llvmpipe|software/i.test(value):null}}')

            async def update(value):
                await space.evaluate('v=>window.updateCore(v)',value)
                await core.evaluate('v=>{window.updateEnvironment(v);window.updateCore(v)}',value)

            await update({'phase':'booting','entrance':{'at':await page.evaluate('Date.now()'),'duration':4300,'cancelAt':None}})
            await page.wait_for_timeout(500)
            await page.screenshot(path=str(output/'01-entry-distant.png'))
            await page.wait_for_timeout(4500)
            await update({'phase':'idle'})
            await page.screenshot(path=str(output/'02-assistant.png'))
            assert (await space.evaluate('window.spaceDiagnostics().travel')) == 0
            first = await space.evaluate('window.spaceDiagnostics()')
            before = await page.screenshot()
            await page.wait_for_timeout(1000)
            after = await page.screenshot()
            assert ImageChops.difference(Image.open(io.BytesIO(before)).convert('RGB'),Image.open(io.BytesIO(after)).convert('RGB')).getbbox(), 'Blank or static animation'
            await page.evaluate('document.querySelector("#core").style.cssText="left:38%;top:0;width:62%;height:92%"')
            await update({'mode':'exploration','planet':'saturn','phase':'speaking','level':.12})
            await page.wait_for_timeout(2200)
            await page.screenshot(path=str(output/'03-saturn.png'))
            assert await space.locator('#planet-label').is_visible()
            for planet in ['earth','moon','sun','mars','neptune','saturn']:
                await update({'planet':planet})
                await page.wait_for_timeout(600)
                assert await space.evaluate('window.spaceDiagnostics().planet') == planet
                if planet=='earth':
                    await page.wait_for_timeout(700)
                    await page.screenshot(path=str(output/'earth-surface.png'))
            await page.screenshot(path=str(output/'04-exploration.png'))
            await update({'mode':'analysis','planet':None,'phase':'thinking'})
            await page.wait_for_timeout(1100)
            await page.screenshot(path=str(output/'05-analysis.png'))
            await update({'mode':'execution','phase':'executing','cue':{'kind':'analysis','serial':1,'at':await page.evaluate('Date.now()')}})
            await page.wait_for_timeout(550)
            await page.screenshot(path=str(output/'06-execution.png'))
            await update({'mode':'assistant','phase':'idle','operation':None,'media':{'playing':True,'progress':30000,'duration':90000,'at':await page.evaluate('Date.now()'),'title':'Faixa sintética de validação'}})
            await page.wait_for_timeout(500)
            await update({'mode':'focus','phase':'speaking','domain':'gmail'})
            await page.wait_for_timeout(1000)
            await page.screenshot(path=str(output/'07-focus.png'))
            assert not await space.locator('#planet-label').is_visible()
            await page.evaluate('document.querySelector("#core").style.cssText="left:0;top:0;width:100%;height:92%"')
            await update({'mode':'assistant','phase':'idle','domain':None})
            for width,height in ([(1366,768)] if '--quick' in sys.argv else [(800,700),(390,844),(1920,1080),(3840,2160)]):
                await page.set_viewport_size({'width':width,'height':height})
                await page.wait_for_timeout(550)
                await page.screenshot(path=str(output/f'viewport-{width}.png'))
                pixels=await space.evaluate('()=>{const c=document.querySelector("canvas");return {width:c.width,height:c.height,data:c.toDataURL()}}')
                assert pixels['width'] > 0 and len(pixels['data']) > 10000
                image=Image.open(io.BytesIO(base64.b64decode(pixels['data'].split(',')[1]))).convert('RGB')
                assert max(high-low for low,high in image.getextrema())>80, 'Blank WebGL pixels'
                results.append({'viewport':[width,height],'space':await space.evaluate('window.spaceDiagnostics()')})
            await page.set_viewport_size({'width':1366,'height':768})
            await page.wait_for_timeout(500)
            await update({'visible':False})
            frozen = await space.evaluate('window.spaceDiagnostics().frames')
            await page.wait_for_timeout(500)
            assert frozen == await space.evaluate('window.spaceDiagnostics().frames')
            await update({'visible':True,'motion':'reduced','mode':'exploration','planet':'earth'})
            await page.evaluate('document.querySelector("#core").style.cssText="left:38%;top:0;width:62%;height:92%"')
            await page.wait_for_timeout(300)
            frozen = await space.evaluate('window.spaceDiagnostics()')
            await page.wait_for_timeout(600)
            stopped = await space.evaluate('window.spaceDiagnostics()')
            # A queued viewport resize can redraw once; it must never advance motion or restart the loop.
            assert frozen['orbitTime'] == stopped['orbitTime'], (frozen,stopped)
            assert stopped['frames'] <= frozen['frames']+3, (frozen,stopped)
            assert not await space.evaluate('window.spaceDiagnostics().scheduled')
            await page.screenshot(path=str(output/'08-reduced-motion.png'))
            await update({'motion':'full','mode':'assistant','planet':None,'phase':'idle'})
            baseline = await space.evaluate('window.spaceDiagnostics()')
            for i in range(30):
                await update({'mode':'exploration' if i%2 else 'focus','planet':'earth','cue':{'kind':'attention','serial':i,'at':await page.evaluate('Date.now()')}})
            await page.wait_for_timeout(800)
            ending = await space.evaluate('window.spaceDiagnostics()')
            assert ending['textures'] == baseline['textures']
            assert ending['geometries'] == baseline['geometries']
            rig = await space.evaluate('async()=>{const r=await import("./environment-rig.mjs");const e={at:1000,duration:4000,cancelAt:2000};return [r.entranceDistance(e,2000),r.entranceDistance(e,2320),r.entranceDistance(e,1100,true)]}')
            assert rig[0]>0 and rig[1:] == [0,0]
            results.append({'baseline':first,'after_switches':ending,'errors':errors,'backend':backend,
                            'hidden_suspended':True,'reduced_suspended':True,'rig_cancelled':True})
            video = page.video
            await context.close()
            await video.save_as(str(BASE/'validation/observatory-demo.webm'))
            await browser.close()
        if errors:
            raise RuntimeError('\n'.join(errors))
        report='report-hardware.json' if '--hardware' in sys.argv else 'report.json'
        (output/report).write_text(json.dumps(results,indent=2),encoding='utf-8')
        print('Observatory: animated pixels, viewports, six planets, modes, cancellation, suspension and stable resources passed.')
    finally:
        server.shutdown();server.server_close();thread.join(timeout=2)


if __name__ == '__main__':
    asyncio.run(main())
