"""Capture primary-core fusion and the preserved front view with synthetic news."""
import asyncio
import base64
import functools
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from playwright.async_api import async_playwright

BASE=Path(__file__).resolve().parents[1]


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self,*args):
        pass


async def main():
    output=BASE/'validation/news-core'
    output.mkdir(parents=True,exist_ok=True)
    server=ThreadingHTTPServer(('127.0.0.1',0),functools.partial(QuietHandler,directory=str(BASE/'core/spatial')))
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    errors=[]
    try:
        async with async_playwright() as pw:
            browser=await pw.chromium.launch(headless=True,
                executable_path='C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
                args=['--enable-unsafe-swiftshader','--use-angle=swiftshader'])
            context=await browser.new_context(viewport={'width':1200,'height':900},
                record_video_dir=str(output/'recording'),record_video_size={'width':1200,'height':900})
            page=await context.new_page();page.on('pageerror',lambda error:errors.append(str(error)))
            url=f'http://127.0.0.1:{server.server_port}'
            await page.goto(url+'/index.html')
            await page.wait_for_function('typeof window.updateNewsCore === "function"')
            await page.evaluate("document.documentElement.style.background=\"#05090d url('./assets/deep-space.png') center/cover\"")
            image='data:image/png;base64,'+base64.b64encode((BASE/'core/spatial/assets/deep-space.png').read_bytes()).decode()
            model={'kind':'news','title':'NOTÍCIAS · DEMONSTRAÇÃO','presentationId':20261012,
                'narrationDriven':True,'newsFusion':True,'items':[
                    {'title':title,'category':category,'source':'Dados sintéticos · demonstração visual',
                     'image':image,'detail':'Conteúdo de teste para validar a apresentação, não é uma notícia real.'}
                    for title,category in [('Pesquisa sobre o clima global','MUNDO'),
                        ('Nova descoberta na exploração espacial','CIÊNCIA'),
                        ('Avanços no estudo de inteligência artificial','TECNOLOGIA')]]}
            await page.evaluate('u=>{const f=document.createElement("iframe");f.id="front";f.src=u;f.style.cssText="position:absolute;inset:15%;width:70%;height:70%;border:0;background:transparent";document.body.append(f)}',url+'/presentation.html')
            await page.wait_for_function('typeof document.getElementById("front").contentWindow.updateCore === "function"')
            frame=page.frame(url=url+'/presentation.html')
            await frame.evaluate('m=>window.updateCore(m)',model)
            await page.evaluate('window.updateCore({phase:"speaking",level:.16,color:"#ff303b",projection:true})')
            await page.evaluate('m=>window.updateNewsCore({id:m.presentationId,items:m.items,focus:0,mode:"fused"})',model)
            await page.wait_for_function('window.newsCoreDiagnostics().images===3')
            await page.wait_for_timeout(1800)
            for index,ordinal in enumerate(['primeira','segunda','terceira']):
                await frame.evaluate('(v)=>window.advancePresentation(v)',
                    {'elapsed':index*4+.2,'cues':[f'A {ordinal} notícia. '+model['items'][index]['title']]})
                focus=await frame.evaluate('Number(document.querySelector(".record.selected").dataset.index)')
                await page.evaluate('v=>window.updateNewsCore(v)',
                    {'id':model['presentationId'],'items':model['items'],'focus':focus,'mode':'fused'})
                await page.wait_for_timeout(2400)
                if index==1:
                    await frame.evaluate('window.cancelPresentation()')
                    await page.evaluate('v=>window.updateNewsCore({...v,mode:"paused"})',
                        {'id':model['presentationId'],'items':model['items'],'focus':focus})
                    await page.wait_for_timeout(900)
                    await frame.evaluate('window.resumePresentation()')
                if index==2:
                    await page.screenshot(path=str(output/'news-fused-demo.png'))
            await frame.evaluate('window.finishPresentation();window.setNewsFusion(false)')
            await page.evaluate('v=>window.updateNewsCore(v)',
                {'id':model['presentationId'],'items':model['items'],'focus':2,'mode':'front'})
            await page.wait_for_timeout(2200)
            await page.screenshot(path=str(output/'news-front-demo.png'))
            await page.evaluate('window.updateCore({phase:"idle",projection:false});window.updateNewsCore(null)')
            await frame.evaluate('window.dismissPresentation()')
            await page.wait_for_timeout(1000)
            video=page.video
            await context.close()
            await video.save_as(str(BASE/'validation/news-core-fusion.webm'))
            await browser.close()
        if errors:
            raise RuntimeError('\n'.join(errors))
        print('Recorded primary core and existing front presentation without browser errors.')
    finally:
        server.shutdown();server.server_close();thread.join(timeout=2)


asyncio.run(main())
