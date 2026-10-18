"""Local frontend contract and pixel checks; never starts Jarvis or its backend."""
import functools
import http.server
import json
import tempfile
import threading
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageChops
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def image(data):
    return Image.open(BytesIO(data)).convert('RGB')


def main():
    server = http.server.ThreadingHTTPServer(
        ('127.0.0.1', 0), functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(ROOT / 'core/spatial')))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    output = Path(tempfile.mkdtemp(prefix='dief-forja-frontend-'))
    results = []
    base = f'http://127.0.0.1:{server.server_port}'
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, channel='msedge', args=['--enable-webgl', '--ignore-gpu-blocklist'])
            for width, height in ((1440, 900), (390, 844)):
                page = browser.new_page(viewport={'width': width, 'height': height})
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.goto(base + '/index.html')
                page.wait_for_function('window.hologramDiagnostics && document.body.dataset.ready === "true"')
                page.wait_for_timeout(1200)
                original = page.evaluate('window.hologramDiagnostics()')
                original_camera = page.evaluate('window.forgeTransitionDiagnostics().camera')
                first = page.screenshot(path=str(output / f'core-{width}.png'))
                assert image(first).getbbox(), 'Actual primary core is blank'
                page.evaluate('() => {window.entry = window.enterForgeTransition({motion:"full"});}')
                page.wait_for_timeout(2800)
                moving = page.evaluate('window.forgeTransitionDiagnostics()')
                assert moving['role'] == 'core' and moving['camera'][2] < original_camera[2], moving
                assert moving['blackoutOpacity']==0, 'Blackout began before the camera entered the core'
                assert page.evaluate('document.body.style.background')=='', 'Core page concealed the space layer early'
                travel = page.screenshot(path=str(output / f'travel-{width}.png'))
                assert ImageChops.difference(image(first), image(travel)).getbbox(), 'Camera image did not change'
                page.wait_for_function('window.forgeTransitionPhase === "blackout"')
                assert image(page.screenshot()).getextrema() == ((0, 0), (0, 0), (0, 0)), 'Blackout is not absolute black'
                assert page.evaluate('window.entry.then(r=>r.status)') == 'completed'
                assert page.evaluate('window.exitForgeTransition({reduced:true}).then(r=>r.phase)') == 'normal'
                page.wait_for_timeout(100)
                assert page.evaluate('window.hologramDiagnostics().geometries') == original['geometries']
                # A repeated entry shares the promise; exit supersedes it cleanly.
                page.evaluate('() => {window.a=window.enterForgeTransition(); window.b=window.enterForgeTransition();}')
                assert page.evaluate('window.a === window.b')
                assert page.evaluate('window.exitForgeTransition({reduced:true}).then(r=>r.phase)') == 'normal'
                assert page.evaluate('window.a.then(r=>r.status)') == 'superseded'
                page.evaluate('''() => {
                    const listener = event => {
                        if (event.detail.phase !== 'blackout') return;
                        removeEventListener('forge-transition',listener);
                        window.eventExit=window.exitForgeTransition({reduced:true});
                    };
                    addEventListener('forge-transition',listener);
                    window.eventEntry=window.enterForgeTransition({reduced:true});
                }''')
                page.wait_for_function('Boolean(window.eventExit)')
                assert page.evaluate('window.eventEntry.then(r=>r.status)') == 'completed'
                assert page.evaluate('window.eventExit.then(r=>r.phase)') == 'normal'
                page.goto(base + '/space.html')
                page.wait_for_function('window.spaceDiagnostics && document.body.dataset.ready === "true"')
                page.evaluate('window.updateCore({staging:false,motion:"reduced"})')
                backdrop=page.evaluate('getComputedStyle(document.body).backgroundImage')
                page.evaluate('() => {window.spaceEntry=window.enterForgeTransition({reduced:false});}')
                page.wait_for_timeout(1200)
                assert page.evaluate('window.forgeTransitionDiagnostics().blackoutOpacity')==0
                assert page.evaluate('getComputedStyle(document.body).backgroundImage')==backdrop
                space_early=page.screenshot(path=str(output/f'space-preserved-{width}.png'))
                assert any(high>30 for low,high in image(space_early).getextrema()), 'Space disappeared during approach'
                page.evaluate('window.exitForgeTransition({reduced:true}).then(r=>r.phase)')
                assert page.evaluate('window.enterForgeTransition({reduced:true}).then(r=>r.phase)') == 'blackout'
                assert image(page.screenshot()).getextrema() == ((0, 0), (0, 0), (0, 0))
                assert page.evaluate('window.exitForgeTransition({reduced:true}).then(r=>r.phase)') == 'normal'
                page.goto(base + '/forja.html')
                page.wait_for_function('window.forgeReady === true')
                assert page.evaluate('window.forgeScenePhase') == 'black'
                assert image(page.screenshot()).getextrema() == ((0, 0), (0, 0), (0, 0))
                page.evaluate('() => {window.entrance=window.beginForgeEntrance({reduced:false});}')
                page.wait_for_timeout(500)
                emerging = page.screenshot(path=str(output / f'light-{width}.png'))
                assert image(emerging).getbbox(), 'White entrance light is blank'
                assert page.locator('#entranceLight').evaluate('(node)=>node.tagName')=='CANVAS'
                page.wait_for_timeout(550)
                trail=page.evaluate('window.forgeDiagnostics().light')
                assert trail['point']['trail']>2, trail
                alpha=page.locator('#entranceLight').evaluate('''c=>{const a=c.getContext('2d').getImageData(0,0,c.width,c.height).data;let visible=0;for(let i=3;i<a.length;i+=4)if(a[i])visible++;return visible/(c.width*c.height)}''')
                assert 0<alpha<.2, f'Light has an opaque rectangular footprint: {alpha}'
                page.screenshot(path=str(output/f'light-trail-{width}.png'))
                page.wait_for_function('window.forgeScenePhase === "ready"')
                page.evaluate('window.updateForge({engine:"Codex",project:"Planeta com aneis",state:"validating",activities:[{id:"edit",title:"Editando material",detail:"planeta.mjs",status:"completed"},{id:"test",title:"Executando testes",status:"running"}]})')
                assert page.locator('progress').count() == 0, 'Invented numeric progress'
                page.screenshot(path=str(output / f'panel-{width}.png'))
                bounds = page.locator('#forgePanel').bounding_box()
                assert bounds and bounds['x'] >= 0 and bounds['x'] + bounds['width'] <= width + 1
                assert bounds['y'] >= 0 and bounds['y'] + bounds['height'] <= height + 1
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                assert page.evaluate('getComputedStyle(document.querySelector("#forgePanel")).borderTopWidth') == '0px'
                page.locator('#forgePrompt').fill('Reduza os aneis 30%')
                assert page.locator('button').count() == 0
                page.locator('#forgePrompt').press('Enter')
                request = page.evaluate('JSON.parse(decodeURIComponent(location.hash.slice("#forge-command-".length)))')
                assert request['action'] == 'prompt' and request['prompt'] == 'Reduza os aneis 30%'
                page.keyboard.press('F11')
                assert page.evaluate('location.hash.startsWith("#window-fullscreen-")')
                # Sandboxed generated JS runs, while the parent remains inaccessible.
                page.route('**/artifact.html', lambda route: route.fulfill(content_type='text/html', body='''<html><body style="margin:0;background:black"><canvas id="c"></canvas><script>
                    const c=document.querySelector('canvas');c.width=300;c.height=300;const x=c.getContext('2d');let n=0;
                    try{parent.document.body.dataset.breached='yes'}catch(e){}
                    function paint(){x.fillStyle='black';x.fillRect(0,0,300,300);x.fillStyle='#00ff88';x.fillRect(40+Math.sin(n++/10)*20,40,100,100);requestAnimationFrame(paint)}paint();
                    </script></body></html>'''))
                page.evaluate('url=>window.updateForge({preview_url:url,preview_version:1})', base + '/artifact.html')
                page.wait_for_function('document.querySelector("iframe")')
                page.wait_for_timeout(400)
                assert page.locator('iframe').get_attribute('sandbox') == 'allow-scripts'
                assert page.evaluate('!document.body.dataset.breached')
                a = page.locator('iframe').screenshot()
                page.wait_for_timeout(220)
                b = page.locator('iframe').screenshot()
                assert ImageChops.difference(image(a), image(b)).getbbox(), 'Generated artifact animation is frozen'
                page.evaluate('window.updateForge({visible:false})')
                assert page.locator('iframe').count() == 0
                page.evaluate('window.updateForge({visible:true})')
                assert page.locator('iframe').count() == 1
                page.set_viewport_size({'width': width + 80, 'height': height + 40})
                assert page.evaluate('window.forgeScenePhase') == 'ready'
                assert page.evaluate('window.exitForgeScene({reduced:true}).then(r=>r.phase)') == 'exited'
                assert page.locator('iframe').count() == 0
                assert image(page.screenshot()).getextrema() == ((0, 0), (0, 0), (0, 0))
                assert page.evaluate('window.beginForgeEntrance({reduced:true}).then(r=>r.phase)') == 'ready'
                page.evaluate('() => {window.leaving=window.exitForgeScene({reduced:false}); window.updateForge({visible:false});}')
                paused = page.evaluate('window.forgeDiagnostics().frames')
                page.wait_for_timeout(150)
                assert page.evaluate('window.forgeDiagnostics().frames') == paused
                page.evaluate('window.updateForge({visible:true})')
                assert page.evaluate('window.leaving.then(r=>r.phase)') == 'exited'
                page.evaluate('() => {window.opening=window.beginForgeEntrance();}')
                assert page.evaluate('window.exitForgeScene({reduced:true}).then(r=>r.phase)') == 'exited'
                assert page.evaluate('window.opening.then(r=>r.status)') == 'superseded'
                page.evaluate('''() => {
                    const listener = event => {
                        if (event.detail.phase !== 'ready') return;
                        removeEventListener('forge-scene',listener);
                        window.eventSceneExit=window.exitForgeScene({reduced:true});
                    };
                    addEventListener('forge-scene',listener);
                    window.eventSceneEntry=window.beginForgeEntrance({reduced:true});
                }''')
                page.wait_for_function('Boolean(window.eventSceneExit)')
                assert page.evaluate('window.eventSceneEntry.then(r=>r.status)') == 'completed'
                assert page.evaluate('window.eventSceneExit.then(r=>r.phase)') == 'exited'
                assert not errors, errors
                results.append({'width': width, 'passed': True, 'cameraDuringTravel': moving['camera'], 'panel': bounds})
                page.close()
            browser.close()
    finally:
        server.shutdown()
    print(json.dumps({'passed': True, 'results': results, 'screenshots': str(output)}))


if __name__ == '__main__':
    main()
