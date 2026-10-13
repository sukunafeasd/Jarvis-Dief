import unittest
from unittest.mock import Mock
import test_scene
import test_fui_screens
import test_refresh_visual


class FourthInterfaceAudit(unittest.TestCase):
    setUpClass=classmethod(test_scene.SceneTests.setUpClass.__func__)
    setUp=test_fui_screens.AllSettingsPagesTests.setUp
    tearDown=test_fui_screens.AllSettingsPagesTests.tearDown
    command=test_scene.SceneTests.command

    def test_pin_preserves_selected_record_when_expanded(self):
        self.window._show_manifestation({'kind':'gmail','title':'GMAIL','items':[{'title':str(i)} for i in range(3)]})
        self.command('focus','3');self.command('pin')
        self.window._expand_pin('gmail')
        self.assertEqual(self.window._presentation['focus'],2)

    def test_restore_pin_uses_latest_data_not_old_snapshot(self):
        self.window._show_manifestation({'kind':'weather','title':'CLIMA','temperature':19})
        self.command('pin')
        self.window._update_pin('weather',{'kind':'weather','title':'CLIMA','temperature':27})
        self.window._restore_pin()
        self.assertEqual(self.window._presentation['model']['temperature'],27)
        self.assertEqual(self.window._pin_previews['weather']['data']['temperature'],27)

    def test_removing_other_pin_keeps_current_pinned_context(self):
        for kind in ('weather','calendar'):
            self.window._show_manifestation({'kind':kind,'title':kind,'items':[]});self.command('pin')
        self.command('unpin','weather')
        self.assertEqual(self.window._pinned_context['model']['kind'],'calendar')
        self.assertTrue(self.window._pinned)

    def test_saved_pin_can_be_opened_without_history(self):
        self.window._pin_data({'kind':'weather','title':'CLIMA','temperature':19,'restored_snapshot':True})
        self.window._presentation=None;self.window._presentation_history=[]
        self.assertTrue(self.command('open','weather')['ok'])
        self.assertEqual(self.window._presentation['model']['temperature'],19)
        self.assertTrue(self.window._presentation['model']['restored_snapshot'])

    def test_unknown_task_count_does_not_display_none_or_fake_total(self):
        self.window._pin_data({'kind':'tasks','title':'TAREFAS','count':None,'items':[{'title':'Registro parcial'}]})
        text=self.window._pin_previews['tasks']['label'].text()
        self.assertIn('-- pendentes',text)
        self.assertNotIn('None',text)

    def test_bad_title_cannot_crash_manifestation_callback(self):
        self.window._show_manifestation({'kind':'weather','title':23,'temperature':19})
        self.assertTrue(self.window._presentation['title'])
        self.assertTrue(self.window._content_panel.isVisible())

    def test_pin_text_remains_visible_until_renderer_is_ready(self):
        data={'kind':'weather','title':'CLIMA','temperature':19}
        self.window._pin_data(data)
        preview=self.window._pin_previews['weather']
        view=Mock(failed=False,_ready=False);preview['view']=view
        self.window._update_pin('weather',data)
        self.assertTrue(preview['label'].isVisible())
        self.window._pin_ready('weather',Mock(failed=False,_ready=True))
        self.assertTrue(preview['label'].isVisible())
        view._ready=True;self.window._pin_ready('weather',view)
        self.assertFalse(preview['label'].isVisible())
        preview['view']=None


class FourthVisualAudit(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=test_refresh_visual.RefreshVisualTests.asyncSetUp
    asyncTearDown=test_refresh_visual.RefreshVisualTests.asyncTearDown

    async def test_native_pin_has_one_frame_and_standalone_card_keeps_its_frame(self):
        await self.page.goto(self.url+'/presentation.html')
        await self.page.wait_for_function('typeof window.updateCore === "function"')
        model={'kind':'weather','title':'CLIMA','temperature':19,'compact':True,'framed':True,'motion':'reduced'}
        await self.page.evaluate('v=>window.updateCore(v)',model)
        await self.page.wait_for_timeout(200)
        self.assertEqual(await self.page.evaluate('document.body.style.getPropertyValue("--hud-surface")'),'none')
        self.assertEqual(await self.page.evaluate('getComputedStyle(document.querySelector("main"),"::before").display'),'none')
        await self.page.evaluate('v=>window.updateCore({...v,framed:false})',model)
        await self.page.wait_for_timeout(200)
        self.assertNotEqual(await self.page.evaluate('document.body.style.getPropertyValue("--hud-surface")'),'none')
        self.assertEqual(self.errors,[])
