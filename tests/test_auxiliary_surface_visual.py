import tempfile
import unittest
from pathlib import Path
import test_refresh_visual

OUTPUT=Path(tempfile.mkdtemp(prefix='dief-forge-skin-'))


class AuxiliarySurfaceVisualTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=test_refresh_visual.RefreshVisualTests.asyncSetUp
    asyncTearDown=test_refresh_visual.RefreshVisualTests.asyncTearDown

    async def test_forge_status_skin_preserves_scene_and_small_viewport_bounds(self):
        await self.page.goto(self.url+'/forja.html')
        await self.page.wait_for_function('window.forgeReady')
        await self.page.evaluate('updateForge({engine:"Codex",project:"Projeto de demonstracao",activities:[{id:"a",title:"Preparando projeto",detail:"Etapa de demonstracao",status:"completed"},{id:"b",title:"Verificando resultado",detail:"Conferindo a previa",status:"running"}]})')
        await self.page.evaluate('beginForgeEntrance({reduced:true})')
        for width,height in ((1366,900),(390,844)):
            await self.page.set_viewport_size({'width':width,'height':height})
            await self.page.wait_for_timeout(150)
            self.assertEqual(await self.page.evaluate('forgeScenePhase'),'ready')
            self.assertEqual(await self.page.locator('body').evaluate('e=>getComputedStyle(e).backgroundColor'),'rgb(0, 0, 0)')
            self.assertEqual(await self.page.locator('.panel-title').evaluate('e=>getComputedStyle(e).color'),'rgb(198, 231, 255)')
            self.assertEqual(await self.page.locator('#forgePanel button').count(),0)
            for selector in ('#forgePanel','.panel-title','#forgePrompt'):
                box=await self.page.locator(selector).bounding_box()
                self.assertIsNotNone(box)
                self.assertGreaterEqual(box['x'],0);self.assertGreaterEqual(box['y'],0)
                self.assertLessEqual(box['x']+box['width'],width+1)
                self.assertLessEqual(box['y']+box['height'],height+1)
            await self.page.screenshot(path=str(OUTPUT/f'forja-{width}.png'))
        self.assertEqual(self.errors,[])
