import hashlib
import math
import unittest
from pathlib import Path
from PIL import Image
from io import BytesIO
import test_refresh_visual


class HologramPolishTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=test_refresh_visual.RefreshVisualTests.asyncSetUp
    asyncTearDown=test_refresh_visual.RefreshVisualTests.asyncTearDown

    async def test_material_palette_state_morph_and_small_framing(self):
        await self.page.goto(self.url+'/index.html')
        self.page.on('console',lambda msg:self.errors.append(msg.text) if msg.type=='error' and ('WebGLProgram' in msg.text or 'Shader Error' in msg.text) else None)
        await self.page.wait_for_function('typeof window.hologramDiagnostics === "function"')
        await self.page.evaluate("document.body.style.background=\"#04070b url('./assets/deep-space.png') center/cover\"")
        await self.page.wait_for_timeout(1300)
        await self.page.evaluate("window.updateCore({phase:'speaking',level:.25})");await self.page.wait_for_timeout(250)
        stats=await self.page.evaluate('window.hologramDiagnostics()')
        self.assertEqual(stats['nodes'],5)
        self.assertNotEqual(stats['palette']['heart'],stats['palette']['structure'])
        self.assertLessEqual(stats['drawCalls'],55)
        baseline=(stats['geometries'],stats['textures'])
        for index,phase in enumerate(('idle','listening','thinking','executing','speaking','sleeping')):
            await self.page.evaluate('s=>window.updateCore(s)',{'phase':phase,'level':.32 if phase in ('listening','speaking') else 0,'resting':phase=='sleeping','color':'#62cfdb'})
            await self.page.wait_for_timeout(800)
            self.assertEqual((await self.page.evaluate('window.hologramDiagnostics().phase')),phase)
            await self.page.screenshot(path=str(test_refresh_visual.BASE/f'validation/hologram-{phase}.png'))
        for width,height in ((1600,900),(640,480),(390,844)):
            await self.page.set_viewport_size({'width':width,'height':height})
            await self.page.evaluate("window.updateCore({phase:'idle',resting:false,level:0,color:'#bdb2eb'})")
            await self.page.wait_for_timeout(1400)
            # With preserveDrawingBuffer=false, read the composited screenshot,
            # not a cleared WebGL buffer between animation frames.
            await self.page.evaluate("document.body.style.background='transparent'")
            png=await self.page.locator('canvas').screenshot(omit_background=True)
            content=Image.open(BytesIO(png)).convert('RGBA')
            pixel_width,pixel_height=content.size
            self.assertGreater(sum(pixel[3]>30 for pixel in content.getdata()),500)
            # The core must retain breathing room instead of being cropped in portrait.
            for x in (0,pixel_width-1):
                self.assertLess(sum(content.getpixel((x,y))[3]>30 for y in range(pixel_height)),pixel_height*.05)
            await self.page.screenshot(path=str(test_refresh_visual.BASE/f'validation/hologram-fit-{width}.png'))
        stats=await self.page.evaluate('window.hologramDiagnostics()')
        self.assertEqual((stats['geometries'],stats['textures']),baseline)
        import json
        (test_refresh_visual.BASE/'validation/hologram-metrics.json').write_text(json.dumps(stats,indent=2),encoding='utf-8')
        self.assertEqual(self.errors,[])

    async def test_projection_reduced_motion_cues_and_hidden_pause(self):
        await self.page.goto(self.url+'/index.html')
        await self.page.wait_for_function('typeof window.hologramDiagnostics === "function"')
        await self.page.wait_for_timeout(1200)
        delta=await self.page.evaluate('''async()=>{
          const [{buildCore},{addCoreSurfaces},{createCoreMotion}]=await Promise.all([
            import('./core-model.mjs'),import('./core-surface.mjs'),import('./core-motion.mjs')]);
          const core=buildCore('cyan',true),motion=createCoreMotion(core,addCoreSurfaces(core));
          motion.state.time=1800;
          motion.step(.016,{phase:'idle',visible:true,level:0});
          const previous=core.beacons.children[0].position.clone();
          motion.step(.016,{phase:'thinking',visible:true,level:0});
          const distance=previous.distanceTo(core.beacons.children[0].position);
          const geometries=new Set(),materials=new Set();
          core.root.traverse(node=>{if(node.isInstancedMesh)node.dispose();if(node.geometry)geometries.add(node.geometry);if(node.material)materials.add(node.material);});
          geometries.forEach(g=>g.dispose());materials.forEach(m=>m.dispose());core.texture.dispose();
          return distance;
        }''')
        self.assertLess(delta,.01,'Long-session state change must not teleport orbit nodes.')
        await self.page.evaluate("window.updateCore({phase:'executing',cue:{kind:'analysis',serial:1}})")
        await self.page.wait_for_timeout(100)
        self.assertTrue(await self.page.evaluate('window.hologramDiagnostics().cueActive'))
        await self.page.evaluate("window.updateCore({phase:'idle',projection:true})")
        await self.page.wait_for_timeout(100)
        self.assertTrue(await self.page.evaluate('window.hologramDiagnostics().projection'))
        await self.page.evaluate("window.updateCore({phase:'speaking',projection:false,level:.2,motion:'reduced'})")
        await self.page.wait_for_timeout(100)
        first=await self.page.locator('canvas').screenshot();await self.page.wait_for_timeout(350)
        self.assertEqual(first,await self.page.locator('canvas').screenshot())
        await self.page.evaluate("window.updateCore({motion:'full',visible:false})")
        before=await self.page.evaluate('window.hologramDiagnostics().orbit');await self.page.wait_for_timeout(350)
        self.assertEqual(before,await self.page.evaluate('window.hologramDiagnostics().orbit'))
        await self.page.evaluate("window.updateCore({visible:true,phase:'idle',level:0})")
        await self.page.wait_for_timeout(300)
        self.assertNotEqual(before,await self.page.evaluate('window.hologramDiagnostics().orbit'))
        self.assertEqual(self.errors,[])

    async def test_motion_recording_and_repeated_states_keep_resources_bounded(self):
        context=await self.browser.new_context(viewport={'width':1200,'height':900},record_video_dir=str(test_refresh_visual.BASE/'validation/hologram-video'))
        page=await context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        await page.goto(self.url+'/index.html')
        await page.wait_for_function('typeof window.hologramDiagnostics === "function"')
        await page.evaluate("document.body.style.background=\"#04070b url('./assets/deep-space.png') center/cover\"")
        await page.wait_for_timeout(1300)
        await page.evaluate("window.updateCore({phase:'speaking',level:.3})");await page.wait_for_timeout(250)
        initial=await page.evaluate('window.hologramDiagnostics()')
        for phase in ('idle','listening','thinking','executing','speaking','idle'):
            for i in range(10):
                await page.evaluate('s=>window.updateCore(s)',{'phase':phase,'level':.12+.18*abs(math.sin(i*.5)) if phase in ('speaking','listening') else 0,'resting':False,'color':'#72d8d1'})
                await page.wait_for_timeout(120)
        final=await page.evaluate('window.hologramDiagnostics()')
        self.assertEqual(final['geometries'],initial['geometries']);self.assertEqual(final['textures'],initial['textures'])
        await page.evaluate("window.updateCore({resting:true,phase:'sleeping',level:0})");await page.wait_for_timeout(1200)
        video=page.video;await page.close();await context.close()
        await video.save_as(str(test_refresh_visual.BASE/'validation/hologram-motion.webm'))
        self.assertEqual(errors,[])


class FacePolishTests(unittest.TestCase):
    def test_scan_is_contextual_and_rest_reduces_pose_motion(self):
        from core.avatar import HoloAvatar
        avatar=HoloAvatar()
        for _ in range(20):avatar.step(.016,0,state='LISTENING')
        self.assertEqual(avatar._scan,-3)
        for _ in range(20):avatar.step(.016,0,state='THINKING')
        self.assertGreater(avatar._scan,-1.75)
        avatar.reduced_motion=True
        for _ in range(20):avatar.step(.016,0,state='THINKING')
        self.assertEqual(avatar._scan,-3)
        self.assertEqual(avatar._yaw,0)

    def test_face_palette_has_neutral_highlights_and_cached_materials(self):
        from core.avatar import HoloAvatar
        from PyQt6.QtGui import QColor
        avatar=HoloAvatar();ramp=avatar._lut(QColor('#03060b'),QColor('#00d4ff'))
        self.assertGreater(ramp[-1].color().red(),10)
        self.assertIs(ramp,avatar._lut(QColor('#03060b'),QColor('#00d4ff')))
