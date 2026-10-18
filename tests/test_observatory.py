import unittest
import test_refresh_visual


class ObservatoryTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = test_refresh_visual.RefreshVisualTests.asyncSetUp
    asyncTearDown = test_refresh_visual.RefreshVisualTests.asyncTearDown

    async def test_shared_rig_entrance_and_interrupt(self):
        await self.page.goto(self.url+'/space.html')
        await self.page.wait_for_function('typeof window.spaceDiagnostics === "function"')
        values=await self.page.evaluate('async()=>{const r=await import("./environment-rig.mjs");const e={at:1000,duration:4000,cancelAt:2000};return [r.entranceDistance(e,1000),r.entranceDistance(e,2000),r.entranceDistance(e,2320),r.entranceDistance(e,1100,true),r.frameBudget({visible:false}),r.frameBudget({visible:true,motion:"reduced"})]}')
        self.assertEqual(values[0],24);self.assertGreater(values[1],0)
        self.assertEqual(values[2:],[0,0,0,0])
        await self.page.evaluate('window.updateCore({entrance:{at:Date.now(),duration:4300},phase:"booting"})')
        await self.page.wait_for_timeout(100)
        before=await self.page.evaluate('window.spaceDiagnostics()')
        await self.page.evaluate('window.updateCore({entrance:{at:Date.now()-200,duration:4300,cancelAt:Date.now()}})')
        await self.page.wait_for_timeout(650)
        self.assertEqual(await self.page.evaluate('window.spaceDiagnostics().travel'),0)
        self.assertGreater(before['travel'],0)
        self.assertEqual(self.errors,[])

    async def test_planets_modes_resources_and_suspension(self):
        await self.page.goto(self.url+'/space.html')
        await self.page.wait_for_function('typeof window.spaceDiagnostics === "function"')
        await self.page.wait_for_function('document.body.dataset.asset==="ready"')
        await self.page.wait_for_function('window.spaceDiagnostics().surfaceMaps.earth==="Solar System Scope" && window.spaceDiagnostics().surfaceMaps.moon==="Solar System Scope"')
        await self.page.evaluate('window.updateCore({mode:"exploration",planet:"saturn",motion:"reduced"})')
        baseline=await self.page.evaluate('window.spaceDiagnostics()')
        self.assertEqual(len(baseline['planets']),10)
        self.assertEqual(baseline['lights'],2)
        for planet in ('sun','earth','saturn','moon'):
            await self.page.evaluate('p=>window.updateCore({mode:"exploration",planet:p,motion:"reduced"})',planet)
            self.assertEqual(await self.page.locator('#planet-label strong').inner_text(),{'sun':'Sol','earth':'Terra','saturn':'Saturno','moon':'Lua'}[planet])
            self.assertTrue(await self.page.locator('#planet-label').is_visible())
        current=await self.page.evaluate('window.spaceDiagnostics()')
        self.assertEqual(current['textures'],baseline['textures'])
        self.assertEqual(current['geometries'],baseline['geometries'])
        await self.page.evaluate('window.updateCore({mode:"focus"})')
        self.assertFalse(await self.page.locator('#planet-label').is_visible())
        frames=await self.page.evaluate('window.spaceDiagnostics().frames')
        await self.page.wait_for_timeout(350)
        self.assertEqual(frames,await self.page.evaluate('window.spaceDiagnostics().frames'))
        await self.page.evaluate('window.updateCore({visible:false,motion:"full"})')
        frames=await self.page.evaluate('window.spaceDiagnostics().frames')
        await self.page.wait_for_timeout(250)
        self.assertEqual(frames,await self.page.evaluate('window.spaceDiagnostics().frames'))
        self.assertEqual(self.errors,[])
