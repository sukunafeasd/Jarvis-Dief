import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import unittest
from pathlib import Path
from unittest.mock import patch
import test_scene
import test_fui_screens
import test_refresh_visual

OUTPUT=Path(__file__).resolve().parents[1]/'validation/universal-pins'


class UniversalPinTests(unittest.TestCase):
    setUpClass=classmethod(test_scene.SceneTests.setUpClass.__func__)
    setUp=test_fui_screens.AllSettingsPagesTests.setUp
    tearDown=test_fui_screens.AllSettingsPagesTests.tearDown
    command=test_scene.SceneTests.command

    def test_every_consulted_kind_pins_and_clears_without_losing_preview(self):
        for kind in ('weather','tasks','calendar','gmail','whatsapp','news','system','memory','search','files','data'):
            self.window._show_manifestation({'kind':kind,'title':'Demonstracao','temperature':23,'count':2,
                'items':[{'title':'Dados de teste','detail':'Exemplo sintetico'}]})
            result=self.command('pin')
            self.assertTrue(result['ok'],(kind,result))
            self.assertIn(kind,self.window._pin_previews)
            self.assertEqual(self.window._pin_previews[kind]['data']['kind'],kind)
            self.assertTrue(self.command('clear')['ok'])
            self.assertIn(kind,self.window._pin_previews)
            self.assertTrue(self.command('unpin',kind)['ok'])

    def test_portuguese_alias_resolves_previous_domain(self):
        self.window._show_manifestation({'kind':'calendar','items':[{'title':'Compromisso'}]})
        self.window._show_manifestation({'kind':'weather','temperature':23})
        self.assertTrue(self.command('pin','agenda')['ok'])
        self.assertIn('calendar',self.window._pin_previews)
        self.assertTrue(self.command('unpin','compromissos')['ok'])

    def test_textual_content_pins_without_inventing_facts(self):
        self.window._show_content('Explicacao','Resposta de demonstracao.')
        self.assertTrue(self.command('pin')['ok'])
        self.assertEqual(self.window._pin_previews['data']['data']['text'],'Resposta de demonstracao.')

    def test_restore_is_idempotent_and_progress_cannot_be_pinned(self):
        self.window._show_manifestation({'kind':'status','title':'Consultando','items':[]})
        self.assertFalse(self.command('pin')['ok'])
        self.window._pins_restored=False
        self.window._pending_saved_pins=None
        with patch.object(self.window._pin_store,'load',return_value=[]) as load:
            self.window._restore_saved_pins();self.window._restore_saved_pins()
            load.assert_called_once()

    def test_early_pin_merges_saved_records_before_deferred_restore(self):
        import copy
        from unittest.mock import Mock
        records=[{'key':'calendar','data':{'kind':'calendar','title':'Agenda salva','items':[{'title':'Compromisso salvo'}]},'slot':1}]
        store=Mock();store.load.side_effect=lambda:copy.deepcopy(records)
        def save(value):records[:]=copy.deepcopy(value)
        store.save.side_effect=save
        self.window._pin_store=store;self.window._pins_restored=False;self.window._pending_saved_pins=None
        self.window._pin_data({'kind':'tasks','count':1,'items':[{'title':'Tarefa nova'}]})
        self.assertEqual({pin['key'] for pin in records},{'tasks','calendar'})
        self.window._restore_saved_pins()
        self.assertEqual(set(self.window._pin_previews),{'tasks','calendar'})

    def test_failed_load_retries_without_overwriting_existing_cache(self):
        from unittest.mock import Mock
        store=Mock();store.load.side_effect=[OSError('temporario'),[{'key':'calendar','data':{'kind':'calendar','items':[]},'slot':1}]]
        self.window._pin_store=store;self.window._pins_restored=False;self.window._pending_saved_pins=None
        self.window._restore_saved_pins()
        self.assertFalse(self.window._pins_restored);store.save.assert_not_called()
        self.window._restore_saved_pins()
        self.assertTrue(self.window._pins_restored);self.assertIn('calendar',self.window._pin_previews)

    def test_saved_capacity_does_not_allow_replacing_other_pins(self):
        from unittest.mock import Mock
        saved=[{'key':kind,'data':{'kind':kind,'items':[]},'slot':i} for i,kind in enumerate(('calendar','gmail','news','memory'))]
        self.window._pin_store=Mock();self.window._pin_store.load.return_value=saved
        self.window._pins_restored=False;self.window._pending_saved_pins=None
        with self.assertRaises(ValueError):self.window._pin_data({'kind':'tasks','count':1})
        self.window._pin_store.save.assert_not_called()

    def test_failed_save_rolls_back_new_and_existing_preview(self):
        import copy
        from unittest.mock import Mock
        records=[]
        store=Mock();store.load.return_value=[]
        def save(value):records[:]=copy.deepcopy(value)
        self.window._pin_store=store;self.window._pins_restored=True
        store.save.side_effect=OSError('temporario')
        with self.assertRaises(ValueError):self.window._pin_data({'kind':'tasks','count':9})
        self.assertNotIn('tasks',self.window._pin_previews)
        store.save.side_effect=save
        self.window._pin_data({'kind':'calendar','title':'Agenda antiga','items':[]})
        self.assertEqual({pin['key'] for pin in records},{'calendar'})
        store.save.side_effect=OSError('temporario')
        with self.assertRaises(ValueError):self.window._pin_data({'kind':'calendar','title':'Alteracao rejeitada','items':[]})
        self.assertEqual(self.window._pin_previews['calendar']['data']['title'],'Agenda antiga')
        self.assertEqual(self.window._pin_previews['calendar']['restore'].text(),'Agenda antiga')


class UniversalSymbolTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=test_refresh_visual.RefreshVisualTests.asyncSetUp
    asyncTearDown=test_refresh_visual.RefreshVisualTests.asyncTearDown

    async def test_pinned_news_search_data_symbols_have_volume_and_move(self):
        OUTPUT.mkdir(parents=True,exist_ok=True)
        await self.page.goto(self.url+'/presentation.html')
        await self.page.wait_for_function('typeof window.holographicMotionDiagnostics==="function"')
        await self.page.set_viewport_size({'width':288,'height':150})
        for kind in ('weather','tasks','calendar','gmail','whatsapp','news','system','memory','search','files','data'):
            await self.page.evaluate('m=>window.updateCore(m)',{'kind':kind,'title':'Demonstracao','compact':True,'framed':True,'motion':'full','count':2,
                'code':61,'temperature':23,'condition':'Chuva','cpu_percent':35,'ram_percent':65,'items':[{'title':'Informacao real de teste','value':'23','detail':'Exemplo sintetico'}]})
            await self.page.wait_for_timeout(1300)
            first=await self.page.locator('#scene').screenshot()
            diag=await self.page.evaluate('window.holographicMotionDiagnostics()')
            self.assertGreaterEqual(diag['drawCalls'],2,kind);self.assertLess(diag['drawCalls'],35,kind)
            await self.page.wait_for_timeout(500)
            self.assertNotEqual(first,await self.page.locator('#scene').screenshot(),kind)
            if kind=='news':self.assertEqual(await self.page.evaluate('document.body.dataset.layout'),'object')
            await self.page.screenshot(path=str(OUTPUT/(kind+'.png')))
        self.assertEqual(self.errors,[])

    async def test_staged_shader_preparation_keeps_core_hidden_until_entrance(self):
        await self.page.goto(self.url+'/index.html?staged=1')
        await self.page.wait_for_function('document.body.dataset.ready==="true"')
        before=await self.page.evaluate('window.hologramDiagnostics()')
        self.assertFalse(before['coreVisible'])
        self.assertEqual(before['assembly'],1)
        visible=await self.page.evaluate('() => {window.updateEnvironment({staging:false,entrance:{at:Date.now(),duration:4300,cancelAt:null}});return window.hologramDiagnostics().coreVisible;}')
        self.assertTrue(visible)
        await self.page.wait_for_timeout(400)
        after=await self.page.evaluate('window.hologramDiagnostics()')
        self.assertTrue(after['coreVisible']);self.assertGreater(after['travel'],15)
        self.assertEqual(before['geometries'],after['geometries'])
        self.assertEqual(self.errors,[])


class VeilTests(unittest.TestCase):
    def test_loading_always_has_distant_hub_and_release_stops_animation(self):
        from PyQt6.QtWidgets import QApplication,QWidget
        from PyQt6.QtTest import QTest
        from core.opening_veil import OpeningVeil
        app=QApplication.instance() or QApplication([])
        parent=QWidget();parent.resize(800,500);veil=OpeningVeil(parent);veil.setGeometry(parent.rect());parent.show();veil.show()
        try:
            QTest.qWait(100)
            image=veil.grab().toImage();center=image.pixelColor(400,250)
            self.assertGreater(center.red(),center.blue())
            self.assertTrue(veil.timer.isActive())
            veil.release();QTest.qWait(450)
            self.assertFalse(veil.isVisible());self.assertFalse(veil.timer.isActive())
        finally:parent.close();parent.deleteLater();app.processEvents()
