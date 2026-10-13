import hashlib
import unittest
from pathlib import Path
from core import visual_library as library
import test_refresh_visual as fixtures


class CreativeRenderTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=fixtures.RefreshVisualTests.asyncSetUp
    asyncTearDown=fixtures.RefreshVisualTests.asyncTearDown

    def model(self,width,height):
        definitions=[{'id':'ideia','icon':'pensamento/ideia/orbital','text':'Uma ideia','anchor':'alto-esquerda','palette':'violeta'},
            {'id':'rain','icon':'clima/chuva/solido','text':'Chuva ilustrativa','anchor':'alto-direita','palette':'gelo','animation':'chuva'},
            {'id':'symbol','text':'Uma nova relação','anchor':'baixo-direita','palette':'menta',
             'parts':[{'primitive':'orb'},{'primitive':'ring','slot':'orbita'},{'primitive':'node','slot':'acima'}]}]
        return {'visible':True,'reduced':False,'elements':library.resolve_layout([library.validate_element(item) for item in definitions],width,height)}

    async def test_real_meshes_motion_viewports_and_reduced_motion(self):
        from PIL import Image
        from io import BytesIO
        for width,height in ((1200,900),(640,480)):
            await self.page.set_viewport_size({'width':width,'height':height})
            await self.page.goto(self.url+'/visual_library.html')
            await self.page.wait_for_function('typeof window.updateCore === "function"')
            await self.page.evaluate("document.body.style.background='#060c16'")
            model=self.model(width,height);await self.page.evaluate('value=>window.updateCore(value)',model)
            await self.page.wait_for_timeout(350)
            first=await self.page.locator('canvas').screenshot();await self.page.wait_for_timeout(300)
            second=await self.page.locator('canvas').screenshot()
            self.assertNotEqual(hashlib.sha256(first).digest(),hashlib.sha256(second).digest())
            pixels=Image.open(BytesIO(second)).convert('RGB')
            self.assertGreater(sum(max(pixel)>40 for pixel in pixels.getdata()),400)
            diagnostics=await self.page.evaluate('window.visualDiagnostics()')
            self.assertEqual(diagnostics['objects'],3);self.assertLess(diagnostics['drawCalls'],100)
            await self.page.screenshot(path=str(Path(__file__).resolve().parents[1]/'validation'/f'biblioteca-3d-{width}.png'))
            model['reduced']=True;await self.page.evaluate('value=>window.updateCore(value)',model)
            frames=(await self.page.evaluate('window.visualDiagnostics()'))['frames']
            await self.page.wait_for_timeout(180)
            self.assertEqual((await self.page.evaluate('window.visualDiagnostics()'))['frames'],frames)
        self.assertEqual(self.errors,[])

    async def test_bounded_repeated_compositions_hidden_loop_and_disposal(self):
        await self.page.goto(self.url+'/visual_library.html');await self.page.wait_for_function('typeof window.updateCore === "function"')
        model=self.model(1200,900)
        for index in range(60):
            model['elements'][0]['id']='concept'+str(index)
            await self.page.evaluate('value=>window.updateCore(value)',model)
        diagnostics=await self.page.evaluate('window.visualDiagnostics()')
        self.assertEqual(diagnostics['objects'],3);self.assertLessEqual(diagnostics['geometries'],20);self.assertLessEqual(diagnostics['materials'],48)
        model['visible']=False;await self.page.evaluate('value=>window.updateCore(value)',model)
        frames=(await self.page.evaluate('window.visualDiagnostics()'))['frames'];await self.page.wait_for_timeout(150)
        self.assertEqual((await self.page.evaluate('window.visualDiagnostics()'))['frames'],frames)
        await self.page.evaluate('window.updateCore({elements:[]})')
        self.assertEqual((await self.page.evaluate('window.visualDiagnostics()'))['objects'],0)
        await self.page.evaluate('window.disposeVisualScene()')
        diagnostics=await self.page.evaluate('window.visualDiagnostics()')
        self.assertEqual(diagnostics['objects'],0);self.assertEqual(diagnostics['materials'],0);self.assertFalse(diagnostics['scheduled'])
        self.assertEqual(self.errors,[])

    async def test_every_registered_recipe_renders_with_bounded_cache(self):
        await self.page.goto(self.url+'/visual_library.html');await self.page.wait_for_function('typeof window.updateCore === "function"')
        recipes=list(library.ICONS.values())
        diagnostics=await self.page.evaluate('''recipes=>{
          for(let offset=0;offset<recipes.length;offset+=12){
            window.updateCore({visible:true,reduced:true,elements:recipes.slice(offset,offset+12).map((recipe,index)=>({
              id:recipe.id,recipe,parts:[],palette:'gelo',colors:['#96cfe8','#ded3a9'],animation:'montar',scale:1,
              revealed:true,visible:true,bounds:{x:80+(index%4)*250,y:100+Math.floor(index/4)*220,width:200,height:160}
            }))});
          }
          return window.visualDiagnostics();
        }''',recipes)
        self.assertEqual(diagnostics['objects'],8)
        self.assertLessEqual(diagnostics['geometries'],20);self.assertLessEqual(diagnostics['materials'],48)
        self.assertEqual(self.errors,[])
