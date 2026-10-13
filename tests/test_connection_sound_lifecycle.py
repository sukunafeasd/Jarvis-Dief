import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import struct
import threading
import time
import unittest
from unittest.mock import Mock, patch
from PyQt6.QtWidgets import QApplication
from core.connection_states import ConnectionChecks
from core.connection_verifier import ConnectionVerifier, saved_checks
from core.ui_sounds import SoundDirector, cue_pcm


class VerificationTests(unittest.TestCase):
    def wait(self, verifier, provider):
        deadline=time.monotonic()+2
        while verifier.checks.get(provider).get('busy') and time.monotonic()<deadline:
            time.sleep(.01)
        self.assertFalse(verifier.checks.get(provider).get('busy'))

    def test_fresh_process_verifies_and_reuses_session_result(self):
        verifier=ConnectionVerifier();callback=Mock(return_value=(True,'Confirmado'))
        self.assertTrue(verifier.submit('google_drive',callback))
        self.wait(verifier,'google_drive')
        self.assertEqual(verifier.checks.get('google_drive')['state'],'connected')
        self.assertFalse(verifier.submit('google_drive',callback))
        self.assertEqual(callback.call_count,1)
        other=ConnectionVerifier()
        self.assertTrue(other.submit('google_drive',callback));self.wait(other,'google_drive')
        self.assertEqual(callback.call_count,2)

    def test_old_result_rechecked_and_failure_not_hidden(self):
        now=[0];checks=ConnectionChecks(lambda:now[0]);verifier=ConnectionVerifier(checks)
        callback=Mock(return_value=(True,'Confirmado'))
        verifier.submit('google_drive',callback);self.wait(verifier,'google_drive')
        now[0]=301;callback.return_value=(False,'Autorize novamente')
        self.assertTrue(verifier.submit('google_drive',callback));self.wait(verifier,'google_drive')
        self.assertEqual(checks.get('google_drive')['state'],'auth_required')

    def test_stale_completion_cannot_overwrite_timeout_or_new_test(self):
        checks=ConnectionChecks();generation=checks.begin('gmail')
        checks.finish('gmail',generation,'error','Timeout')
        self.assertFalse(checks.finish('gmail',generation,'connected','Tarde'))
        new=checks.begin('gmail')
        self.assertFalse(checks.finish('gmail',generation,'connected','Antigo'))
        self.assertTrue(checks.finish('gmail',new,'connected','Novo'))

    def test_duplicate_worker_does_not_repeat_network_request(self):
        gate=threading.Event();verifier=ConnectionVerifier()
        callback=Mock(side_effect=lambda:(gate.wait(2),'Confirmado'))
        verifier.submit('gmail',callback)
        self.assertFalse(verifier.submit('gmail',callback));gate.set();self.wait(verifier,'gmail')
        self.assertEqual(callback.call_count,1)

    def test_saved_inventory_skips_disabled_and_unconfigured_never_connects(self):
        plugins=[{'name':'google_drive','valid':True,'enabled':True},
                 {'name':'spotify_control','valid':True,'enabled':False},
                 {'name':'home_automation','valid':True,'enabled':True}]
        with patch('core.gmail_connection.status',return_value={'connected':False}), patch('core.whatsapp_web.PROFILE') as profile, patch('core.resource_policy.external_status',side_effect=lambda n:{'connected':n=='google_drive'}), patch('core.google_services.verify',return_value=(True,'OK')) as verify, patch('core.google_services.connect') as connect:
            profile.exists.return_value=False
            callbacks=list(saved_checks(plugins))
            self.assertEqual([name for name,_ in callbacks],['google_drive'])
            callbacks[0][1]();verify.assert_called_once_with('google_drive');connect.assert_not_called()


class SoundLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])

    def director(self):
        value=SoundDirector(None);value.enabled=True
        self.addCleanup(lambda:value.ambient_timer.stop())
        for name in ('click','refresh-complete','ambient','music-start','music-pause'):
            effect=Mock();effect.isPlaying.return_value=False;value.effects[name]=effect
        return value

    def test_space_silences_for_speech_music_and_hidden_window(self):
        value=self.director();ambient=value.effects['ambient']
        value.scene(visible=True);ambient.play.assert_called()
        value.voice(True);ambient.stop.assert_called()
        value.voice(False);value.media({'is_playing':True});ambient.reset_mock()
        value.scene(visible=True);ambient.stop.assert_called();ambient.play.assert_not_called()
        value.media({'is_playing':False});ambient.play.assert_called()
        value.stop();ambient.reset_mock();value._ambience();ambient.play.assert_not_called()

    def test_rest_is_quieter_and_click_does_not_cut_completion(self):
        value=self.director();value.scene(visible=True,resting=True)
        value.effects['ambient'].setVolume.assert_called_with(.025)
        value.play('refresh-complete');value.effects['refresh-complete'].isPlaying.return_value=True
        value.last_any=0
        self.assertFalse(value.play('click'))
        value.effects['refresh-complete'].stop.assert_not_called()

    def test_cues_audible_without_pcm_clipping(self):
        data=cue_pcm('projection');samples=struct.unpack('<'+'h'*(len(data)//2),data)
        self.assertGreater(max(map(abs,samples)),10000)
        self.assertLess(max(map(abs,samples)),32767)
