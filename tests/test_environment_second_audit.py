import unittest
import test_refresh_visual


class EnvironmentVisualAudit(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=test_refresh_visual.RefreshVisualTests.asyncSetUp
    asyncTearDown=test_refresh_visual.RefreshVisualTests.asyncTearDown

    async def test_modes_clear_previous_planet_and_have_distinct_visual_state(self):
        await self.page.goto(self.url+'/space.html')
        await self.page.wait_for_function('document.body.dataset.asset === "ready"')
        for mode in ('exploration','analysis','execution','focus','assistant'):
            await self.page.evaluate('mode=>window.updateCore({mode,planet:mode==="exploration"?"saturn":null,motion:"reduced"})',mode)
            state=await self.page.evaluate('window.spaceDiagnostics()')
            self.assertEqual(state['mode'],mode)
            if mode in ('analysis','execution','focus'):
                self.assertEqual(state['solarVisibility'],0 if mode=='focus' else .45)
                self.assertFalse(await self.page.locator('#planet-label').is_visible())
            self.assertEqual(state['gridOpacity'],0)
            self.assertEqual(state['networkOpacity'],0)
            if mode=='assistant':self.assertEqual(state['planet'],None)
        self.assertEqual(self.errors,[])

    async def test_staging_then_shared_entrance_has_no_immediate_cut(self):
        await self.page.goto(self.url+'/index.html')
        await self.page.wait_for_function('typeof window.updateEnvironment === "function"')
        await self.page.evaluate('window.updateEnvironment({staging:true});window.updateCore({motion:"reduced"})')
        await self.page.evaluate('window.updateEnvironment({staging:false,mode:"focus"})')
        self.assertEqual(await self.page.evaluate('window.hologramDiagnostics().environmentMode'),'focus')
        await self.page.evaluate('window.updateCore({motion:"full",phase:"speaking"});window.updateEnvironment({entrance:{at:Date.now(),duration:4300,cancelAt:null}})')
        await self.page.wait_for_timeout(250)
        before=await self.page.evaluate('window.hologramDiagnostics().travel')
        await self.page.wait_for_timeout(750)
        after=await self.page.evaluate('window.hologramDiagnostics().travel')
        self.assertGreater(before,after)
        self.assertGreater(after,15)
        self.assertEqual(self.errors,[])
