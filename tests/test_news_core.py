import base64
import unittest
from pathlib import Path
from unittest.mock import Mock
from PyQt6.QtCore import QUrl
import test_refresh_visual
import test_scene

BASE=Path(__file__).resolve().parents[1]
OUTPUT=BASE/'validation/news-core'


def news_model():
    image='data:image/png;base64,'+base64.b64encode((BASE/'core/spatial/assets/deep-space.png').read_bytes()).decode()
    return {'kind':'news','title':'NOTÍCIAS DE DEMONSTRAÇÃO','presentationId':123,
        'narrationDriven':True,'newsFusion':True,'items':[
            {'title':title,'source':'Fonte de demonstração','category':category,'image':image}
            for title,category in [('Pesquisa sobre o clima global','MUNDO'),
                ('Nova descoberta na exploração espacial','CIÊNCIA'),
                ('Avanços no estudo de inteligência artificial','TECNOLOGIA')]]}


class NewsCoreVisualTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=test_refresh_visual.RefreshVisualTests.asyncSetUp
    asyncTearDown=test_refresh_visual.RefreshVisualTests.asyncTearDown

    async def prepare(self):
        OUTPUT.mkdir(parents=True,exist_ok=True)
        self.page.on('console',lambda message:self.errors.append(message.text)
            if message.type=='error' and ('Shader Error' in message.text or 'VALIDATE_STATUS' in message.text) else None)
        await self.page.goto(self.url+'/index.html')
        await self.page.wait_for_function('typeof window.updateNewsCore === "function"')
        await self.page.evaluate("document.documentElement.style.background=\"#05090d url('./assets/deep-space.png') center/cover\"")
        await self.page.evaluate('window.updateCore({phase:"speaking",color:"#ff303b",projection:false,visible:true,level:.14})')
        await self.page.wait_for_timeout(1200)

    async def test_news_stays_in_primary_core_after_narration(self):
        await self.prepare()
        model=news_model()
        await self.page.evaluate('m=>window.updateNewsCore({id:m.presentationId,items:m.items,focus:0,mode:"fused"})',model)
        await self.page.wait_for_function('window.newsCoreDiagnostics().images===3')
        await self.page.wait_for_timeout(800)
        self.assertEqual(await self.page.locator('canvas').count(),1)
        self.assertEqual(await self.page.evaluate('window.newsCoreDiagnostics().visible'),[0])
        await self.page.wait_for_timeout(1000)
        self.assertEqual(await self.page.evaluate('window.newsCoreDiagnostics().focus'),0)
        for index in (1,2):
            await self.page.evaluate('(v)=>window.updateNewsCore(v)',{'id':123,'items':model['items'],'focus':index,'mode':'fused'})
            await self.page.wait_for_timeout(750)
        self.assertEqual(await self.page.evaluate('window.newsCoreDiagnostics().visible'),[0,1,2])
        self.assertIn('Nova descoberta',await self.page.locator('#core-news-summary').inner_text())
        await self.page.screenshot(path=str(OUTPUT/'fused-news.png'))
        await self.page.evaluate("document.documentElement.style.background='transparent'")
        raw=await self.page.locator('canvas').screenshot(omit_background=True)
        from io import BytesIO
        from PIL import Image
        image=Image.open(BytesIO(raw)).convert('RGBA')
        self.assertGreater(sum(pixel[3]>80 for pixel in image.get_flattened_data()),10000)
        await self.page.evaluate('u=>{const f=document.createElement("iframe");f.id="front";f.src=u;f.style.cssText="position:absolute;inset:15%;width:70%;height:70%;border:0;background:transparent";document.body.append(f)}',self.url+'/presentation.html')
        await self.page.wait_for_function('typeof document.getElementById("front").contentWindow.updateCore === "function"')
        frame=self.page.frame(url=self.url+'/presentation.html')
        await frame.wait_for_function('typeof window.updateCore === "function"')
        await frame.evaluate('m=>window.updateCore({...m,focus:2})',model)
        self.assertEqual(await frame.evaluate('document.body.style.visibility'),'hidden')
        await frame.evaluate('window.finishPresentation()')
        await self.page.evaluate('m=>window.updateNewsCore({id:123,items:m.items,focus:2,mode:"settled"})',model)
        await self.page.wait_for_timeout(1100)
        self.assertEqual(await self.page.evaluate('window.newsCoreDiagnostics().phase'),'settled')
        self.assertEqual(await frame.evaluate('document.body.style.visibility'),'hidden')
        self.assertEqual(await frame.locator('.news-banner').count(),1)
        await self.page.screenshot(path=str(OUTPUT/'inside-after-narration.png'))
        self.assertEqual(self.errors,[])

    async def test_reduced_hidden_interruption_and_resource_disposal(self):
        await self.prepare()
        baseline=await self.page.evaluate('window.hologramDiagnostics()')
        model=news_model()
        value={'id':123,'items':model['items'],'focus':0,'mode':'fused'}
        await self.page.evaluate('window.updateCore({motion:"reduced"})')
        await self.page.evaluate('v=>window.updateNewsCore(v)',value)
        await self.page.wait_for_function('window.newsCoreDiagnostics().images===3')
        await self.page.evaluate('v=>window.updateNewsCore({...v,mode:"paused"})',value)
        before=await self.page.evaluate('document.querySelector("canvas").toDataURL()')
        await self.page.wait_for_timeout(250)
        self.assertEqual(before,await self.page.evaluate('document.querySelector("canvas").toDataURL()'))
        await self.page.evaluate('window.updateCore({visible:false})')
        await self.page.wait_for_timeout(150)
        self.assertEqual(before,await self.page.evaluate('document.querySelector("canvas").toDataURL()'))
        await self.page.evaluate('window.updateCore({visible:true,motion:"reduced"})')
        for index in range(12):
            await self.page.evaluate('v=>{window.updateNewsCore({...v,id:Math.random()});window.updateNewsCore(null)}',value)
        await self.page.wait_for_timeout(100)
        final=await self.page.evaluate('window.hologramDiagnostics()')
        self.assertEqual(baseline['geometries'],final['geometries'])
        self.assertEqual(baseline['textures'],final['textures'])
        await self.page.evaluate('v=>window.updateNewsCore({...v,items:[{title:"Sem fotografia",image:"https://unapproved.test/p.png"}]})',value)
        self.assertEqual(await self.page.evaluate('window.newsCoreDiagnostics().images'),0)
        await self.page.evaluate('v=>window.updateNewsCore({...v,mode:"front"})',value)
        self.assertEqual(await self.page.evaluate('window.newsCoreDiagnostics().phase'),'inactive')
        self.assertEqual(self.errors,[])

    async def test_small_viewport_and_semantic_focus_no_automatic_carousel(self):
        await self.prepare()
        await self.page.set_viewport_size({'width':640,'height':480})
        model=news_model()
        await self.page.evaluate('m=>window.updateNewsCore({id:123,items:m.items,focus:0,mode:"fused"})',model)
        await self.page.wait_for_function('window.newsCoreDiagnostics().images===3')
        await self.page.wait_for_timeout(650)
        await self.page.screenshot(path=str(OUTPUT/'fused-small.png'))
        first=await self.page.locator('canvas').screenshot()
        await self.page.wait_for_timeout(300)
        self.assertNotEqual(first,await self.page.locator('canvas').screenshot())
        self.assertEqual(await self.page.evaluate('window.newsCoreDiagnostics().focus'),0)
        self.assertLess(await self.page.evaluate('window.hologramDiagnostics().drawCalls'),65)
        self.assertEqual(self.errors,[])


class NewsCoreBridgeTests(unittest.TestCase):
    setUpClass=classmethod(test_scene.SceneTests.setUpClass.__func__)
    def setUp(self):
        test_scene.SceneTests.setUp(self)
        self.window.hud.hud_style='core'
        self.window.hud._spatial_core=Mock(failed=False)
        self.window._content_spatial=Mock(failed=False,_loaded=True)

    def tearDown(self):
        self.window.hud._spatial_core=None
        self.window._content_spatial=None
        test_scene.SceneTests.tearDown(self)

    def test_pause_and_completion_keep_news_inside_core(self):
        self.window._show_manifestation({'kind':'news','title':'NOTÍCIAS','narrationDriven':True,'items':[{'title':'Teste'}]})
        self.assertEqual(self.window.hud.news_content['mode'],'fused')
        self.window._apply_state('SPEAKING')
        self.window._advance_presentation(.1)
        self.window._cancel_presentation()
        self.window._apply_state('LISTENING')
        self.assertEqual(self.window.hud.news_content['mode'],'paused')
        self.window._resume_presentation()
        self.window._apply_state('SPEAKING')
        self.window._advance_presentation(.1)
        self.window._apply_state('LISTENING')
        self.assertEqual(self.window.hud.news_content['mode'],'settled')

    def test_chapters_wait_until_last_and_stale_focus_is_ignored(self):
        self.window._show_manifestation({'kind':'news','title':'NOTÍCIAS','narrationDriven':True,'newsLast':False,'items':[{'title':'Primeira'},{'title':'Segunda'}]})
        model=self.window._presentation['model']
        self.window._apply_state('SPEAKING');self.window._advance_presentation(.1);self.window._apply_state('LISTENING')
        self.assertEqual(self.window.hud.news_content['mode'],'fused')
        self.window._spatial_navigation(QUrl('file:///test#speech-focus-1-1-stale'))
        self.assertEqual(self.window.hud.news_content['focus'],0)
        self.window._spatial_navigation(QUrl('file:///test#speech-focus-1-2-'+str(model['presentationId'])))
        self.assertEqual(self.window.hud.news_content['focus'],1)
        self.window._show_manifestation({'kind':'weather','title':'CLIMA','temperature':19})
        self.assertIsNone(self.window.hud.news_content)

    def test_core_failure_retains_existing_front_fallback(self):
        self.window.hud._spatial_core.failed=True
        self.window._show_manifestation({'kind':'news','title':'NOTÍCIAS','narrationDriven':True,'items':[{'title':'Teste'}]})
        self.assertIsNone(self.window.hud.news_content)
        payload=self.window._content_spatial.sync.call_args.args[0]
        self.assertFalse(payload['newsFusion'])
