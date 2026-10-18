"""Offline regression tests using synthetic speech and application state."""
import ast
import copy
import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from core.presentation_clock import PresentationClock
import test_refresh_visual
import test_presentation_state_gap


BASE = Path(__file__).resolve().parents[1]


def method(path, owner, name):
    tree = ast.parse((BASE / path).read_text(encoding='utf-8'))
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == owner)
    node = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == name)
    namespace = {'copy': copy, 'json': json, 'C': SimpleNamespace(PRI='#ffffff', WHITE='#ffffff'), '_read_full_config': lambda: {}}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(BASE / path), 'exec'), namespace)
    return namespace[name]


class SyncContractTests(unittest.TestCase):
    def test_large_played_batch_does_not_lose_audio_time_or_delay_topic(self):
        clock = PresentationClock()
        clock.enqueue('Segunda noticia.', at=1.2)
        self.assertEqual(clock.advance(1.5)['cues'], ['Segunda noticia.'])
        self.assertEqual(clock.elapsed, 1.5)

    def test_drain_discards_future_cues_and_late_pcm_without_resetting_time(self):
        clock = PresentationClock()
        clock.advance(.3)
        clock.enqueue('Nao chegou a ser falado.', at=5)
        clock.finish()
        self.assertFalse(clock.pending)
        self.assertFalse(clock.active)
        self.assertEqual(clock.advance(10)['elapsed'], .3)
        clock.replace_scene()
        clock.enqueue('Novo assunto.', at=.3)
        self.assertEqual(clock.advance(.1)['cues'], ['Novo assunto.'])

    def test_scene_end_freezes_typing_and_never_reveals_unspoken_pinned_item(self):
        finish = method('core/visual_scene.py', 'VisualSceneController', 'finish')
        clock = PresentationClock()
        clock.advance(.1)
        items = {'pin': {'revealed': False, 'pinned': True},
                 'text': {'revealed': True, 'chars': 3, 'text': 'Texto sintetico'}}
        scene = SimpleNamespace(cancelled=False, clock=clock, items=items,
                                pending_cues=[{'id': 'pin', 'at': 7}], timer=Mock(), reflow=Mock(), render_text=Mock())
        before = copy.deepcopy(items)
        finish(scene)
        self.assertEqual(scene.items['pin'], before['pin'])
        self.assertEqual(scene.items['text']['chars'], len(items['text']['text']))
        self.assertFalse(scene.pending_cues)
        self.assertTrue(clock.finished)
        scene.timer.stop.assert_called_once()

    def test_completed_navigation_cannot_change_current_topic(self):
        navigate = method('ui.py', 'MainWindow', '_spatial_navigation')
        window = SimpleNamespace(_presentation={'completed': True, 'focus': 0})
        navigate(window, SimpleNamespace(fragment=lambda: 'speech-focus-1-2-scene'))
        self.assertEqual(window._presentation['focus'], 0)

    def test_new_speech_retires_old_completed_topic_but_preserves_pins_and_refresh(self):
        apply_state = method('ui.py', 'MainWindow', '_apply_state')
        for pinned, locked in ((False, False), (True, False), (False, True)):
            window = test_presentation_state_gap.PresentationStateGapTests().window()
            window.hud.state = 'LISTENING'
            window.hud.speaking = False
            window._presentation.update(completed=True, narration_active=False, audio_started=False)
            window._pinned = pinned
            window._refresh_lock = 'refresh' if locked else None
            window._presentation_history = []
            window._content_panel = Mock()
            window._layout_scene = Mock()
            apply_state(window, 'SPEAKING')
            if pinned or locked:
                self.assertIsNotNone(window._presentation)
                window._content_panel.hide.assert_not_called()
            else:
                self.assertIsNone(window._presentation)
                self.assertEqual(len(window._presentation_history), 1)
                window._content_panel.hide.assert_called_once()

    def test_finished_native_scene_ignores_new_cue_until_playback_resumes(self):
        advance = method('core/visual_scene.py', 'VisualSceneController', 'advance')
        clock = PresentationClock()
        clock.advance(.2)
        clock.finish()
        item = {'created': 1, 'revealed': False}
        scene = SimpleNamespace(clock=clock, cancelled=False, items={'next': item},
                                pending_cues=[{'at': 0, 'id': 'next', 'created': 1}], reflow=Mock(), tick=Mock())
        advance(scene, .1)
        self.assertFalse(item['revealed'])
        scene.reflow.assert_not_called()

    def test_native_fallback_uses_transparent_projection_surface(self):
        sync = method('ui.py', 'MainWindow', '_sync_presentation_view')
        window = Mock()
        window._content_spatial = None
        window._native_content_header.count.return_value = 0
        window.hud._spatial_core = None
        sync(window, {'kind': 'weather'})
        style = window._content_display.setStyleSheet.call_args.args[0]
        self.assertIn('background:transparent', style)
        self.assertIn('border:0', style)

    def test_snapshot_reports_visible_pins_when_transient_panel_is_hidden(self):
        snapshot = method('ui.py', 'MainWindow', 'interface_snapshot')
        window = Mock()
        window._presentation = None
        window._space_view = None
        scene={'count':0,'elements':[],'library_available':True}
        window._visual_scene = Mock()
        window._visual_scene.snapshot.return_value = scene
        window._scene_animations = []
        window._settings_hub = None
        window._daily_refresh_view = None
        window.isVisible.return_value=True
        window.isMinimized.return_value=False
        window._attachments = {}
        window._pinned_context = None
        window._presentation_history = []
        window._environment.snapshot.return_value = {}
        window._content_panel.isVisible.return_value = False
        window._terminal.isVisible.return_value = False
        window._execution.isVisible.return_value = False
        pin = Mock()
        pin.isVisible.return_value = True
        window._pin_previews = {'weather': {'data': {'title': 'Clima de teste', 'temperature': 21}, 'widget': pin}}
        result = snapshot(window)
        self.assertEqual(result['visual_scene'],scene)
        self.assertFalse(result['layout_animating'])
        self.assertTrue(result['observation']['has_visible_content'])
        self.assertFalse(result['observation']['screen_capture'])
        self.assertIsNone(result['presentation']['content'])
        self.assertEqual(result['pinned_previews'][0]['content']['temperature'], 21)
        pin.isVisible.return_value = False
        result = snapshot(window)
        self.assertFalse(result['observation']['has_visible_content'])
        self.assertIsNone(result['pinned_previews'][0]['content'])
        window._ultron_payload={'state':{'phase':'diagnostic','telemetry':{'cpu_percent':12}}}
        result=snapshot(window)
        self.assertTrue(result['observation']['has_visible_content'])
        self.assertEqual(result['protocols']['ultron']['state']['telemetry']['cpu_percent'],12)
        window._ultron_payload=None
        window._daily_refresh_view=Mock(transaction='refresh')
        window._daily_refresh_view.isVisible.return_value=True
        result=snapshot(window)
        self.assertTrue(result['observation']['has_visible_content'])
        self.assertTrue(result['daily_refresh']['visible'])


class SyncBrowserTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = test_refresh_visual.RefreshVisualTests.asyncSetUp
    asyncTearDown = test_refresh_visual.RefreshVisualTests.asyncTearDown

    async def ready(self, model):
        await self.page.route('**/*', lambda route: route.continue_() if route.request.url.startswith(self.url + '/') else route.abort())
        await self.page.goto(self.url + '/presentation.html')
        await self.page.wait_for_function('typeof window.updateCore === "function"')
        await self.page.evaluate('model=>window.updateCore(model)', model)

    async def test_finish_and_cancel_stop_letters_and_ignore_late_subject_cues(self):
        for ending in ('finishPresentation', 'cancelPresentation'):
            await self.ready({'kind': 'news', 'presentationId': ending, 'narrationDriven': True,
                              'items': [{'title': 'Pesquisa lunar com texto longo de demonstracao'},
                                        {'title': 'Outro assunto orbital'}]})
            await self.page.evaluate('window.advancePresentation({elapsed:.7,cues:[]})')
            await self.page.wait_for_timeout(100)
            await self.page.evaluate('name=>window[name]()', ending)
            before = await self.page.locator('#summary').inner_text()
            await self.page.evaluate('window.advancePresentation({elapsed:30,cues:["Segunda noticia."]})')
            await self.page.wait_for_timeout(700)
            self.assertEqual(await self.page.locator('#summary').inner_text(), before)
            self.assertEqual(await self.page.locator('.selected').get_attribute('data-index'), '0')
            await self.page.evaluate('window.resumePresentation();window.advancePresentation({elapsed:1,cues:["Segunda noticia."]})')
            self.assertEqual(await self.page.locator('.selected').get_attribute('data-index'), '1')
        self.assertEqual(self.errors, [])

    async def test_finished_unspoken_details_stay_hidden_and_live_surface_is_transparent(self):
        await self.ready({'kind': 'gmail', 'presentationId': 'mail', 'narrationDriven': True,
                          'items': [{'title': 'Mensagem sintetica', 'detail': 'Nao foi narrada'}]})
        await self.page.evaluate('window.advancePresentation({elapsed:2,cues:[]});window.finishPresentation()')
        await self.page.wait_for_timeout(700)
        self.assertEqual(await self.page.locator('.record p').inner_text(), '')
        for width, height in ((1200, 900), (390, 844)):
            await self.page.set_viewport_size({'width': width, 'height': height})
            await self.page.evaluate('window.updateCore({kind:"weather",presentationId:"weather",temperature:21,narrationDriven:false})')
            await self.page.wait_for_timeout(250)
            self.assertEqual(await self.page.evaluate('document.body.dataset.surface'), 'projection')
            self.assertEqual(await self.page.evaluate('getComputedStyle(document.body).backgroundImage'), 'none')
            self.assertFalse(await self.page.evaluate('document.documentElement.scrollWidth>innerWidth'))
            await self.page.wait_for_timeout(450)
            output = BASE / 'validation' / 'presentation-sync'
            output.mkdir(parents=True, exist_ok=True)
            await self.page.evaluate('document.documentElement.style.background="#03070a"')
            await self.page.screenshot(path=str(output / f'weather-{width}.png'))
            pixels = await self.page.locator('#scene').screenshot()
            from PIL import Image, ImageChops
            from io import BytesIO
            image = Image.open(BytesIO(pixels)).convert('RGB')
            self.assertIsNotNone(ImageChops.difference(image, Image.new('RGB', image.size, image.getpixel((0, 0)))).getbbox())
        self.assertEqual(self.errors, [])


if __name__ == '__main__':
    unittest.main()
