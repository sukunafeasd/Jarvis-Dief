import copy
import json
import math
import unittest
from pathlib import Path
from unittest.mock import Mock,patch
from core import visual_library as library
from actions.visual_composer import visual_composer,TOOL
from core.action_loader import discover_actions
import test_scene


def element(identifier='ideia',**kwargs):
    return {'id':identifier,'icon':'pensamento/ideia/orbital','text':'Uma ideia para considerar.','anchor':'alto-direita',**kwargs}


class LibraryTests(unittest.TestCase):
    def test_registry_has_real_recipes_and_unique_semantics(self):
        summary=library.overview()
        self.assertEqual(summary['icons'],1280);self.assertEqual(summary['semantic_concepts'],160)
        self.assertEqual(len(library.PHRASE_BANK),80)
        self.assertEqual(len({item['id'] for item in library.ICONS.values()}),1280)
        for item in library.ICONS.values():
            self.assertIn(item['variant'],library.VARIANTS)
            self.assertIn(item['family'],{'network','slabs','columns','clock','route','message','weather','orbit','spark','circuit','shield','ring','grid'})
            self.assertTrue(item['meaning'])
        stored=json.loads((Path(__file__).resolve().parents[1]/'core/spatial/assets/visual-library.json').read_text(encoding='utf-8'))
        self.assertEqual(stored['icons'],list(library.ICONS.values()))

    def test_query_paginates_without_invented_ids(self):
        first=library.search(query='ideia',limit=3)
        second=library.search(query='ideia',limit=3,offset=first['next_offset'])
        self.assertEqual(first['total'],8)
        self.assertFalse({x['id'] for x in first['items']} & {x['id'] for x in second['items']})
        self.assertTrue(all('ideia' in item['id'] for item in first['items']))

    def test_custom_words_and_symbols_do_not_require_known_topic(self):
        result=library.validate_element({'id':'pergunta_nova','text':'E se a resposta dependesse do contexto?',
            'x':.77,'y':.34,'parts':[{'primitive':'orb'},{'primitive':'ring','slot':'orbita'}]})
        self.assertEqual(result['text'],'E se a resposta dependesse do contexto?')
        self.assertEqual(len(result['parts']),2);self.assertNotIn('recipe',result)

    def test_raw_code_urls_shaders_and_unknown_resources_are_rejected(self):
        for field in ('shader','glsl','geometry','css','html','url','material','code'):
            with self.subTest(field=field),self.assertRaises(ValueError):library.validate_element(element(**{field:'arbitrary'}))
        for value in ('inventado','https://example.com/mesh.glb'):
            with self.assertRaises(ValueError):library.validate_element(element(icon=value))

    def test_bounds_and_complexity_are_finite_and_bounded(self):
        for value in (math.inf,math.nan,-1,2,True):
            with self.subTest(value=value),self.assertRaises(ValueError):library.validate_element(element(x=value,y=.5))
        with self.assertRaises(ValueError):library.validate_request({'action':'compose','elements':[element(str(i)) for i in range(13)]})
        with self.assertRaises(ValueError):library.validate_element(element(parts=[{'primitive':'orb'}]*7))
        with self.assertRaises(ValueError):library.validate_element(element(text='A'*301))

    def test_duplicate_identity_and_total_text_are_rejected(self):
        with self.assertRaises(ValueError):library.validate_request({'action':'compose','elements':[element(),element()]})
        with self.assertRaises(ValueError):library.validate_request({'action':'compose','elements':[element(str(i),text='A'*300) for i in range(7)]})

    def test_real_phrase_lookup_and_plain_text(self):
        item=library.validate_element({'id':'question','phrase':'pergunta/1'})
        self.assertEqual(item['text'],'O que realmente importa aqui?')
        literal='<script>alert("teste")</script>'
        self.assertEqual(library.validate_element(element(text=literal))['text'],literal)

    def test_layout_avoids_protected_bounds_and_reports_hidden_items(self):
        blocked=[{'x':400,'y':240,'width':400,'height':400}]
        items=[library.validate_element(element(str(i),x=.5,y=.5,text='Uma ideia.')) for i in range(10)]
        placed=library.resolve_layout(items,1200,900,blocked)
        visible=[item for item in placed if item['visible']]
        self.assertTrue(visible)
        for index,item in enumerate(visible):
            box=item['bounds'];self.assertGreaterEqual(box['y'],90)
            self.assertFalse(any(library.intersects(box,other) for other in blocked))
            self.assertFalse(any(library.intersects(box,other['bounds']) for other in visible[index+1:]))
        small=library.resolve_layout(items,320,320,[{'x':0,'y':0,'width':320,'height':320}])
        self.assertTrue(all(not item['visible'] and item['placement_note'] for item in small))

    def test_tool_is_discoverable_and_interface_receives_validated_request(self):
        registry=discover_actions(Path(__file__).resolve().parents[1]/'actions',logger=lambda *_:None);self.assertTrue(registry.has('visual_composer'))
        self.assertEqual(TOOL['name'],'visual_composer')
        player=Mock();player.control_interface.return_value={'ok':True,'scene':{'count':1}}
        result=json.loads(visual_composer({'action':'compose','elements':[element()]},player))
        self.assertTrue(result['ok']);self.assertEqual(player.control_interface.call_args.args[0],'visual_scene')
        player.reset_mock()
        self.assertFalse(json.loads(visual_composer({'action':'compose','elements':[element(icon='inexistente')]},player))['ok'])
        player.control_interface.assert_not_called()


class SceneLibraryTests(unittest.TestCase):
    setUpClass=classmethod(test_scene.SceneTests.setUpClass.__func__)
    setUp=test_scene.SceneTests.setUp
    tearDown=test_scene.SceneTests.tearDown
    command=test_scene.SceneTests.command

    def apply(self,**request):
        return self.command('visual_scene',json.dumps(request,ensure_ascii=False))

    def test_creative_scene_without_content_window_and_plain_text(self):
        result=self.apply(action='compose',elements=[element(text='<b>Uma pergunta aberta</b>')])
        self.assertTrue(result['ok']);self.assertFalse(self.window._content_panel.isVisible())
        controller=self.window._visual_scene
        self.assertEqual(controller.items['ideia']['text'],'<b>Uma pergunta aberta</b>')
        self.assertEqual(controller.labels['ideia'].textFormat().name,'PlainText')
        self.assertTrue(result['scene']['elements'][0]['visible'])
        self.assertEqual(self.command('inspect')['screen']['visual_scene']['count'],1)

    def test_update_pin_clear_and_remove_keep_stable_identity(self):
        self.apply(action='compose',elements=[element()])
        self.assertTrue(self.apply(action='pin',id='ideia')['ok'])
        self.apply(action='compose',elements=[element('contexto',text='Um contexto diferente.')])
        self.assertEqual(set(self.window._visual_scene.items),{'ideia','contexto'})
        self.apply(action='clear');self.assertEqual(set(self.window._visual_scene.items),{'ideia'})
        self.apply(action='update',id='ideia',text='A ideia mudou.',x=.15,y=.72)
        self.assertEqual(self.window._visual_scene.items['ideia']['text'],'A ideia mudou.')
        self.assertTrue(self.window._visual_scene.items['ideia']['pinned'])
        self.apply(action='remove',id='ideia');self.assertFalse(self.window._visual_scene.items)
        self.assertFalse(self.window._visual_scene.timer.isActive())

    def test_semantic_cues_follow_played_audio_not_arrival(self):
        self.apply(action='compose',elements=[element('a',cue='ideia central'),element('b',cue='outro caminho')])
        controller=self.window._visual_scene
        controller.enqueue({'text':'Ideia central para pensar com calma. Depois, outro caminho aparece.'})
        self.assertFalse(controller.items['a']['revealed']);self.assertFalse(controller.items['b']['revealed'])
        controller.advance(.1)
        self.assertTrue(controller.items['a']['revealed']);self.assertFalse(controller.items['b']['revealed'])
        for _ in range(6):controller.advance(.5)
        self.assertTrue(controller.items['b']['revealed'])
        self.assertEqual(controller.items['b']['timing'],'audio-estimado')

    def test_interruption_cancels_future_cues_and_timers(self):
        self.apply(action='compose',elements=[element(cue='próximo ponto')])
        controller=self.window._visual_scene;controller.enqueue({'text':'Depois vamos ao próximo ponto.'})
        self.window._cancel_presentation()
        for _ in range(10):controller.advance(.5)
        controller.finish()
        self.assertFalse(controller.items['ideia']['revealed']);self.assertFalse(controller.timer.isActive())
        self.assertFalse(controller.pending_cues)

    def test_cancelled_composition_still_decays_without_animation(self):
        self.apply(action='compose',duration=5,elements=[element('a'),element('b',pinned=True)])
        controller=self.window._visual_scene;now=max(item['created'] for item in controller.items.values())
        controller.cancel();self.assertFalse(controller.timer.isActive())
        with patch('core.visual_scene.time.monotonic',return_value=now+6):controller.expire()
        self.assertEqual(set(controller.items),{'b'});self.assertFalse(controller.expiry.isActive())

    def test_safe_fallback_and_expiration_preserve_pins(self):
        self.apply(action='compose',elements=[element('a',cue='sem áudio'),element('b',pinned=True)])
        controller=self.window._visual_scene;now=max(item['created'] for item in controller.items.values())
        with patch('core.visual_scene.time.monotonic',return_value=now+7):controller.tick()
        self.assertEqual(controller.items['a']['timing'],'fallback-visual')
        with patch('core.visual_scene.time.monotonic',return_value=now+46):controller.tick()
        self.assertEqual(set(controller.items),{'b'})
        self.command('clear');self.assertEqual(set(controller.items),{'b'})

    def test_resize_and_pin_bounds_remain_respected(self):
        self.window._show_manifestation({'kind':'weather','title':'CLIMA','temperature':19});self.command('pin')
        for width,height in ((1200,900),(640,480)):
            self.window.resize(width,height);self.app.processEvents()
            result=self.apply(action='compose',elements=[element('a',anchor='baixo-esquerda'),element('b',anchor='alto-direita',text='Contexto')])
            self.assertTrue(result['ok'])
            visible=[item for item in self.window._visual_scene._placements if item['visible']]
            for item in visible:
                self.assertFalse(any(library.intersects(item['bounds'],other) for other in self.window._visual_scene.blocked()))
            self.window.grab().save(str(Path(__file__).resolve().parents[1]/'validation'/f'biblioteca-fallback-{width}.png'))

    def test_failure_is_atomic_and_pinned_scene_limit_is_enforced(self):
        self.apply(action='compose',elements=[element()])
        before=copy.deepcopy(self.window._visual_scene.items)
        self.assertFalse(self.apply(action='update',id='ideia',icon='inventado')['ok'])
        self.assertEqual(before,self.window._visual_scene.items)
        self.apply(action='compose',elements=[element(str(i),pinned=True,text='Ícone') for i in range(12)])
        self.assertFalse(self.apply(action='compose',elements=[element('novo')])['ok'])
        self.assertEqual(len(self.window._visual_scene.items),12)
