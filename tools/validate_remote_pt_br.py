"""Valida paginas locais em navegador isolado, sem contas nem mensagens reais."""
import asyncio
import functools
import threading
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from playwright.async_api import async_playwright

ROOT=Path(__file__).resolve().parents[1]


class Quiet(SimpleHTTPRequestHandler):
    def log_message(self,*args):pass


async def main():
    server=ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Quiet,directory=str(ROOT/'dashboard/static')))
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        async with async_playwright() as playwright:
            browser=await playwright.chromium.launch(headless=True,executable_path='C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe')
            try:
                page=await browser.new_page();errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
                await page.add_init_script("sessionStorage.setItem('jarvis_token','fixture-local-sem-conta')")
                for name in ('login','app'):
                    for width in (320,390,1200):
                        await page.set_viewport_size({'width':width,'height':800})
                        await page.goto(f'http://127.0.0.1:{server.server_port}/{name}.html')
                        await page.wait_for_timeout(100)
                        if name=='app':await page.evaluate("setStatus('sleeping')")
                        assert await page.locator('html').get_attribute('lang')=='pt-BR'
                        assert 'DIEF JARVIS' in await page.title()
                        for selector in ('.logo','.btn'):
                            for box in await page.locator(selector).all():
                                bounds=await box.bounding_box()
                                if bounds:assert bounds['x']>=-1 and bounds['x']+bounds['width']<=width+1,(name,width,selector,bounds)
                        await page.screenshot(path=str(ROOT/'validation'/f'remoto-pt-br-{name}-{width}.png'))
                assert not errors,errors
                print('6 enquadramentos locais validados; nenhum erro JavaScript.')
            finally:await browser.close()
    finally:
        server.shutdown();server.server_close();thread.join(timeout=2)


if __name__=='__main__':asyncio.run(main())
