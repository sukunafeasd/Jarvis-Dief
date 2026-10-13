import json
import unittest
from unittest.mock import AsyncMock, Mock, patch

from core.application_context import ApplicationContext
from actions.app_control import app_control


class ContextTests(unittest.TestCase):
    def test_global_desktop_control_refuses_hidden_execution(self):
        from actions.computer_control import computer_control
        with patch('actions.computer_control._click') as click:
            result = computer_control({'action': 'click', 'x': 20, 'y': 20, 'background': True})
            self.assertIn('área de trabalho visível', result)
            click.assert_not_called()

    def test_spotify_followup_stays_in_spotify(self):
        ctx = ApplicationContext()
        ctx.select('spotify')
        ctx.observe_user('pesquisa uma musica aqui')
        from actions.browser_control import browser_control
        with patch('actions.app_control.app_control', return_value='app-result') as app, patch('actions.browser_control._open_native') as web:
            self.assertEqual(browser_control({'action': 'search', 'query': 'Musica'}, session_memory=ctx), 'app-result')
            self.assertEqual(app.call_args.args[0]['app'], 'spotify')
            web.assert_not_called()

    def test_explicit_web_and_different_app_override_context(self):
        ctx = ApplicationContext()
        ctx.select('spotify')
        ctx.observe_user('pesquise no Google')
        self.assertEqual(ctx.search_target(), '')
        ctx.observe_user('procura no Excel')
        self.assertEqual(ctx.search_target(), 'excel')

    def test_expired_context_and_unrelated_request_do_not_route(self):
        clock = Mock(return_value=0)
        ctx = ApplicationContext(clock)
        ctx.select('spotify')
        ctx.observe_user('como esta o clima?')
        self.assertEqual(ctx.search_target(), '')
        clock.return_value = 601
        ctx.observe_user('pesquisa uma musica')
        self.assertEqual(ctx.search_target(), '')

    def test_launch_is_verified_before_context_changes(self):
        from actions import open_app
        ctx = ApplicationContext()
        with patch.object(open_app, '_SYSTEM', 'Windows'), patch.dict(open_app._OS_LAUNCHERS, {'Windows': Mock(return_value=True)}), patch('actions.app_control.app_windows', return_value=[{'handle': 2}]):
            result = json.loads(open_app.open_app({'app_name': 'spotfy'}, session_memory=ctx))
            self.assertTrue(result['ok'])
            self.assertEqual(ctx.current(), 'Spotify')

    def test_aliases_do_not_match_arbitrary_substrings(self):
        from actions.open_app import _normalize
        self.assertEqual(_normalize('news'), 'news')
        self.assertEqual(_normalize('please open Spotify and delete files'), 'please open Spotify and delete files')

    def test_windows_launch_never_uses_global_keyboard(self):
        from actions import open_app
        with patch.object(open_app.shutil, 'which', return_value='C:/test/Spotify.exe'), patch.object(open_app.subprocess, 'Popen') as launch:
            self.assertTrue(open_app._launch_windows('spotify'))
            self.assertEqual(launch.call_args.args[0], ['C:/test/Spotify.exe'])
            self.assertNotIn('shell', launch.call_args.kwargs)


class AppSearchTests(unittest.TestCase):
    def field(self):
        field = Mock()
        field.element_info.control_type = 'Edit'
        field.element_info.name = 'Pesquisar'
        field.is_enabled.return_value = True
        return field

    def test_background_search_verifies_field_without_focus(self):
        field = self.field()
        field.iface_value.CurrentValue = 'Musica'
        with patch('actions.app_control.app_windows', return_value=[{'handle': 4}]), patch('actions.app_control.desktop'), patch('actions.app_control.visible_controls', return_value=[field]):
            result = json.loads(app_control({'app': 'spotify', 'action': 'search', 'query': 'Musica'}))
            self.assertTrue(result['ok'])
            field.iface_value.SetValue.assert_called_once_with('Musica')
            field.set_focus.assert_not_called()
            field.type_keys.assert_not_called()

    def test_ambiguous_fields_do_not_write(self):
        fields = [self.field(), self.field()]
        with patch('actions.app_control.app_windows', return_value=[{'handle': 4}]), patch('actions.app_control.desktop'), patch('actions.app_control.visible_controls', return_value=fields):
            result = json.loads(app_control({'app': 'spotify', 'action': 'search', 'query': 'Musica'}))
            self.assertFalse(result['ok'])
            for field in fields:
                field.iface_value.SetValue.assert_not_called()

    def test_mismatched_value_is_not_success(self):
        field = self.field()
        field.iface_value.CurrentValue = 'outro texto'
        with patch('actions.app_control.app_windows', return_value=[{'handle': 4}]), patch('actions.app_control.desktop'), patch('actions.app_control.visible_controls', return_value=[field]):
            self.assertFalse(json.loads(app_control({'app': 'spotify', 'action': 'search', 'query': 'Musica'}))['ok'])


class BrowserTests(unittest.IsolatedAsyncioTestCase):
    async def test_duplicate_buttons_are_not_clicked(self):
        from actions.browser_control import _BrowserSession
        with patch('actions.browser_control._resolve_browser'):
            sess = _BrowserSession('edge')
        page = Mock()
        loc = Mock()
        page.get_by_role.return_value.filter.return_value = loc
        loc.count = AsyncMock(return_value=2)
        loc.click = AsyncMock()
        sess._get_page = AsyncMock(return_value=page)
        result = await sess.smart_click('Enviar')
        self.assertIn('ambíguo', result)
        loc.click.assert_not_called()

    async def test_background_profile_is_separate_and_headless(self):
        from actions.browser_control import _BrowserSession
        with patch('actions.browser_control._resolve_browser', return_value={'engine': 'chromium', 'exe': None, 'channel': 'msedge'}):
            sess = _BrowserSession('edge', background=True)
        sess._pw = Mock()
        sess._pw.chromium.launch_persistent_context = AsyncMock(return_value=Mock())
        sess._adopt_page = AsyncMock()
        await sess._launch()
        call = sess._pw.chromium.launch_persistent_context.call_args
        self.assertTrue(call.kwargs['headless'])
        self.assertTrue(call.args[0].endswith('edge_background'))
