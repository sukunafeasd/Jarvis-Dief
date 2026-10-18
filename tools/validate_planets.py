"""Playwright visual QA on isolated local assets, no accounts or microphone."""
import functools
import http.server
import json
import sys
import tempfile
import threading
from pathlib import Path
from io import BytesIO
from PIL import Image,ImageChops
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]


def main():
    server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(http.server.SimpleHTTPRequestHandler,directory=str(ROOT/'core/spatial')))
    threading.Thread(target=server.serve_forever,daemon=True).start()
    output=Path(tempfile.mkdtemp(prefix='dief-planets-'));results=[]
    try:
        with sync_playwright() as playwright:
            browser=playwright.chromium.launch(headless=True,channel='msedge',args=['--enable-webgl','--ignore-gpu-blocklist'])
            for width,height in ((1440,900),(390,844)):
                page=browser.new_page(viewport={'width':width,'height':height},device_scale_factor=1)
                errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
                page.goto(f'http://127.0.0.1:{server.server_port}/space.html')
                page.wait_for_function("document.body.dataset.ready==='true'")
                page.wait_for_function("Object.keys(window.spaceDiagnostics().surfaceMaps).length===10",timeout=30000)
                for planet in ('earth','saturn','mars'):
                    page.evaluate("planet=>window.updateCore({staging:false,visible:true,mode:'exploration',planet,motion:'full',phase:'listening'})",planet)
                    page.wait_for_timeout(3500)
                    label=page.locator('#planet-label');bounds=label.bounding_box()
                    assert label.is_visible() and bounds and bounds['x']>=0 and bounds['y']>=0 and bounds['x']+bounds['width']<=width+1 and bounds['y']+bounds['height']<=height+1
                    image=page.screenshot(path=str(output/f'{planet}-{width}.png'))
                    pixels=Image.open(BytesIO(image)).convert('RGB');assert pixels.getextrema()[0][1]>100
                    before=page.evaluate('window.spaceDiagnostics()');page.wait_for_timeout(300)
                    after=page.evaluate('window.spaceDiagnostics()');assert after['orbitTime']>before['orbitTime']
                    results.append({'viewport':width,'planet':planet,'maps':len(after['surfaceMaps']),'moving':True,'draw_calls':after['drawCalls'],'bounds':bounds,'errors':errors})
                page.close()
            browser.close()
    finally:server.shutdown()
    result={'passed':not any(row['errors'] for row in results),'results':results,'screenshots':str(output)}
    print(json.dumps(result,ensure_ascii=False),flush=True)
    return 0 if result['passed'] else 1


if __name__=='__main__':sys.exit(main())
