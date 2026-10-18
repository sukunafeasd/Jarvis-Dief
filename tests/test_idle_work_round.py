"""Offline work budgets: no accounts, models or physical audio."""
import json
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from core.plugin_loader import PluginRegistry, PluginRecord


class RegistryWorkTests(unittest.TestCase):
    def registry(self):
        records = [PluginRecord(name='plugin_'+str(i), file='fixture.py', valid=True,
                                settings={'namespace':'plugin_'+str(i),'fields':[]}) for i in range(40)]
        registry = PluginRegistry({record.name:record for record in records}, logger=lambda text:None)
        registry._all_records = records
        return registry

    def test_catalog_reads_configuration_once_and_sees_next_change(self):
        from memory import config_manager as config
        registry = self.registry()
        with tempfile.TemporaryDirectory() as folder, patch.object(config, 'CONFIG_FILE', Path(folder)/'config.json'):
            path = config.CONFIG_FILE
            path.write_text(json.dumps({'plugins_enabled':{'plugin_0':False}}))
            original = Path.read_text
            reads = []
            def read(file, *args, **kwargs):
                if file == path:
                    reads.append(file)
                return original(file, *args, **kwargs)
            with patch.object(Path, 'read_text', read):
                catalog = registry.list_for_ui()
            self.assertEqual(len(reads), 1)
            self.assertFalse(catalog[0]['enabled'])
            path.write_text('{"plugins_enabled":{"plugin_0":true}}')
            self.assertTrue(registry.list_for_ui()[0]['enabled'])

    def test_settings_catalog_reads_one_snapshot_and_keeps_namespaces_separate(self):
        from memory import config_manager as config
        registry = self.registry()
        with tempfile.TemporaryDirectory() as folder, patch.object(config, 'CONFIG_FILE', Path(folder)/'config.json'):
            path = config.CONFIG_FILE
            path.write_text(json.dumps({'plugins_enabled':{'plugin_0':False},
                                        'plugin_config':{'plugin_1':{'endpoint':'fixture'}}}))
            original = Path.read_text
            reads = []
            def read(file, *args, **kwargs):
                if file == path:
                    reads.append(file)
                return original(file, *args, **kwargs)
            with patch.object(Path, 'read_text', read):
                sections = registry.settings_schemas()
            self.assertEqual(len(reads), 1)
            self.assertEqual(len(sections), 39)
            self.assertEqual(sections[0]['values'], {'endpoint':'fixture'})


class SettingsTickTests(unittest.TestCase):
    def test_hidden_or_minimized_settings_do_not_refresh(self):
        from core.settings_hub import SettingsHub
        hub = SimpleNamespace(isVisible=Mock(return_value=False), isMinimized=Mock(return_value=False), refresh=Mock())
        SettingsHub._refresh_tick(hub)
        hub.refresh.assert_not_called()
        hub.isVisible.return_value = True
        hub.isMinimized.return_value = True
        SettingsHub._refresh_tick(hub)
        hub.refresh.assert_not_called()
        hub.isMinimized.return_value = False
        SettingsHub._refresh_tick(hub)
        hub.refresh.assert_called_once_with(active_only=True)


import test_scene
import test_fui_screens


class NativeSettingsWorkTests(unittest.TestCase):
    setUpClass = classmethod(test_scene.SceneTests.setUpClass.__func__)

    def setUp(self):
        test_fui_screens.AllSettingsPagesTests.setUp(self)
        import ui
        from core.settings_hub import SettingsHub
        self.hub = SettingsHub(self.window, ui.API_FILE, ui.C)

    def tearDown(self):
        self.hub.close();self.hub.deleteLater();self.app.processEvents()
        test_fui_screens.AllSettingsPagesTests.tearDown(self)

    def test_profile_tick_does_not_read_logs_or_poll_plugins(self):
        hub = self.hub
        hub.show();hub.open_page('profile');self.app.processEvents()
        with patch.object(self.window, 'get_plugins', Mock()) as inventory, \
                patch.object(self.window._log, 'toPlainText', wraps=self.window._log.toPlainText) as log, \
                patch.object(hub.connections_page, 'refresh') as connections:
            for _ in range(10):hub._refresh_tick()
        inventory.assert_not_called();log.assert_not_called();connections.assert_not_called()
        with patch.object(hub.connections_page, 'refresh') as connections:
            hub.open_page('connections')
            connections.assert_called_once()

    def test_hidden_settings_stop_timer_and_reopening_resumes(self):
        self.assertFalse(self.hub.timer.isActive())
        self.hub.show();self.app.processEvents()
        self.assertTrue(self.hub.timer.isActive())
        self.hub.hide();self.app.processEvents()
        self.assertFalse(self.hub.timer.isActive())
        self.hub.show();self.app.processEvents()
        self.assertTrue(self.hub.timer.isActive())

    def test_hidden_successful_reconnection_is_not_reported_as_timeout(self):
        self.window._connection_status={'connected':False,'revision':1}
        self.window.on_connection_test=Mock()
        self.hub.show();self.hub.check_ai();self.hub.hide()
        self.window._connection_status={'connected':True,'revision':2}
        self.hub._ai_test_timeout()
        self.assertIsNone(self.hub._ai_check)
        self.assertEqual(self.hub._connection_checks.get('ai')['state'], 'connected')

    def test_unchanged_row_does_not_recreate_its_icon(self):
        import core.settings_connections as connections
        row = self.hub.connections_page.rows['ai']
        row.set_state('connected', 'Same state')
        with patch.object(connections, 'glyph', wraps=connections.glyph) as icon:
            for _ in range(10):row.set_state('connected', 'Same state')
            icon.assert_not_called()
            row.set_state('error', 'Changed state')
            self.assertEqual(icon.call_count, 1)
        self.assertEqual(row.status.text(), connections.STATES['error'][0])

    def test_extension_status_is_not_reprobed_between_cached_refreshes(self):
        page = self.hub.connections_page
        page._external_local.clear()
        with patch('core.settings_connections.local_status', return_value={
                'installed':True,'local_available':True}) as local, \
                patch('core.extension_suite.status', side_effect=AssertionError('Duplicate probe')):
            for _ in range(10):
                page.refresh_plugins({'markitdown':{'valid':True,'enabled':True}})
        self.assertEqual(local.call_count, 1)

    def test_new_rows_share_one_settings_catalog(self):
        page = self.hub.connections_page
        mapping = {'fixture_'+str(i):{'valid':True,'enabled':True} for i in range(4)}
        with patch.object(self.window, 'get_plugin_settings', Mock(return_value=[{'plugin':'fixture_1'}])) as catalog:
            page.refresh_plugins(mapping)
            page.refresh_plugins(mapping)
        self.assertEqual(catalog.call_count, 1)
        self.assertIsNotNone(page.rows['plugin:fixture_1'].configure)
        self.assertIsNone(page.rows['plugin:fixture_0'].configure)
