"""Record the local presentation layer with synthetic data only."""
import asyncio
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
    server=ThreadingHTTPServer(('127.0.0.1',0),functools.partial(QuietHandler,directory=str(BASE/'core/spatial')))
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        async with async_playwright() as pw:
            edge=Path('C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe')
            browser=await pw.chromium.launch(headless=True,args=['--enable-unsafe-swiftshader','--use-angle=swiftshader'],**({'executable_path':str(edge)} if edge.exists() else {}))
            context=await browser.new_context(viewport={'width':900,'height':600},record_video_dir=str(BASE/'validation/motion'),record_video_size={'width':900,'height':600})
            page=await context.new_page()
            await page.goto(f'http://127.0.0.1:{server.server_port}/presentation.html')
            await page.wait_for_function('typeof window.updateCore === "function"')
            await page.evaluate("document.documentElement.style.background=\"#05090d url('./assets/deep-space.png') center/cover\"")
            models=[{'kind':'weather','title':'CLIMA · DEMONSTRAÇÃO','city':'Porto Alegre','temperature':19,'code':61,'condition':'Chuva','rain':80,'wind':12,'humidity':74},
                    {'kind':'gmail','title':'GMAIL · DEMONSTRAÇÃO','items':[{'title':'Reunião confirmada','detail':'Equipe de demonstração'},{'title':'Documento disponível','detail':'Projeto de demonstração'}]},
                    {'kind':'whatsapp','title':'WHATSAPP · DEMONSTRAÇÃO','items':[{'title':'Grupo de estudo','detail':'Revisamos o material amanhã?','value':'2'}]},
                    {'kind':'tasks','title':'TAREFAS · DEMONSTRAÇÃO','count':3,'items':[{'title':'Revisar documento','priority':'high'},{'title':'Preparar reunião'},{'title':'Organizar materiais'}]},
                    {'kind':'calendar','title':'AGENDA · DEMONSTRAÇÃO','items':[{'title':'Reunião de revisão','due':'2026-10-12T14:00'}]},
                    {'kind':'system','title':'SISTEMA · DEMONSTRAÇÃO','cpu_percent':35,'ram_percent':62,'gpu_percent':18},
                    {'kind':'memory','title':'MEMÓRIA · DEMONSTRAÇÃO','items':[{'title':'Preferência registrada','detail':'Contexto de demonstração'}]},
                    {'kind':'files','title':'ARQUIVOS · DEMONSTRAÇÃO','items':[{'title':'Documento de teste.pdf'}]},
                    {'kind':'search','title':'BUSCA · DEMONSTRAÇÃO','items':[{'title':'Resultado de teste'}]},
                    {'kind':'data','title':'Caminhada','source':'DADOS SINTÉTICOS','items':[{'title':'Passos de teste','value':'2.483'},{'title':'Distância de teste','value':'0,13 km'}]},
                    {'kind':'data','title':'Energia','source':'DADOS SINTÉTICOS','items':[{'title':'Valor de teste','value':'78%'}]},
                    {'kind':'data','title':'Calorias','source':'DADOS SINTÉTICOS','items':[{'title':'Gasto de teste','value':'182 kcal'}]}]
            for index,model in enumerate(models):
                await page.evaluate('value=>window.updateCore({...value,narrationDriven:false,presentationId:performance.now()})',model)
                await page.wait_for_timeout(2700)
                if index==0:
                    await page.set_viewport_size({'width':274,'height':125})
                    await page.evaluate('value=>window.updateCore({...value,compact:true,narrationDriven:false})',model)
                    await page.wait_for_timeout(1600)
                    await page.set_viewport_size({'width':900,'height':600})
            video=page.video
            await context.close()
            await video.save_as(str(BASE/'validation/presentation-motion.webm'))
            await browser.close()
            print('Local presentation recording:',BASE/'validation/presentation-motion.webm')
    finally:
        server.shutdown();server.server_close();thread.join(timeout=2)


asyncio.run(main())
