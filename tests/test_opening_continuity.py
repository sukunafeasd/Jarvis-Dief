"""Real local WebGL: one core, prepared scene and world-fixed ULTRON."""
import asyncio
from io import BytesIO
from pathlib import Path
import unittest
import tempfile
from PIL import Image
import test_refresh_visual

OUTPUT=Path(tempfile.mkdtemp(prefix='dief-opening-continuity-'))


class OpeningContinuityTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=test_refresh_visual.RefreshVisualTests.asyncSetUp
    asyncTearDown=test_refresh_visual.RefreshVisualTests.asyncTearDown

    async def test_ultron_load_failure_does_not_publish_ready(self):
        await self.page.route('**/ultron-crust.json',lambda route:route.abort())
        await self.page.goto(self.url+'/space.html?staged=1')
        await self.page.wait_for_function('document.body.dataset.error==="ultron-unavailable"')
        self.assertNotEqual(await self.page.evaluate('document.body.dataset.ready'),'true')

    async def test_last_backdrop_failure_settles_reduced_motion_readiness(self):
        held=[]
        await self.page.route('**/deep-space.png',lambda route:held.append(route))
        await self.page.goto(self.url+'/space.html?staged=1',wait_until='domcontentloaded')
        await self.page.wait_for_function('typeof updateCore==="function"')
        await self.page.evaluate('updateCore({motion:"reduced"})')
        await self.page.wait_for_function('window.ultronDiagnostics?.().frames>0 && spaceDiagnostics().pendingMaps===0')
        self.assertNotEqual(await self.page.evaluate('document.body.dataset.ready'),'true')
        for route in held:await route.abort()
        await self.page.wait_for_function('document.body.dataset.ready==="true"')

    async def shot(self,name):
        OUTPUT.mkdir(parents=True,exist_ok=True)
        return await self.page.screenshot(path=str(OUTPUT/name))

    async def test_real_core_stays_far_until_release_then_approaches_without_replacement(self):
        await self.page.goto(self.url+'/index.html?staged=1')
        await self.page.wait_for_function('document.body.dataset.ready==="true"')
        first=await self.page.evaluate('hologramDiagnostics()')
        self.assertTrue(first['coreVisible']);self.assertEqual(first['travel'],24)
        pixels=Image.open(BytesIO(await self.shot('core-prepared.png'))).convert('RGB')
        self.assertGreater(sum(r>70 and r>g*1.6 and r>b*1.3 for r,g,b in pixels.getdata()),30)
        await self.page.wait_for_timeout(700)
        await self.page.set_viewport_size({'width':1000,'height':700})
        await self.page.wait_for_timeout(150)
        held=await self.page.evaluate('hologramDiagnostics()')
        self.assertEqual(held['travel'],24);self.assertTrue(held['coreVisible'])
        self.assertEqual(first['geometries'],held['geometries'])
        await self.page.evaluate('''() => {window.testNow=1000;Date.now=()=>testNow;
            updateEnvironment({staging:false,entrance:{at:1000,duration:4300,cancelAt:null}});}''')
        values=[]
        for at in (1000,1800,3000,4200,5300):
            await self.page.evaluate('at=>testNow=at',at)
            await self.page.wait_for_timeout(110)
            values.append(await self.page.evaluate('hologramDiagnostics()'))
        self.assertEqual(values[0]['travel'],24)
        self.assertEqual(values[-1]['travel'],0)
        self.assertTrue(all(a['camera'][2]>=b['camera'][2] for a,b in zip(values,values[1:])))
        self.assertTrue(all(v['coreVisible'] and v['geometries']==first['geometries'] for v in values))
        await self.shot('core-arrived.png')
        self.assertEqual(self.errors,[])

    async def test_ultron_is_world_fixed_while_all_cameras_approach(self):
        for width,height in ((1440,900),(390,844)):
            await self.page.set_viewport_size({'width':width,'height':height})
            await self.page.goto(self.url+'/space.html?staged=1')
            await self.page.wait_for_function('document.body.dataset.ready==="true"',timeout=45000)
            initial=await self.page.evaluate('({space:spaceDiagnostics(),planet:ultronDiagnostics()})')
            self.assertEqual(initial['space']['pendingMaps'],0)
            self.assertEqual(len(initial['space']['surfaceMaps']),10)
            self.assertTrue(initial['space']['solarVisible'])
            self.assertGreater(initial['planet']['frames'],0)
            self.assertEqual(initial['planet']['travel'],24)
            before=await self.shot(f'world-prepared-{width}.png')
            await self.page.evaluate('''() => {window.testNow=1000;Date.now=()=>testNow;
                updateCore({staging:false,entrance:{at:1000,duration:4300,cancelAt:null}});}''')
            values=[]
            for at in (1000,2500,4000,5300):
                await self.page.evaluate('at=>testNow=at',at)
                await self.page.wait_for_function('Math.abs(ultronDiagnostics().camera[2]-spaceDiagnostics().camera.z)<.0001 && Math.abs(spaceDiagnostics().camera.z-3-spaceDiagnostics().travel)<.0001',timeout=15000)
                values.append(await self.page.evaluate('({space:spaceDiagnostics(),planet:ultronDiagnostics()})'))
            for sample in values:
                planet=sample['planet'];space=sample['space']
                self.assertEqual(planet['worldPosition'],initial['planet']['worldPosition'])
                self.assertEqual(planet['worldScale'],initial['planet']['worldScale'])
                self.assertAlmostEqual(planet['camera'][2],space['camera']['z'],places=4,msg=str(self.errors)+str(values))
                self.assertAlmostEqual(planet['camera'][0],space['camera']['x'],places=4)
            self.assertGreater(values[0]['planet']['camera'][2],values[-1]['planet']['camera'][2]+20)
            self.assertNotEqual(values[0]['planet']['projectedCenter'],values[-1]['planet']['projectedCenter'])
            after=await self.shot(f'world-arrived-{width}.png')
            self.assertNotEqual(before,after)
            original=values[-1]['planet']['worldPosition']
            await self.page.set_viewport_size({'width':width-40,'height':height})
            await self.page.wait_for_timeout(100)
            self.assertEqual(await self.page.evaluate('ultronDiagnostics().worldPosition'),original)
            await self.page.evaluate('updateUltron({state:{phase:"active"}})')
            await self.page.wait_for_timeout(100)
            self.assertEqual(await self.page.evaluate('ultronDiagnostics().camera[2]'),3)
        self.assertEqual(self.errors,[])

    async def test_protocol_focus_approaches_fixed_planet_and_returns(self):
        for width,height in ((1440,900),(390,844)):
            await self.page.set_viewport_size({'width':width,'height':height})
            await self.page.goto(self.url+'/space.html')
            await self.page.wait_for_function('document.body.dataset.ready==="true"',timeout=45000)
            await self.page.evaluate('''() => {window.testNow=10000;Date.now=()=>testNow;
                updateCore({staging:false,entrance:null});}''')
            await self.page.wait_for_function('ultronDiagnostics().camera[2]===3')
            original=await self.page.evaluate('ultronDiagnostics()')
            await self.page.evaluate('updateUltron({state:{phase:"scanning"}})')
            focus=await self.page.evaluate('ultronCameraState')
            for at in (10600,11200,11800):
                await self.page.evaluate('at=>testNow=at',at)
                await self.page.wait_for_function('''() => Math.abs(ultronDiagnostics().camera[2]-spaceDiagnostics().camera.z)<.0001
                    && ultronDiagnostics().camera[2]<2''',timeout=15000)
                await self.page.wait_for_timeout(160)
                planet=await self.page.evaluate('ultronDiagnostics()')
                self.assertEqual(planet['worldPosition'],original['worldPosition'])
                self.assertEqual(planet['worldScale'],original['worldScale'])
            self.assertLess(planet['camera'][2],-5)
            self.assertNotEqual(planet['projectedCenter'],original['projectedCenter'])
            self.assertGreater(planet['projectedCenter'][0],-.8)
            self.assertLess(planet['projectedCenter'][0],.5)
            await self.page.evaluate('updateUltron({state:{phase:"active",progress:100}})')
            self.assertEqual(await self.page.evaluate('ultronCameraState.at'),focus['at'])
            image=Image.open(BytesIO(await self.shot(f'ultron-focused-{width}.png'))).convert('RGB')
            self.assertGreater(sum(r>100 and r>g*1.6 and r>b*1.4 for r,g,b in image.getdata()),500)
            await self.page.evaluate('updateUltron({state:{phase:"idle"}})')
            await self.page.evaluate('testNow=13600')
            await self.page.wait_for_function('ultronDiagnostics().camera[2]===3 && spaceDiagnostics().camera.z===3',timeout=15000)
            self.assertEqual(await self.page.evaluate('ultronDiagnostics().worldPosition'),original['worldPosition'])
        self.assertEqual(self.errors,[])

    async def test_reduced_motion_protocol_focus_invalidates_both_views(self):
        await self.page.goto(self.url+'/space.html')
        await self.page.wait_for_function('document.body.dataset.ready==="true"',timeout=45000)
        await self.page.evaluate('updateCore({motion:"reduced"});updateUltron({state:{phase:"active"}})')
        await self.page.wait_for_function('ultronDiagnostics().camera[2]<-5 && spaceDiagnostics().camera.z<-5',timeout=15000)
        await self.page.evaluate('updateUltron({state:{phase:"idle"}})')
        await self.page.wait_for_function('ultronDiagnostics().camera[2]===3 && spaceDiagnostics().camera.z===3',timeout=15000)
        self.assertEqual(self.errors,[])

    async def test_reduced_motion_preparation_finishes_with_no_camera_trip(self):
        await self.page.goto(self.url+'/space.html?staged=1')
        await self.page.wait_for_function('typeof updateCore==="function"')
        await self.page.evaluate('updateCore({motion:"reduced"})')
        await self.page.wait_for_function('document.body.dataset.ready==="true"',timeout=45000)
        state=await self.page.evaluate('({space:spaceDiagnostics(),planet:ultronDiagnostics()})')
        self.assertEqual(state['space']['travel'],0);self.assertEqual(state['planet']['travel'],0)
        self.assertEqual(state['planet']['camera'][2],3)
        self.assertEqual(self.errors,[])
