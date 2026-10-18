"""State continuity regressions; simulated security readings, no OS actions."""
import unittest
from core.interface_verification import verify_result
import test_refresh_visual


class VerificationFollowup(unittest.TestCase):
    def test_clear_reports_preserved_free_holograms(self):
        screen={'presentation':{'visible':False},'workspace':{},'pinned_previews':[],
            'visual_scene':{'elements':[{'id':'aviso','pinned':True,'visible':True}]}}
        result=verify_result('clear','',{'ok':True,'screen':screen})
        self.assertTrue(result['ok'])
        self.assertIn('holograma:aviso',result['preserved'])

    def test_center_requires_centered_real_geometry(self):
        screen={'presentation':{'visible':False},'scene_viewport':{'width':1000,'height':800},
            'avatar_bounds':{'x':0,'y':0,'width':500,'height':800}}
        self.assertFalse(verify_result('move','center',{'ok':True,'screen':screen})['ok'])
        screen['avatar_bounds']['x']=250
        self.assertTrue(verify_result('move','center',{'ok':True,'screen':screen})['verification']['postcondition_verified'])

    def test_auto_composition_is_not_alleged_to_be_geometry_verification(self):
        screen={'presentation':{'visible':True},'scene_viewport':{'width':1000,'height':800},
            'avatar_bounds':{'x':0,'y':0,'width':500,'height':800}}
        self.assertIsNone(verify_result('move','auto',{'ok':True,'screen':screen})['verification']['postcondition_verified'])


class UltronFollowup(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=test_refresh_visual.RefreshVisualTests.asyncSetUp
    asyncTearDown=test_refresh_visual.RefreshVisualTests.asyncTearDown

    async def test_poll_keeps_selected_context_until_new_command(self):
        await self.page.goto(self.url+'/space.html')
        await self.page.wait_for_function('document.body.dataset.ready==="true"',timeout=45000)
        for mode,context in (('vault','vault'),('simulation','simulation')):
            await self.page.evaluate('mode=>updateUltron({state:{phase:"active"},result:{mode}})',mode)
            self.assertEqual(await self.page.evaluate('ultronDiagnostics().context'),context)
            await self.page.evaluate('updateUltron({state:{phase:"active",telemetry:{cpu_percent:7}}})')
            self.assertEqual(await self.page.evaluate('ultronDiagnostics().context'),context)
        await self.page.evaluate('updateUltron({state:{phase:"active"},result:{mode:"diagnostic"}})')
        self.assertEqual(await self.page.evaluate('ultronDiagnostics().context'),'diagnostic')
        self.assertEqual(self.errors,[])

    async def test_disabled_antivirus_is_not_reported_as_active_protection(self):
        await self.page.goto(self.url+'/space.html')
        await self.page.wait_for_function('document.body.dataset.ready==="true"',timeout=45000)
        await self.page.evaluate('''updateUltron({state:{phase:'active',findings:[{id:'defender',title:'Microsoft Defender',detail:{enabled:false,realtime:true},severity:'warning'}]},result:{mode:'diagnostic'}});
            advanceUltron({elapsed:0,cues:['A protecao do Microsoft Defender foi consultada.']});''')
        text=await self.page.locator('#ultron-projection').inner_text()
        self.assertIn('Protecao indisponivel',text)
        self.assertNotIn('Protecao em tempo real ativa',text)
        self.assertEqual(self.errors,[])
