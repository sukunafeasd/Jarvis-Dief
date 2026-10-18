"""Isolated rendering of integrated ULTRON assets; no accounts or PC actions."""
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
    output=Path(tempfile.mkdtemp(prefix='dief-ultron-integrated-'));results=[]
    snapshot={'phase':'active','scan':{'running':False,'progress':100},'telemetry':{'cpu_percent':17,'memory_percent':43,'disk_percent':52,'process_count':180},'findings':[],'vault_count':2}
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True,channel='msedge',args=['--enable-webgl','--ignore-gpu-blocklist'])
            for width,height in ((1440,900),(390,844)):
                page=browser.new_page(viewport={'width':width,'height':height});errors=[]
                page.on('pageerror',lambda e:errors.append(str(e)))
                page.on('console',lambda m:errors.append(m.text) if m.type=='error' else None)
                page.goto(f'http://127.0.0.1:{server.server_port}/space.html')
                page.wait_for_function('Boolean(window.ultronDiagnostics)',timeout=45000)
                page.evaluate('window.updateCore({staging:false,visible:true,motion:"full",mode:"assistant",phase:"idle"})')
                page.wait_for_timeout(1000);dormant=page.evaluate('window.ultronDiagnostics()')
                assert dormant['phase']=='idle' and dormant['embedded'] and dormant['basaltTiles']==64
                page.screenshot(path=str(output/f'dormant-{width}.png'))
                page.evaluate('s=>window.updateUltron({state:s,result:{mode:"diagnostic"}})',snapshot)
                page.wait_for_timeout(2400)
                assert '17%' not in page.locator('#ultron-projection').inner_text(),'Data revealed ahead of actual speech'
                page.evaluate('window.advanceUltron({cues:["CPU em 17 por cento. Memoria em 43 por cento. Disco em 52 por cento."]})')
                page.wait_for_timeout(650)
                assert '17%' in page.locator('#ultron-projection').inner_text()
                page.evaluate('window.advanceUltron({elapsed:2,cues:[]})')
                changed={**snapshot,'telemetry':{**snapshot['telemetry'],'cpu_percent':99}}
                page.evaluate('s=>window.updateUltron({state:s,result:null})',changed)
                assert '17%' in page.locator('#ultron-projection').inner_text() and '99%' not in page.locator('#ultron-projection').inner_text(),'Polling replaced narrated values'
                bounds=page.locator('#ultron-projection').bounding_box()
                assert bounds and bounds['x']>=0 and bounds['x']+bounds['width']<=width+1
                first=page.screenshot(path=str(output/f'active-{width}.png'))
                page.wait_for_timeout(400);second=page.screenshot()
                assert ImageChops.difference(Image.open(BytesIO(first)).convert('RGB'),Image.open(BytesIO(second)).convert('RGB')).getbbox(),'Planet does not move'
                page.evaluate('window.updateUltron({state:{phase:"idle"},result:{mode:"deactivation"}})')
                page.wait_for_timeout(1200);assert page.locator('#ultron-projection').is_hidden()
                assert not errors,errors
                results.append({'width':width,'passed':True,'bounds':bounds,'dormant':dormant})
                page.close()
            browser.close()
    finally:server.shutdown()
    print(json.dumps({'passed':True,'results':results,'screenshots':str(output)}),flush=True)

if __name__=='__main__':main()
