import math
import unittest
import copy
from unittest.mock import patch
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from core.pin_layout import arrange,validate_placement
from core.pinned_scene_store import PinnedSceneStore
import test_scene
import test_fui_screens
import test_refresh_visual


class FreePinTests(unittest.TestCase):
    setUpClass=classmethod(test_scene.SceneTests.setUpClass.__func__)
    setUp=test_fui_screens.AllSettingsPagesTests.setUp
    tearDown=test_fui_screens.AllSettingsPagesTests.tearDown
    command=test_scene.SceneTests.command

    def test_six_domains_survive_and_seventh_is_rejected(self):
        kinds=('weather','tasks','calendar','gmail','whatsapp','system')
        for kind in kinds:self.window._pin_data({'kind':kind,'temperature':19,'items':[]})
        self.assertEqual(len(self.window._pin_previews),6)
        with self.assertRaises(ValueError):self.window._pin_data({'kind':'news','items':[]})
        self.assertEqual(len(self.window._pin_store.load()),6)
        rects=[item['widget'].geometry() for item in self.window._pin_previews.values()]
        self.assertTrue(all(self.window._scene_stage.rect().contains(rect) for rect in rects))
        self.assertFalse(any(a.intersects(b) for i,a in enumerate(rects) for b in rects[i+1:]))

    def test_free_position_size_and_row_persist(self):
        self.window.resize(1920,1080);self.app.processEvents()
        for kind in ('weather','gmail','calendar'):self.window._pin_data({'kind':kind,'items':[]})
        result=self.command('move_pin','weather','{"x":0.32,"y":0.31,"width":0.20,"height":0.22}')
        self.assertTrue(result['ok'])
        item=self.window._pin_previews['weather'];self.assertGreater(item['widget'].x(),100)
        saved=next(p for p in self.window._pin_store.load() if p['key']=='weather')
        self.assertEqual(saved['placement']['x'],.32)
        self.assertTrue(self.command('move_pin','','row')['ok'])
        rects=[item['widget'].geometry() for item in self.window._pin_previews.values()]
        self.assertEqual(len({r.y() for r in rects}),1)
        self.assertEqual(len({r.x() for r in rects}),3)

    def test_failed_move_does_not_mutate_saved_scene(self):
        self.window._pin_data({'kind':'weather','temperature':19})
        before=copy.deepcopy(self.window._pin_previews['weather'].get('placement'))
        with patch.object(self.window,'_save_pins',return_value=False):
            self.assertFalse(self.command('move_pin','weather','{"x":0.3,"y":0.3}')['ok'])
        self.assertEqual(self.window._pin_previews['weather'].get('placement'),before)

    def test_invalid_coordinates_and_old_snapshot_compatibility(self):
        store=PinnedSceneStore(self.visual_folder.name)
        old=[{'key':'weather','data':{'kind':'weather'},'slot':0}]
        self.assertEqual(store.validate(old),old)
        for value in ({'x':math.nan,'y':.2},{'x':True,'y':.2},{'x':2,'y':0},{'x':0,'y':0,'width':0}):
            with self.assertRaises(ValueError):validate_placement(value)

    def test_profile_sizes_are_different_and_small_viewport_fits(self):
        entries={kind:{'data':{'kind':kind,'items':[]}} for kind in ('weather','tasks','calendar','gmail','news','system')}
        for w,h in ((1920,1080),(1200,800),(820,580)):
            rects=arrange(entries,w,h)
            self.assertEqual(len(rects),6)
            self.assertTrue(all(x>=0 and y>=0 and x+rw<=w and y+rh<=h for x,y,rw,rh in rects.values()))
        self.assertGreater(len({(r[2],r[3]) for r in arrange(entries,1920,1080).values()}),3)

    def test_dense_free_placement_has_no_overlaps_and_explicit_size_is_not_capped(self):
        entries={kind:{'data':{'kind':kind,'items':[]}} for kind in ('weather','tasks','calendar','gmail','news','system')}
        entries['weather']['placement']={'x':.3,'y':.4}
        rects=list(arrange(entries,820,580).values())
        from PyQt6.QtCore import QRect
        self.assertFalse(any(QRect(*a).intersects(QRect(*b)) for i,a in enumerate(rects) for b in rects[i+1:]))
        one={'weather':{'data':{'kind':'weather'},'placement':{'x':.02,'y':.1,'width':.8,'height':.8}}}
        self.assertEqual(arrange(one,1200,800)['weather'][2:],(960,640))

    def test_six_pin_row_and_column_are_exact_in_small_viewports(self):
        for mode,w,h in (('row',820,580),('column',1200,800)):
            entries={kind:{'data':{'kind':kind},'placement':{'x':0,'y':0,'layout':mode}} for kind in ('weather','tasks','calendar','gmail','news','system')}
            rects=list(arrange(entries,w,h).values())
            self.assertEqual(len({r[1 if mode=='row' else 0] for r in rects}),1)
            self.assertTrue(all(x+rw<=w and y+rh<=h for x,y,rw,rh in rects))

    def test_individual_move_cannot_displace_grouped_siblings(self):
        self.window.resize(1200,800);self.app.processEvents()
        for kind in ('weather','tasks','calendar'):self.window._pin_data({'kind':kind,'items':[]})
        self.assertTrue(self.command('move_pin','','row')['ok'])
        before={key:item['widget'].geometry() for key,item in self.window._pin_previews.items()}
        self.assertFalse(self.command('move_pin','weather','{"x":0.67,"y":0.685,"width":0.32,"height":0.3}')['ok'])
        self.assertEqual(before,{key:item['widget'].geometry() for key,item in self.window._pin_previews.items()})

    def test_f11_from_settings_restores_visible_window_size(self):
        from core.settings_hub import SettingsHub
        hub=SettingsHub(self.window,self.window._pin_store.folder/'profile.json',__import__('ui').C)
        self.window._settings_hub=hub
        hub.showFullScreen();self.app.processEvents()
        QTest.keyClick(hub.name,Qt.Key.Key_F11);self.app.processEvents()
        self.assertFalse(hub.isFullScreen())
        self.assertLess(hub.width(),hub.screen().availableGeometry().width())
        QTest.qWait(180);QTest.keyClick(hub.name,Qt.Key.Key_F11)
        self.assertTrue(hub.isFullScreen());hub.close();hub.deleteLater()


class WeatherProjectionTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=test_refresh_visual.RefreshVisualTests.asyncSetUp
    asyncTearDown=test_refresh_visual.RefreshVisualTests.asyncTearDown

    async def test_weather_is_unframed_but_pinned_preview_remains_framed(self):
        await self.page.goto(self.url+'/presentation.html')
        await self.page.wait_for_function('typeof window.updateCore==="function"')
        model={'kind':'weather','temperature':19,'condition':'Chuva leve','code':61,'city':'Cidade de teste','narrationDriven':False,
               'forecast':[{'date':'2026-10-14','max':23,'min':17,'rain':80}]}
        for w,h in ((760,630),(390,700)):
            await self.page.set_viewport_size({'width':w,'height':h})
            await self.page.evaluate('value=>window.updateCore(value)',model)
            await self.page.wait_for_timeout(250)
            self.assertEqual(await self.page.get_attribute('body','data-surface'),'projection')
            self.assertEqual(await self.page.evaluate('getComputedStyle(document.body).backgroundImage'),'none')
            metrics=await self.page.locator('#metrics').bounding_box();details=await self.page.locator('#details').bounding_box()
            self.assertGreaterEqual(details['y'],metrics['y']+metrics['height']-1)
            await self.page.screenshot()
        await self.page.evaluate('value=>window.updateCore(value)',{**model,'compact':True,'framed':True})
        self.assertEqual(await self.page.get_attribute('body','data-surface'),'card')
        self.assertEqual(self.errors,[])
