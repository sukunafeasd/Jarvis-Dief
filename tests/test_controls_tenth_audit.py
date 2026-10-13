import asyncio
import unittest
from unittest.mock import Mock, AsyncMock, patch
from PyQt6.QtWidgets import QDialog
from PyQt6.QtTest import QTest
from PyQt6.QtCore import Qt
import test_scene
import test_fui_screens
import test_refresh_visual
from core.briefing_presentation import explicit_refresh, wants_briefing
from core.environment_director import EnvironmentDirector


class RequestTenthAudit(unittest.TestCase):
    def test_refresh_and_briefing_are_separate_requests(self):
        for text in ('Jarvis, se atualize','me atualiza','atualize seu contexto'):
            self.assertTrue(explicit_refresh(text),text)
            self.assertFalse(wants_briefing(text),text)
        self.assertTrue(wants_briefing('me dê um resumo do dia'))

    def test_explicit_mode_is_not_hidden_by_old_reading_context(self):
        director=EnvironmentDirector();director.command('analise')
        self.assertEqual(director.payload(reading=True,domain='news')['mode'],'analysis')
        self.assertEqual(director.payload(settings=True)['mode'],'focus')


class ContextTenthAudit(unittest.IsolatedAsyncioTestCase):
    async def test_self_update_stores_verified_context_without_summary_cards(self):
        from main import JarvisLive
        assistant=JarvisLive.__new__(JarvisLive);assistant._refresh_summary=False
        assistant.session=Mock();assistant._manual_rest=False;assistant._awake=True
        assistant._is_speaking=False;assistant.audio_in_queue=asyncio.Queue()
        assistant._tail_active=Mock(return_value=False);assistant._turn_done_event=asyncio.Event();assistant.ui=Mock()
        async def complete(**kwargs):
            if kwargs['turn_complete']:
                assistant._played_audio_seconds=getattr(assistant,'_played_audio_seconds',0)+1
                assistant._turn_done_event.set()
        assistant.session.send_client_content=AsyncMock(side_effect=complete)
        package={'data':{'tasks':{'count':2}},'unavailable':[]}
        with patch('core.session_refresh.collect_updates',new=AsyncMock(return_value=package)),patch('core.daily_briefing.mark_delivered'):
            await assistant._send_startup_briefing()
        self.assertEqual(assistant._day_context,package)
        self.assertFalse(any(call.args[0]['kind']=='tasks' for call in assistant.ui.show_manifestation.call_args_list))
        self.assertEqual(sum(call.kwargs['turn_complete'] for call in assistant.session.send_client_content.call_args_list),2)


class ControlTenthAudit(unittest.TestCase):
    setUpClass=classmethod(test_scene.SceneTests.setUpClass.__func__)
    setUp=test_fui_screens.AllSettingsPagesTests.setUp
    tearDown=test_fui_screens.AllSettingsPagesTests.tearDown
    command=test_scene.SceneTests.command

    def test_clear_keeps_pinned_weather_and_saved_data(self):
        self.window._show_manifestation({'kind':'weather','temperature':23})
        self.command('pin')
        self.assertTrue(self.command('clear')['ok'])
        self.assertIn('weather',self.window._pin_previews)
        self.assertEqual(self.window._pin_previews['weather']['data']['temperature'],23)
        self.assertTrue(self.window._pin_previews['weather']['widget'].isVisible())

    def test_f11_targets_main_window_even_when_settings_are_visible(self):
        previous=getattr(self.window,'_settings_hub',None)
        settings=QDialog(self.window);self.window._settings_hub=settings
        try:
            settings.showFullScreen();self.window.showFullScreen()
            QTest.keyClick(self.window._content_display,Qt.Key.Key_F11)
            self.assertFalse(self.window.isFullScreen())
            self.assertTrue(settings.isFullScreen())
        finally:
            settings.close();self.window._settings_hub=previous


class ModeTenthAudit(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=test_refresh_visual.RefreshVisualTests.asyncSetUp
    asyncTearDown=test_refresh_visual.RefreshVisualTests.asyncTearDown

    async def test_modes_change_core_geometry_and_space_has_no_grid(self):
        await self.page.goto(self.url+'/index.html')
        await self.page.wait_for_function('typeof window.updateEnvironment === "function"')
        await self.page.evaluate('window.updateCore({motion:"reduced"})')
        captures=[]
        for mode in ('assistant','analysis','execution','focus'):
            await self.page.evaluate('mode=>window.updateEnvironment({mode})',mode)
            captures.append(await self.page.locator('canvas').screenshot())
            output=test_refresh_visual.BASE/'validation/modes-tenth'
            output.mkdir(parents=True,exist_ok=True)
            await self.page.screenshot(path=str(output/(mode+'.png')))
        self.assertEqual(len(set(captures)),4)
        await self.page.evaluate('window.updateCore({newsFusion:true});window.updateEnvironment({mode:"focus"})')
        self.assertTrue(await self.page.evaluate('window.hologramDiagnostics().coreVisible'))
        await self.page.goto(self.url+'/space.html')
        await self.page.wait_for_function('typeof window.spaceDiagnostics === "function"')
        for mode in ('assistant','analysis','execution','focus','exploration'):
            await self.page.evaluate('mode=>window.updateCore({mode,motion:"reduced"})',mode)
            self.assertEqual(await self.page.evaluate('window.spaceDiagnostics().gridOpacity'),0)
