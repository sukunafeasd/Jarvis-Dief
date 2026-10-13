"""Sequencia visual isolada, sem microfone, contas ou chamadas de IA."""
import asyncio
import base64
import functools
import json
import threading
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from playwright.async_api import async_playwright

BASE=Path(__file__).resolve().parents[1]
OUTPUT=BASE/'validation/interface-audit'


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self,*args):pass


async def main():
    OUTPUT.mkdir(parents=True,exist_ok=True)
    server=ThreadingHTTPServer(('127.0.0.1',0),functools.partial(QuietHandler,directory=str(BASE/'core/spatial')))
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    errors=[]
    try:
        async with async_playwright() as pw:
            browser=await pw.chromium.launch(headless=True,executable_path='C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',args=['--enable-unsafe-swiftshader','--use-angle=swiftshader'])
            context=await browser.new_context(viewport={'width':1366,'height':768},record_video_dir=str(OUTPUT),record_video_size={'width':1366,'height':768})
            page=await context.new_page();page.on('pageerror',lambda error:errors.append(str(error)))
            await page.goto(f'http://127.0.0.1:{server.server_port}/presentation.html')
            await page.wait_for_function('typeof window.updateCore === "function"')
            await page.evaluate("document.documentElement.style.background=\"#03070a url('./assets/deep-space.png') center/cover\"")
            photo='data:image/jpeg;base64,'+base64.b64encode((BASE/'core/spatial/assets/moon-nasa.jpg').read_bytes()).decode()
            news={'kind':'news','title':'VALIDACAO DE NOTICIAS','presentationId':'audit-news','narrationDriven':True,
                  'items':[{'title':'Pesquisa lunar de demonstracao','source':'Dados sinteticos','image':photo},
                           {'title':'Exploracao espacial de demonstracao','source':'Dados sinteticos','image':photo}]}

            async def play(start,duration,cue=None,identity='audit-news'):
                for step in range(int(duration*10)):
                    await page.evaluate('b=>window.advancePresentation(b)',{'elapsed':start+step*.1,'cues':[cue] if cue and step==0 else [],'presentationId':identity})
                    await page.wait_for_timeout(100)

            await page.evaluate('m=>window.updateCore(m)',news)
            await page.wait_for_timeout(1000)
            await play(0,4,'Primeira noticia.')
            await page.evaluate('window.cancelPresentation()')
            await play(4,1,'Segunda noticia.')
            assert await page.locator('.selected').get_attribute('data-index')=='0'
            await page.screenshot(path=str(OUTPUT/'sequence-paused.png'))
            await page.evaluate('window.resumePresentation()')
            await play(0,4,'Segunda noticia.')
            assert await page.locator('.selected').get_attribute('data-index')=='1'
            await page.evaluate('window.finishPresentation()')
            await page.wait_for_timeout(2500)
            await page.screenshot(path=str(OUTPUT/'sequence-completed.png'))
            weather={'kind':'weather','title':'CLIMA DE TESTE','presentationId':'audit-weather','narrationDriven':True,
                     'city':'Porto Alegre','temperature':19,'code':61,'condition':'Chuva','rain':80,'wind':12,'humidity':70}
            await page.evaluate('m=>window.updateCore(m)',weather)
            await play(0,4,'Chuva e vento em Porto Alegre.',identity='audit-weather')
            await page.evaluate('window.advancePresentation({elapsed:20,cues:["Segunda noticia."],presentationId:"audit-news"})')
            assert await page.evaluate('document.body.dataset.kind')=='weather'
            await page.evaluate('window.finishPresentation()')
            await page.wait_for_timeout(2000)
            await page.screenshot(path=str(OUTPUT/'sequence-weather.png'))
            assert not errors,errors
            video=page.video
            await context.close()
            await video.save_as(str(OUTPUT/'synchronization-demo.webm'))
            await browser.close()
            print(json.dumps({'ok':True,'voice':'simulated-playback','errors':errors,'video':str(OUTPUT/'synchronization-demo.webm')}))
    finally:
        server.shutdown();server.server_close();thread.join(timeout=2)


if __name__=='__main__':asyncio.run(main())
