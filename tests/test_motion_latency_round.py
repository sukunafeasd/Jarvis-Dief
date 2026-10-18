"""Local responsiveness regressions; no model, speech provider or accounts."""
import asyncio
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock,patch

from core.environment_director import EnvironmentDirector
from core.forge_host import saved_artifacts_named
from main import JarvisLive
from test_command_delivery_round import owner


class ResponsivenessTests(unittest.IsolatedAsyncioTestCase):
    async def test_rest_acknowledgement_does_not_block_voice_loop(self):
        assistant=owner();assistant._manual_rest=True
        heartbeat=threading.Event();observed=[]
        def control(*args):
            heartbeat.wait(.3);observed.append(heartbeat.is_set())
            return {'ok':True}
        assistant.ui.control_interface.side_effect=control
        async def pulse():
            await asyncio.sleep(.02);heartbeat.set()
        task=asyncio.create_task(pulse())
        await assistant._handle_text_command('bom dia')
        await task
        self.assertEqual(observed,[True])

    async def test_ordinary_screen_request_does_not_initialize_or_wait_for_codex(self):
        assistant=owner();assistant._forge_mode=False
        assistant._queue_daily_briefing.return_value=False
        runtime=Mock();runtime.command.side_effect=AssertionError('Unrelated Codex operation')
        assistant.ui.forge_runtime=runtime
        with patch('core.forge_host.saved_artifacts_named',return_value=[]):
            self.assertFalse(await JarvisLive._route_protocol_user_once(assistant,'mostre o clima na tela'))
        runtime.command.assert_not_called()

    async def test_named_saved_artifact_still_pins_without_catalog_command(self):
        assistant=owner();assistant._forge_mode=False
        assistant.ui.pin_forge_artifact=Mock(return_value={'ok':True})
        from unittest.mock import AsyncMock
        assistant._speak_protocol=AsyncMock()
        artifact={'id':'a'*32,'name':'Reator'}
        with patch('core.forge_host.saved_artifacts_named',return_value=[artifact]):
            self.assertTrue(await JarvisLive._route_protocol_user_once(assistant,'coloque o Reator ao lado'))
        assistant.ui.pin_forge_artifact.assert_called_once_with(artifact)


class EnvironmentAndCatalogTests(unittest.TestCase):
    def test_thinking_does_not_switch_into_analysis(self):
        director=EnvironmentDirector()
        self.assertEqual(director.payload(phase='idle')['mode'],'assistant')
        self.assertEqual(director.payload(phase='thinking')['mode'],'assistant')
        self.assertEqual(director.payload(phase='thinking',domain='system')['mode'],'assistant')

    def test_library_names_are_read_without_creating_runtime(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            artifact=root/'forge/library'/('a'*32)
            artifact.mkdir(parents=True)
            (artifact/'artifact.json').write_text(json.dumps({'id':artifact.name,'name':'Reator'}),encoding='utf-8')
            with patch('core.local_data.ROOT',root),patch('core.forge_host.runtime_for',side_effect=AssertionError('No runtime')):
                self.assertEqual(saved_artifacts_named('reator'),[{'id':artifact.name,'name':'Reator'}])
                self.assertEqual(saved_artifacts_named('clima'),[])

    def test_partial_registration_is_rechecked_without_parent_mtime_change(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);artifact=root/'forge/library'/('b'*32)
            artifact.mkdir(parents=True)
            stamp=artifact.parent.stat().st_mtime_ns
            with patch('core.local_data.ROOT',root),patch('core.forge_host.time.monotonic',return_value=100):
                self.assertEqual(saved_artifacts_named('Reator'),[])
            (artifact/'artifact.json').write_text(json.dumps({'id':artifact.name,'name':'Reator'}),encoding='utf-8')
            self.assertEqual(artifact.parent.stat().st_mtime_ns,stamp)
            with patch('core.local_data.ROOT',root),patch('core.forge_host.time.monotonic',return_value=103):
                self.assertEqual(saved_artifacts_named('Reator'),[{'id':artifact.name,'name':'Reator'}])


class MotionVisualTests(unittest.IsolatedAsyncioTestCase):
    from test_refresh_visual import RefreshVisualTests
    asyncSetUp=RefreshVisualTests.asyncSetUp
    asyncTearDown=RefreshVisualTests.asyncTearDown

    async def test_analysis_and_execution_preserve_solar_without_wires(self):
        await self.page.goto(self.url+'/space.html')
        await self.page.wait_for_function('document.body.dataset.ready==="true"',timeout=45000)
        for mode in ('assistant','analysis','execution'):
            await self.page.evaluate('mode=>updateCore({mode,phase:"thinking",motion:"reduced"})',mode)
            await self.page.wait_for_function('spaceDiagnostics().networkOpacity===0 && spaceDiagnostics().solarVisible')
            state=await self.page.evaluate('spaceDiagnostics()')
            self.assertEqual(state['networkOpacity'],0)
            self.assertGreater(state['solarVisibility'],.4)
            self.assertEqual(state['scheduler'],'animation-frame')
        self.assertEqual(self.errors,[])

    async def test_idle_camera_entrance_is_driven_by_animation_frames(self):
        await self.page.goto(self.url+'/index.html?staged=1')
        await self.page.wait_for_function('document.body.dataset.ready==="true"')
        await self.page.evaluate('updateEnvironment({staging:false,entrance:{at:Date.now(),duration:4300}})')
        initial=await self.page.evaluate('hologramDiagnostics()')
        await self.page.wait_for_timeout(250)
        current=await self.page.evaluate('hologramDiagnostics()')
        self.assertEqual(current['scheduler'],'animation-frame')
        self.assertTrue(current['cameraActive'])
        self.assertLess(current['camera'][2],initial['camera'][2])
        self.assertGreater(current['framesRendered'],initial['framesRendered'])
        self.assertTrue(current['coreVisible'])
        self.assertEqual(self.errors,[])
