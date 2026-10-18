"""Real local render checks for world anchoring and entry frame progression."""
import functools
import http.server
import json
import sys
import tempfile
import threading
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageChops
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from core.forge_status import project_snapshot


def pixels(data):
    return Image.open(BytesIO(data)).convert('RGB')


def main():
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(
        http.server.SimpleHTTPRequestHandler, directory=str(ROOT / 'core/spatial')))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    output = Path(tempfile.mkdtemp(prefix='dief-entry-fixes-'))
    results = []
    base = f'http://127.0.0.1:{server.server_port}'
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, channel='msedge', args=['--enable-webgl', '--ignore-gpu-blocklist'])
            for width, height in ((1440, 900), (390, 844)):
                page = browser.new_page(viewport={'width': width, 'height': height})
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.route('**/*', lambda route: route.continue_() if route.request.url.startswith(base) else route.abort())
                page.goto(base + '/index.html')
                page.wait_for_function('window.hologramDiagnostics && document.body.dataset.ready === "true"')
                page.wait_for_timeout(500)
                origin = page.evaluate('window.forgeTransitionDiagnostics().camera')
                page.evaluate('''() => {
                    window.samples=[];window.entry=window.enterForgeTransition({reduced:false});
                    const record=()=>{samples.push({t:performance.now(),...forgeTransitionDiagnostics()});
                        if(forgeTransitionPhase!=="blackout")requestAnimationFrame(record)};record();
                }''')
                previous = page.screenshot()
                changes = []
                for i in range(4):
                    page.wait_for_timeout(300)
                    current = page.screenshot(path=str(output / f'core-{width}-{i}.png'))
                    changes.append(bool(ImageChops.difference(pixels(previous), pixels(current)).getbbox()))
                    previous = current
                assert all(changes), ('Frozen entry pixels', changes)
                samples = page.evaluate('samples')
                assert samples[-1]['camera'][2] < origin[2] - .05, 'Entry waits before camera travel'
                assert all(b['camera'][2] <= a['camera'][2] + 1e-6 for a, b in zip(samples, samples[1:])), (
                    'Camera reverses', page.evaluate('window.forgeTransitionError'),
                    [(a,b) for a,b in zip(samples,samples[1:]) if b['camera'][2] > a['camera'][2] + 1e-6])
                gaps = [b['t']-a['t'] for a,b in zip(samples,samples[1:])]
                page.wait_for_function('forgeTransitionPhase==="blackout"')
                assert pixels(page.screenshot()).getextrema() == ((0,0),(0,0),(0,0))
                assert page.evaluate('exitForgeTransition({reduced:true}).then(r=>r.status)') == 'completed'
                page.goto(base + '/forja.html')
                page.wait_for_function('forgeReady')
                page.evaluate('''() => {updateForge({activities:[
                    {id:"old",title:"Etapa anterior",detail:"Concluido",status:"completed"},
                    {id:"cmd",title:"Validando a criacao",detail:"Em andamento",status:"running"},
                    {id:"msg",title:"Preparando a criacao",detail:"Aguardando sua resposta",status:"waiting"},
                    {id:"files",title:"Atualizando arquivos",detail:"Concluido",status:"completed"}
                ]});window.entry=beginForgeEntrance({reduced:false});}''')
                page.wait_for_timeout(500)
                opacity = page.locator('#forgePanel').evaluate('(el)=>Number(getComputedStyle(el).opacity)')
                assert opacity > .03, ('Panel delayed', opacity)
                page.screenshot(path=str(output / f'panel-entry-{width}.png'))
                page.wait_for_function('forgeScenePhase==="ready"')
                text = page.locator('#stepsContainer').inner_text()
                assert 'Em andamento' in text and 'Concluido' in text
                assert page.locator('.step-item').count() == 3 and 'Etapa anterior' not in text
                assert page.locator('.step-item.waiting').count() == 1
                assert not any(raw in text for raw in ('powershell', 'exit=', 'partial', 'C:/', 'File changes'))
                assert page.locator('button').count() == 0
                page.locator('#forgePrompt').fill('Crie um planeta')
                page.locator('#forgePrompt').press('Shift+Enter')
                assert '\n' in page.locator('#forgePrompt').input_value()
                page.locator('#forgePrompt').press('Enter')
                assert page.evaluate('JSON.parse(decodeURIComponent(location.hash.slice(15))).prompt') == 'Crie um planeta'
                page.keyboard.press('F11')
                assert page.evaluate('location.hash.startsWith("#window-fullscreen-")')
                for state, expected in (({'phase':'running','activities':[
                    {'title':'Command execution','detail':'powershell.exe Get-Process | exit=None','status':'running'},
                    {'title':'Agent message','detail':'partial delta {','status':'streaming'}]}, 'running'),
                    ({'phase':'idle','preview_validation':'pending'}, 'waiting'),
                    ({'phase':'idle','generation_verified':True}, 'completed'),
                    ({'phase':'error','error':'O projeto foi preservado.'}, 'failed')):
                    projected = project_snapshot({'authenticated':True, **state})
                    page.evaluate('value=>updateForge(value)', projected)
                    assert page.locator('.step-item').count() == 1
                    assert page.locator('.step-item.' + expected).count() == 1
                    assert page.locator('.step-name').inner_text() == projected['activities'][0]['title']
                    assert not any(raw in page.locator('#stepsContainer').inner_text() for raw in ('powershell', 'exit=', 'partial delta'))
                page.screenshot(path=str(output / f'panel-{width}.png'))
                page.route('**/world-test.html', lambda route: route.fulfill(content_type='text/html', body='''
                    <html><body style="margin:0;background:black"><canvas id="world" style="width:100vw;height:100vh"></canvas>
                    <script type="module">import {UltronWorld} from './ultron/ultron.mjs';
                    window.world=new UltronWorld(document.querySelector('canvas'),{embedded:true});
                    world.host({visible:true,staging:false,motion:'full'});await world.init();</script></body></html>'''))
                page.goto(base + '/world-test.html')
                page.wait_for_function('window.world?.ready && world.frames>3')
                position = page.evaluate('world.root.position.toArray()')
                first = page.locator('canvas').screenshot(path=str(output / f'ultron-idle-{width}.png'))
                assert pixels(first).getbbox(), 'Ultron is blank'
                page.evaluate('world.setState("active",[])')
                page.wait_for_timeout(1800)
                final = page.locator('canvas').screenshot(path=str(output / f'ultron-active-{width}.png'))
                assert page.evaluate('world.root.position.toArray()') == position, 'Planet follows camera'
                assert page.evaluate('world.open') > .5
                assert ImageChops.difference(pixels(first),pixels(final)).getbbox(), 'Ultron entry pixels frozen'
                bounds = pixels(final).getbbox()
                assert bounds[0] > 0 and bounds[2] < width, ('Ultron clipped at viewport edge', bounds)
                assert not errors, errors
                results.append({'width':width,'corePixelChanges':changes,'sampleCount':len(samples),
                                'maxFrameGapMs':round(max(gaps),1),'panelEarlyOpacity':opacity,'ultronWorldPosition':position})
                page.close()
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
    print(json.dumps({'passed':True,'results':results,'screenshots':str(output)}))


if __name__ == '__main__':
    main()
