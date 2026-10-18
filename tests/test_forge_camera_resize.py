"""Real WebGL camera return after a viewport change, no Codex connection."""
import unittest
import math
import test_refresh_visual


class ForgeCameraResizeTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=test_refresh_visual.RefreshVisualTests.asyncSetUp
    asyncTearDown=test_refresh_visual.RefreshVisualTests.asyncTearDown

    async def test_exit_returns_to_current_responsive_camera_without_snap(self):
        await self.page.set_viewport_size({'width':1200,'height':800})
        await self.page.goto(self.url+'/index.html')
        await self.page.wait_for_function('document.body.dataset.ready==="true"')
        entered=await self.page.evaluate('enterForgeTransition({reduced:false})')
        self.assertEqual(entered['status'],'completed')
        await self.page.set_viewport_size({'width':400,'height':900})
        await self.page.wait_for_timeout(100)
        result=await self.page.evaluate('''async()=>{
            const result=await exitForgeTransition({reduced:false});
            const immediate=hologramDiagnostics().camera[2];
            await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
            return {result,immediate,later:hologramDiagnostics().camera[2],visible:hologramDiagnostics().coreVisible};
        }''')
        expected=max(7.7,2.35/(math.tan(math.radians(18))*(400/900)))
        self.assertEqual(result['result']['status'],'completed')
        self.assertAlmostEqual(result['immediate'],expected,places=3)
        self.assertAlmostEqual(result['later'],result['immediate'],places=3)
        self.assertTrue(result['visible'])
        self.assertEqual(self.errors,[])
