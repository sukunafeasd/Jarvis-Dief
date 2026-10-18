import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import Mock,patch
from PyQt6.QtWidgets import QApplication
from core.connection_states import ConnectionChecks,resolve


class StateTests(unittest.TestCase):
    def test_saved_credentials_are_not_live_connections(self):
        self.assertEqual(resolve('gmail',{'connected':True}),'pending')
        self.assertEqual(resolve('whatsapp',{'saved_session':True}),'pending')
        self.assertEqual(resolve('iphone',{}),'unverified')
        self.assertEqual(resolve('gmail',{}, {'state':'error'}),'error')
        self.assertEqual(resolve('gmail',{}, {'state':'auth_required'}),'auth_required')
        self.assertEqual(resolve('gmail',{'connected':True},{'state':'connected'}),'connected')

    def test_cache_generation_duplicate_expiry_and_isolation(self):
        now=[0];checks=ConnectionChecks(lambda:now[0])
        first=checks.begin('gmail');self.assertIsNone(checks.begin('gmail'))
        self.assertIsNotNone(checks.begin('whatsapp'))
        checks.invalidate('gmail');second=checks.begin('gmail')
        self.assertFalse(checks.finish('gmail',first,'connected','old'))
        self.assertTrue(checks.finish('gmail',second,'connected','verified'))
        snapshot=checks.get('gmail');snapshot['state']='error'
        self.assertEqual(checks.get('gmail')['state'],'connected')
        now[0]=301;self.assertTrue(checks.get('gmail')['stale'])
        self.assertEqual(checks.get('gmail')['state'],'connected')
        self.assertTrue(checks.get('whatsapp')['busy'])

    def test_plugins_do_not_fake_external_connection(self):
        self.assertEqual(resolve('x',{},plugin={'valid':True,'enabled':True}),'local')
        self.assertEqual(resolve('x',{},plugin={'valid':True,'enabled':False}),'disabled')
        self.assertEqual(resolve('x',{},plugin={'valid':False,'enabled':True}),'broken')


class ConnectionsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])
        cls.app.setStyle('Fusion')

    def setUp(self):
        import ui
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.config=Path(self.temp.name)/'config.json';self.config.write_text('{}')
        self.gmail_status={'connected':True,'account_email':'conta@example.test'}
        patches=[patch.object(ui,'API_FILE',self.config),
            patch('core.gmail_connection.status',side_effect=lambda:dict(self.gmail_status)),
            patch('core.gmail_connection.expected_account',return_value='conta@example.test'),
            patch('core.gmail_connection.credential_client_id',return_value=''),
            patch('core.gmail_connection.CREDENTIALS',Path(self.temp.name)/'missing.json'),
            patch('core.whatsapp_web.PROFILE',Path(self.temp.name)/'missing-profile')]
        for item in patches:item.start();self.addCleanup(item.stop)
        self.window=ui.MainWindow(str(ui.BASE_DIR/'core/face_model.obj'))
        self.window.on_voice_change=Mock()
        self.window.get_plugins=lambda:[{'name':'gmail_control','valid':True,'enabled':True},
            {'name':'whatsapp_web','valid':True,'enabled':True},
            {'name':'desktop_accessibility','valid':True,'enabled':True},
            {'name':'sample_plugin','valid':True,'enabled':False}]
        self.window.get_plugin_settings=lambda:[]
        from core.settings_hub import SettingsHub
        self.hub=SettingsHub(self.window,self.config,ui.C)
        self.page=self.hub.connections_page
        self.addCleanup(self.cleanup_widgets)

    def cleanup_widgets(self):
        self.hub.close();self.window.close();self.hub.deleteLater();self.window.deleteLater();self.app.processEvents()

    def finish(self,provider,state):
        generation=self.hub._connection_checks.begin(provider)
        self.hub._connection_checks.finish(provider,generation,state,'Resultado de teste')
        self.hub.refresh()

    def test_pending_connected_and_error_actions(self):
        self.assertEqual(self.page.rows['gmail'].status.text(),'Verificação pendente')
        self.finish('gmail','connected')
        row=self.page.rows['gmail'];self.assertEqual(row.status.text(),'Conectado')
        self.assertEqual(row.action.text(),'Testar conexão')
        with patch.object(self.hub,'check_gmail') as check,patch.object(self.hub,'connect_gmail') as connect:
            row.action.click();check.assert_called_once();connect.assert_not_called()
        self.finish('gmail','error');self.assertEqual(row.action.text(),'Testar novamente')

    def test_categories_keep_accounts_native_and_skills_separate(self):
        self.assertEqual([self.page.categories.tabText(i) for i in range(3)],['Contas','Plugins nativos','Skills'])
        self.assertIs(self.page.rows['gmail'].parentWidget(),self.page.body)
        self.assertIs(self.page.rows['plugin:sample_plugin'].parentWidget(),self.page.native_body)
        self.assertGreaterEqual(len(self.page.skill_rows),27)
        self.assertTrue(all(row.status.text()=='Ativa' for row in self.page.skill_rows.values()))
        for index in range(3):
            self.page.categories.setCurrentIndex(index)
            self.assertEqual(self.page.pages.currentIndex(),index)

    def test_connection_editor_can_reopen_and_save_without_disappearing(self):
        self.window.get_plugin_settings=lambda:[{'namespace':'sample_plugin','title':'Teste','fields':[{'key':'key','type':'secret','label':'Chave'}]}]
        self.hub.show();self.hub.open_page('connections')
        with patch('memory.config_manager.save_plugin_config') as save:
            for value in ('first-synthetic','second-synthetic'):
                self.hub.open_plugin_settings('sample_plugin');self.app.processEvents()
                panel=self.hub._detail_overlay
                self.assertTrue(panel.isVisible())
                field=panel._widgets[('sample_plugin','key')]
                from PyQt6.QtWidgets import QLineEdit
                self.assertEqual(field.echoMode(),QLineEdit.EchoMode.Password)
                field.setText(value);panel._save_all()
                save.assert_called_with('sample_plugin',{'key':value})
                self.assertIn('Salvo',panel._status_labels['sample_plugin'].text())
                panel.hide();self.app.processEvents();self.app.processEvents()
            self.assertEqual(save.call_count,2)

    def test_save_error_is_visible_and_keeps_inflight_action_locked(self):
        import ui
        panel=ui.PluginSettingsOverlay([{'namespace':'sample_plugin','fields':[],
            'action':{'label':'Testar','run':lambda values:(True,'OK')}}],self.hub)
        self.addCleanup(panel.deleteLater)
        panel._running_actions.add('sample_plugin');panel._action_buttons['sample_plugin'].setEnabled(False)
        with patch('memory.config_manager.save_plugin_config',side_effect=OSError('synthetic')):
            panel._save_all()
        self.assertTrue(panel._status_labels['sample_plugin'].text())
        self.assertIn('sample_plugin',panel._running_actions)
        self.assertFalse(panel._action_buttons['sample_plugin'].isEnabled())
        panel._on_test_done('sample_plugin',True,'Verificado')
        self.assertTrue(panel._action_buttons['sample_plugin'].isEnabled())

    def test_editor_test_button_runs_once_and_displays_result(self):
        import ui
        release=threading.Event();callback=Mock(side_effect=lambda values:(release.wait(2),'Teste concluido'))
        panel=ui.PluginSettingsOverlay([{'namespace':'sample_plugin','fields':[],
            'action':{'label':'Testar','run':callback}}],self.hub)
        self.addCleanup(panel.deleteLater)
        with patch('memory.config_manager.save_plugin_config'):
            panel._action_buttons['sample_plugin'].click()
            self.assertFalse(panel._action_buttons['sample_plugin'].isEnabled())
            panel._action_buttons['sample_plugin'].click();release.set()
            deadline=time.monotonic()+3
            while panel._running_actions and time.monotonic()<deadline:
                self.app.processEvents();time.sleep(.01)
        callback.assert_called_once_with({})
        self.assertEqual(panel._status_labels['sample_plugin'].text(),'Teste concluido')
        self.assertTrue(panel._action_buttons['sample_plugin'].isEnabled())

    def test_native_editor_result_replaces_previous_error(self):
        name='document_reader'
        self.window.get_plugins=lambda:[{'name':name,'valid':True,'enabled':True}]
        self.hub.refresh();self.finish('plugin:'+name,'error')
        with patch('core.resource_policy.local_status',return_value={'available':True}):
            self.hub._plugin_authorization_finished(name,True,'Disponível')
        self.assertEqual(self.hub._connection_checks.get('plugin:'+name)['state'],'connected')
        self.assertNotEqual(self.page.rows['plugin:'+name].status.text(),'Falha no teste')

    def test_disconnected_opens_credentials_not_oauth(self):
        self.gmail_status['connected']=False;self.page._local_at=0;self.hub.refresh()
        with patch.object(self.hub,'connect_gmail') as connect:
            self.page.rows['gmail'].action.click()
            self.assertFalse(self.page.gmail_editor.isHidden());connect.assert_not_called()

    def test_qr_open_is_awaiting_not_connected(self):
        captured=[]
        with patch('core.whatsapp_web.transport.call',return_value={'ok':True,'connected':False}),patch.object(self.hub,'_connection_worker',side_effect=lambda callback,*a,**kw:captured.append(callback())):
            self.hub.connect_whatsapp()
        self.assertEqual(captured[0]['state'],'awaiting');self.assertFalse(captured[0]['ok'])

    def test_ai_requires_fresh_connection_and_timeout_is_failure(self):
        self.window.on_connection_test=Mock()
        self.window._connection_status={'connected':True,'model':'teste','revision':2}
        self.hub.check_ai();self.hub.refresh()
        self.window.on_connection_test.assert_called_once()
        self.window.on_voice_change.assert_not_called()
        self.assertIsNotNone(self.hub._ai_check)
        self.window._connection_status['revision']=3;self.hub.refresh()
        self.assertIsNone(self.hub._ai_check)
        self.assertEqual(self.hub._connection_checks.get('ai')['state'],'connected')
        self.hub.check_ai();self.hub._ai_test_timeout()
        self.assertEqual(self.hub._connection_checks.get('ai')['state'],'error')
        self.assertFalse(self.hub._ai_timeout.isActive())

    def test_plugin_button_captures_name_and_semantic_navigation(self):
        with patch.object(self.hub,'activate_plugin') as activate:
            self.page.rows['plugin:sample_plugin'].action.click()
            activate.assert_called_once_with('sample_plugin')
        for key in ('profile','connections','activity','ai'):
            self.hub.open_page(key)
            self.assertEqual(self.hub.tabs.currentIndex(),self.hub.page_indices[key])
            self.window._settings_hub=self.hub
            with patch.object(self.window,'_toggle_drawer') as drawer:
                self.window._open_settings_tab(key)
                drawer.assert_called_once_with(True)
                self.assertEqual(self.hub.navigation.currentRow(),self.hub.page_indices[key])
        self.assertEqual(self.page.rows['plugin:sample_plugin'].status.text(),'Desativado')

    def test_worker_duplicate_and_late_completion_after_close(self):
        release=threading.Event();done=threading.Event();calls=[]
        def callback():
            calls.append(1);release.wait(2);done.set();return True,'Verificado'
        self.hub._connection_worker(callback,'whatsapp')
        self.hub._connection_worker(callback,'whatsapp')
        self.assertFalse(self.page.rows['whatsapp'].action.isEnabled())
        self.hub.close();release.set();self.assertTrue(done.wait(2))
        deadline=time.monotonic()+2
        while self.hub._connection_checks.get('whatsapp').get('busy') and time.monotonic()<deadline:time.sleep(.01)
        self.app.processEvents();self.assertEqual(calls,[1])
        self.assertNotEqual(self.hub.connection_notice.text(),'Verificado')

    def test_mocked_responsive_rows_and_editor(self):
        import ui
        self.hub.show();self.hub.open_page('connections');self.page.gmail_editor.show()
        for width,height in ((800,600),(1366,768),(1920,1080)):
            self.hub.resize(width,height);self.app.processEvents();self.app.processEvents()
            for row in self.page.rows.values():
                for widget in (row.title,row.status,row.actions):
                    self.assertGreaterEqual(widget.x(),0)
                    self.assertLessEqual(widget.x()+widget.width(),row.width())
            for button in self.hub.connection_buttons:
                if self.page.gmail_editor.isAncestorOf(button):
                    self.assertLessEqual(button.x()+button.width(),button.parentWidget().width())
            self.hub.grab().save(str(ui.BASE_DIR/f'validation/connections-verified-layout-{width}.png'))
        self.page.gmail_editor.hide();self.hub.resize(1366,768)
        self.app.processEvents();self.app.processEvents()
        self.hub.grab().save(str(ui.BASE_DIR/'validation/connections-list-reviewed.png'))

    def test_new_provider_rows_connect_or_test_actual_service(self):
        original=self.window.get_plugins()
        self.window.get_plugins=lambda:original+[
            {'name':name,'valid':True,'enabled':True} for name in ('google_calendar','google_drive','spotify_control','document_reader','personal_routines','structured_browser')]
        with patch('core.google_services.status',return_value={'connected':False,'configured':False}),patch('core.spotify_service.status',return_value={'connected':False,'configured':False}):
            self.hub.refresh()
            self.assertEqual(self.page.rows['plugin:google_drive'].status.text(),'Não conectado')
            with patch.object(self.hub,'open_plugin_settings') as configure:
                self.page.rows['plugin:google_drive'].action.click();configure.assert_called_once_with('google_drive')
        self.page._external_local.clear()
        with patch('core.google_services.status',return_value={'connected':True,'configured':True}),patch('core.spotify_service.status',return_value={'connected':False,'configured':False}):
            self.hub.refresh()
            self.finish('google_drive','connected')
            self.assertEqual(self.page.rows['plugin:google_drive'].action.text(),'Testar conexão')
            with patch.object(self.hub,'_connection_worker') as worker:
                self.page.rows['plugin:google_drive'].action.click()
                self.assertEqual(worker.call_args.args[1],'google_drive')

    def test_service_results_reach_real_panel_and_keep_provider(self):
        import json
        from core.essential_plugins import respond
        player=Mock()
        respond(lambda:{'items':[{'id':'google-real','summary':'Consulta','start':{'dateTime':'2026-10-12T14:00:00-03:00'}}]},player,'calendar','GOOGLE AGENDA','google_calendar')
        model=player.show_manifestation.call_args.args[0]
        self.assertEqual(model['items'][0]['due'],'2026-10-12T14:00:00-03:00')
        self.window._show_manifestation(model)
        reference=self.window.interface_snapshot()['references'][0]
        self.assertEqual(reference['tool'],'google_calendar');self.assertEqual(reference['id'],'google-real')
        from plugins import spotify_control
        with patch('core.spotify_service.run',return_value={'tracks':[{'id':'track-real','title':'Música','artists':['Artista']}] }):
            spotify_control.run({'action':'search','query':'Música'},player)
        self.window._show_manifestation(player.show_manifestation.call_args.args[0])
        self.assertEqual(self.window.interface_snapshot()['references'][0]['tool'],'spotify_control')


if __name__=='__main__':unittest.main()
