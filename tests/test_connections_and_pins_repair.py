import json
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock,patch
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage,QColor
from PyQt6.QtWidgets import QApplication,QPushButton
import ui
from core import spotify_service as spotify
from core.pinned_scene_store import PinnedSceneStore


class SpotifyRepairTests(unittest.TestCase):
    def test_google_api_failure_keeps_previous_active_authorization(self):
        from core import google_services as google
        from googleapiclient.errors import HttpError
        credentials=Mock();credentials.to_json.return_value=json.dumps({'token':'fixture-token'})
        flow=Mock();flow.run_local_server.return_value=credentials
        identity=Mock();identity.userinfo.return_value.get.return_value.execute.return_value={'email':'fixture@example.com'}
        error=HttpError(Mock(status=403,reason='Forbidden'),json.dumps({'error':{'details':[{'reason':'SERVICE_DISABLED'}]}}).encode())
        with patch.object(google,'credential_path',return_value=Path(__file__)),patch.object(google,'client_configuration',return_value={}),patch('google_auth_oauthlib.flow.InstalledAppFlow.from_client_config',return_value=flow),patch.object(google,'settings',return_value={'expected_email':'fixture@example.com'}),patch.object(google,'build',side_effect=[identity,Mock()]),patch.object(google,'check_api',side_effect=error),patch.object(google.tokens,'write') as write,patch.object(google.tokens,'remove') as remove:
            with self.assertRaises(google.GoogleConnectionProblem):google.connect('google_drive')
            self.assertEqual(write.call_count,1)
            self.assertEqual(write.call_args.args[0],'google_drive_pending')
            remove.assert_not_called()

    def test_settings_authorization_result_replaces_old_warning(self):
        from core.settings_hub import SettingsHub
        from core.connection_states import ConnectionChecks
        hub=Mock();hub._connection_checks=ConnectionChecks()
        generation=hub._connection_checks.begin('google_drive')
        hub._connection_checks.finish('google_drive',generation,'auth_required','Old warning')
        with patch('core.resource_policy.external_status',return_value={'connected':True}):
            SettingsHub._plugin_authorization_finished(hub,'google_drive',True,'Verified')
        self.assertEqual(hub._connection_checks.get('google_drive')['state'],'connected')
        self.assertEqual(hub._connection_checks.get('google_drive')['message'],'Verified')
        hub.connections_page._external_local.pop.assert_called_once_with('google_drive',None)

    def test_google_disabled_api_is_not_a_missing_human_confirmation(self):
        from core.google_services import error_details
        error=Mock(resp=Mock(status=403),content=json.dumps({'error':{'details':[{'reason':'SERVICE_DISABLED'}]}}).encode())
        result=error_details(error)
        self.assertEqual(result['state'],'error');self.assertIn('API',result['message'])

    def test_missing_device_launches_player_and_verifies_once(self):
        api=Mock();uri='spotify:track:'+'a'*22
        api.devices.side_effect=[{'devices':[]},{'devices':[{'id':'real-device','is_active':True}]}]
        api.current_playback.return_value={'is_playing':True,'item':{'uri':uri}}
        with patch.object(spotify,'service',return_value=api),patch.object(spotify,'open_player') as opened,patch.object(spotify.time,'sleep'):
            result=spotify.run({'action':'play','uri':uri})
        self.assertTrue(result['verified']);opened.assert_called_once()
        api.start_playback.assert_called_once_with(device_id='real-device',uris=[uri])

    def test_query_uses_actual_search_uri_and_wrong_track_is_not_success(self):
        api=Mock();uri='spotify:track:'+'a'*22
        api.search.return_value={'tracks':{'items':[{'uri':uri}]}}
        api.devices.return_value={'devices':[{'id':'device'}]}
        api.current_playback.return_value={'is_playing':True,'item':{'uri':'spotify:track:'+'b'*22}}
        with patch.object(spotify,'service',return_value=api),patch.object(spotify.time,'sleep'):
            result=spotify.run({'action':'play','query':'Musica de teste'})
        self.assertFalse(result['verified']);self.assertTrue(result['uncertain'])
        api.start_playback.assert_called_once_with(device_id='device',uris=[uri])

    def test_ambiguous_devices_do_not_play_on_arbitrary_phone(self):
        api=Mock();api.devices.return_value={'devices':[{'id':'a'},{'id':'b'}]}
        with patch.object(spotify,'service',return_value=api):
            with self.assertRaisesRegex(ValueError,'mais de um'):spotify.run({'action':'play'})
        api.start_playback.assert_not_called()

    def test_access_error_does_not_claim_auth_popup_will_fix_premium(self):
        error=Mock(http_status=403,reason='PREMIUM_REQUIRED')
        result=spotify.error_details(error)
        self.assertEqual(result['state'],'error');self.assertIn('Premium',result['message'])
        self.assertEqual(spotify.error_details(Mock(http_status=401,reason='expired'))['state'],'auth_required')


class PinAndConfirmationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])

    def window(self):
        window=ui.MainWindow(str(ui.BASE_DIR/'core/face_model.obj'))
        window.show();self.app.processEvents();window._overlay.hide()
        return window

    def cleanup(self,window):
        window.close();window.deleteLater();self.app.processEvents()

    def test_weather_position_survives_reopen_and_unpin_is_persistent(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(ui,'API_FILE',Path(folder)/'config.json'):
            first=self.window()
            first._pin_data({'kind':'weather','title':'CLIMA','city':'Cidade de teste','temperature':19,'condition':'Chuva'})
            first._pin_previews['weather']['slot']=3;first._save_pins()
            self.cleanup(first)
            second=self.window();second._restore_saved_pins()
            self.assertIn('weather',second._pin_previews)
            preview=second._pin_previews['weather']
            self.assertEqual(preview['slot'],3);self.assertEqual(preview['data']['temperature'],19)
            self.assertTrue(preview['data']['restored_snapshot'])
            second._remove_pin('weather');self.cleanup(second)
            self.assertEqual(PinnedSceneStore(folder).load(),[])

    def test_photo_survives_original_removal_and_has_no_close_button(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(ui,'API_FILE',Path(folder)/'config.json'):
            path=Path(folder)/'original.png';image=QImage(30,30,QImage.Format.Format_RGB32);image.fill(QColor('#44aabb'));image.save(str(path))
            first=self.window();first._terminal_attach(str(path));identifier=next(iter(first._attachments));first._pin_image(identifier)
            path.unlink();self.cleanup(first)
            second=self.window();second._restore_saved_pins()
            preview=second._pin_previews['photo:'+identifier]
            self.assertFalse(preview['pixmap'].isNull());self.assertEqual(preview['widget'].findChildren(QPushButton),[])
            self.cleanup(second)

    def test_confirmation_is_a_modal_window_above_fullscreen_settings(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(ui,'API_FILE',Path(folder)/'config.json'):
            window=self.window();window._show_confirm_banner('Confirmacao de teste','Nada real sera executado.')
            banner=window._confirm_overlay
            self.assertTrue(banner.isWindow());self.assertTrue(banner.isVisible())
            self.assertEqual(banner.windowModality(),Qt.WindowModality.ApplicationModal)
            window._hide_confirm_banner();self.cleanup(window)

    def test_pin_cache_is_encrypted_and_rejects_asset_path_escape(self):
        with tempfile.TemporaryDirectory() as folder:
            store=PinnedSceneStore(folder)
            store.save([{'key':'tasks','data':{'kind':'tasks','items':[{'title':'PRIVATE FIXTURE'}]}}])
            self.assertNotIn(b'PRIVATE FIXTURE',store.path.read_bytes())
            with self.assertRaises(ValueError):store.save([{'key':'photo:x','asset':'../escape.png','data':{'kind':'photo','attachment_id':'x'}}])
