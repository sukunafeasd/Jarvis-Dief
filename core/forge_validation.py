"""Validate a generated candidate in an isolated browser, never the privileged HUD."""
from urllib.parse import urlsplit


def validate_candidate(url):
    origin=urlsplit(url)
    if origin.scheme!='http' or origin.hostname!='127.0.0.1' or not origin.port:
        return {'syntax':False,'assets':False,'initialized':False,'nonblank':False,'framing':False,'console_errors':['URL de previa invalida.']}
    from playwright.sync_api import sync_playwright
    from PIL import Image,ImageChops
    from io import BytesIO
    errors=[];failed=[]
    with sync_playwright() as playwright:
        browser=playwright.chromium.launch(channel='msedge',headless=True,args=['--enable-webgl','--ignore-gpu-blocklist'])
        try:
            # CSP already forbids service workers via an opaque sandbox origin.
            # Playwright's additional blocking shim throws inside that origin.
            context=browser.new_context(viewport={'width':1200,'height':800})
            def route(request):
                candidate=urlsplit(request.request.url)
                if candidate.scheme=='http' and candidate.netloc==origin.netloc:request.continue_()
                else:request.abort()
            context.route('**/*',route)
            page=context.new_page()
            page.on('pageerror',lambda error:errors.append(str(error)[:500]))
            page.on('console',lambda message:errors.append(message.text[:500]) if message.type=='error' else None)
            page.on('requestfailed',lambda request:failed.append(request.url[:300]))
            page.on('response',lambda response:failed.append(response.url[:300]) if response.status>=400 else None)
            page.goto(url,wait_until='load',timeout=20000)
            page.wait_for_timeout(1200)
            geometry=page.evaluate('({width:innerWidth,height:innerHeight,scroll:document.documentElement.scrollWidth,children:document.body.children.length})')
            data=page.screenshot();pixels=Image.open(BytesIO(data)).convert('RGB')
            extrema=pixels.getextrema()
            nonblank=any(high-low>12 for low,high in extrema)
            framing=geometry['scroll']<=geometry['width']+2 and geometry['children']>0
            return {'syntax':not errors,'assets':not failed,'initialized':True,'nonblank':nonblank,'framing':framing,'console_errors':errors[:20]}
        finally:browser.close()
