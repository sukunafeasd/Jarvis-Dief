"""Layout and behavior checks with isolated profiles and synthetic connections."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import tempfile
from pathlib import Path
from unittest.mock import patch, Mock
import unittest
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QPushButton, QLineEdit, QComboBox, QSpinBox
import test_settings_connections

OUTPUT=Path(tempfile.mkdtemp(prefix='dief-observatory-'))


class ObservatorySettingsTests(unittest.TestCase):
    setUpClass=classmethod(test_settings_connections.ConnectionsTests.setUpClass.__func__)
    def setUp(self):
        verify=patch('ui.MainWindow._verify_saved_connections');verify.start();self.addCleanup(verify.stop)
        test_settings_connections.ConnectionsTests.setUp(self)
    cleanup_widgets=test_settings_connections.ConnectionsTests.cleanup_widgets

    def test_responsive_connections_and_search_keep_actions_accessible(self):
        self.window.get_plugins=lambda:[{'name':key,'valid':True,'enabled':True} for key in
            ('spotify_control','google_calendar','notion_service','context7','deep_research','gmail_control','whatsapp_web')]
        with patch('core.settings_connections.external_status',return_value={'connected':False}),patch('core.settings_connections.local_status',return_value={'available':True}):
            self.hub.refresh()
        self.hub.show();self.hub.open_page('connections')
        for width,height in ((1366,900),(1920,1080),(800,600)):
            self.hub.resize(width,height);QTest.qWait(250)
            self.assertEqual(self.page.account_scroll.horizontalScrollBar().maximum(),0)
            for row in self.page.rows.values():
                if not row.isVisible():continue
                for control in (row.title,row.detail,row.status,row.action,row.configure):
                    if control is None or not control.isVisible():continue
                    self.assertTrue(row.rect().contains(control.mapTo(row,control.rect().bottomRight())),(width,row.identifier,control.geometry()))
                self.assertFalse(row.title.geometry().intersects(row.detail.geometry()),row.identifier)
            self.assertTrue(self.hub.grab().save(str(OUTPUT/f'connections-{width}.png')))
        self.page.search.setText('Codex');QTest.qWait(60)
        self.assertTrue(self.page.forge_connection.isVisible());self.assertTrue(self.page.rows['gmail'].isHidden())
        self.page.search.setText('spotify');QTest.qWait(60)
        self.assertTrue(self.page.forge_connection.isHidden());self.assertTrue(self.page.rows['plugin:spotify_control'].isVisible())
        self.page.search.clear();self.page.categories.setCurrentIndex(2);QTest.qWait(80)
        self.assertTrue(self.hub.grab().save(str(OUTPUT/'skills-800.png')))

    def test_profile_screens_and_actions_keep_form_values(self):
        self.hub.name.setText('chefe');self.hub.city.setText('Porto Alegre, RS')
        self.hub.interests.setPlainText('Tecnologia, ciência, notícias do Brasil')
        self.hub.show()
        for width,height in ((1366,900),(1920,1080),(800,600)):
            self.hub.resize(width,height)
            for key in ('profile','appearance','ai','chat','activity'):
                self.hub.open_page(key);QTest.qWait(120)
                page=self.hub.tabs.currentWidget()
                if hasattr(page,'horizontalScrollBar'):self.assertEqual(page.horizontalScrollBar().maximum(),0,(width,key))
                self.assertTrue(self.hub.grab().save(str(OUTPUT/f'{key}-{width}.png')))
        self.hub.open_page('profile');self.assertEqual(self.hub.city.text(),'Porto Alegre, RS')
        self.hub.panel_sounds_muted.setChecked(True);self.assertTrue(self.hub.panel_sounds_muted.isChecked())
        self.hub.close();self.assertFalse(self.hub.timer.isActive())
        self.assertNotEqual(self.hub.core_preview._light.state(),self.hub.core_preview._light.State.Running)

    def test_forge_restores_account_and_model_and_respects_edits(self):
        forge=self.page.forge_connection
        state={'authenticated':True,'transport':'ready','account':{'type':'apiKey'},'model':'example-model',
               'models':[{'id':'example-model'},{'id':'other-model'}]}
        forge._done(state)
        self.assertEqual(forge.auth.currentData(),'apiKey');self.assertEqual(forge.model.currentData(),'example-model')
        runtime=Mock()
        with patch.object(forge,'runtime',return_value=runtime),patch.object(forge,'_start',side_effect=lambda cb:cb()):
            forge.authorize()
        runtime.connect.assert_called_once_with(auth_mode=None,key='',model='example-model')
        forge.auth.setCurrentIndex(0);forge.auth.activated.emit(0)
        forge.model.setCurrentIndex(2);forge.model.activated.emit(2)
        forge._done(state)
        self.assertEqual(forge.auth.currentData(),'chatgpt');self.assertEqual(forge.model.currentData(),'other-model')

    def test_preview_pauses_health_checks_and_resumes_with_fresh_timeout(self):
        preview=self.hub.core_preview
        fake=Mock();fake.failed=False;fake._payload={};fake._health.isActive.return_value=False
        preview.view=fake
        with patch.object(preview,'isVisible',return_value=True),patch.object(self.hub,'isMinimized',return_value=False):
            preview.sync_preview();fake._health.start.assert_called_once_with(1000)
            self.assertTrue(fake.sync.call_args[0][0]['visible'])
        with patch.object(preview,'isVisible',return_value=False):
            preview.sync_preview();fake._health.stop.assert_called_once()
            self.assertFalse(fake.sync.call_args[0][0]['visible'])
        preview.view=None

    def test_switch_thumb_follows_a_silent_rollback(self):
        toggle=self.hub.panel_sounds_muted
        toggle.setChecked(True)
        toggle.blockSignals(True)
        toggle.setChecked(False)
        toggle.blockSignals(False)
        self.assertFalse(toggle.isChecked())
        self.assertEqual(toggle.position,0)
        self.assertNotEqual(toggle.animation.state(),toggle.animation.State.Running)


if __name__=='__main__':
    print('Capturas:',OUTPUT,flush=True);unittest.main()
