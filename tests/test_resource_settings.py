import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock,patch
from PyQt6.QtWidgets import QApplication
import ui
from core import integration_tokens,gmail_connection,home_automation
from core.plugin_loader import discover_plugins
from core.settings_hub import SettingsHub


class ResourceSettingsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])

    def test_new_external_services_show_disconnected_and_open_configuration(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);config=root/'api_keys.json';config.write_text('{}')
            with patch.object(ui,'API_FILE',config),patch('memory.config_manager.CONFIG_FILE',config),patch.object(integration_tokens,'ROOT',root),patch.object(gmail_connection,'TOKEN',root/'gmail.bin'),patch.object(gmail_connection,'CREDENTIALS',root/'credentials.json'),patch('core.whatsapp_web.PROFILE',root/'whatsapp'):
                registry=discover_plugins(ui.BASE_DIR/'plugins',set(),logger=lambda _:None)
                self.assertGreaterEqual(len(registry.list_for_ui()),35)
                window=ui.MainWindow(str(ui.BASE_DIR/'core/face_model.obj'))
                window.get_plugins=registry.list_for_ui;window.get_plugin_settings=registry.settings_schemas
                hub=SettingsHub(window,config,ui.C);hub.open_page('connections');hub.resize(1000,850);hub.show();self.app.processEvents();hub.refresh()
                for name in ('gmail_compose','outlook_service','home_automation','mcp_bridge'):
                    identifier='plugin:'+name
                    self.assertIn(identifier,hub.connections_page.rows)
                    self.assertEqual(hub.connections_page.rows[identifier].status.text(),'Não conectado')
                    with patch.object(hub,'open_plugin_settings') as open_settings:
                        hub.activate_plugin(name);open_settings.assert_called_once_with(name)
                self.assertTrue(hub.grab().save(str(Path(folder)/'resource-connections.png')))
                for name in ('file_library','task_execution','resource_backups','local_resources','calendar_planning'):
                    row=hub.connections_page.rows['plugin:'+name]
                    self.assertEqual(row.status.text(),'Disponível')
                    self.assertEqual(row.action.text(),'Testar ferramenta')
                    self.assertIsNone(row.configure)
                for name in ('gmail_compose','outlook_service','home_automation','mcp_bridge'):
                    row=hub.connections_page.rows['plugin:'+name]
                    row.set_state('auth_required')
                    self.assertTrue(row.reauthorize.isVisible())
                    with patch.object(hub,'reauthorize_plugin') as reconnect:
                        row.reauthorize.click();reconnect.assert_called_once_with(name)
                    row.resize(390,300);self.app.processEvents()
                    for button in row.actions.findChildren(ui.QPushButton):
                        if button.isVisible():self.assertLessEqual(button.x()+button.width(),row.actions.width())
                with patch('core.resource_policy.external_status',return_value={'configured':True,'connected':True}),patch.object(hub,'_connection_worker') as worker,patch('core.google_services.connect') as connect:
                    hub.reauthorize_plugin('gmail_compose')
                    self.assertEqual(worker.call_args.args[1],'gmail_compose')
                    self.assertTrue(worker.call_args.kwargs['connecting'])
                    worker.call_args.args[0]();connect.assert_called_once_with('gmail_compose')
                sections=registry.settings_schemas()
                for name in ('google_calendar','spotify_control','outlook_service'):
                    section=next(item for item in sections if item['plugin']==name)
                    panel=ui.PluginSettingsOverlay([section],window.centralWidget())
                    button=next(item for item in panel.findChildren(ui.QPushButton) if item.text()==section['setup_label'])
                    with patch('PyQt6.QtGui.QDesktopServices.openUrl',return_value=True) as opened:
                        button.click()
                        self.assertEqual(opened.call_args.args[0].toString(),section['setup_url'])
                    panel.close();panel.deleteLater();self.app.processEvents()
                hub.close();window.close();hub.deleteLater();window.deleteLater();self.app.processEvents()

    def test_home_token_is_protected_not_saved_in_plaintext_form(self):
        schema={'plugin':'home_automation','namespace':'home_automation','title':'Casa','fields':[{'key':'base_url','label':'Servidor','type':'text'},{'key':'access_token','label':'Token','type':'password'}],'values':{}}
        with tempfile.TemporaryDirectory() as folder,patch.object(integration_tokens,'ROOT',Path(folder)),patch('memory.config_manager.save_plugin_config') as save:
            panel=ui.PluginSettingsOverlay([schema])
            panel._widgets[('home_automation','base_url')].setText('http://localhost:8123')
            panel._widgets[('home_automation','access_token')].setText('fixture-private-token-for-testing')
            panel._save_ns('home_automation')
            self.assertEqual(save.call_args.args[1]['access_token'],'')
            self.assertEqual(panel._widgets[('home_automation','access_token')].text(),'')
            raw=(Path(folder)/'token_home_automation.bin').read_bytes()
            self.assertNotIn(b'fixture-private-token-for-testing',raw)
            self.assertEqual(integration_tokens.read('home_automation')['token'],'fixture-private-token-for-testing')
            panel.close();panel.deleteLater();self.app.processEvents()
