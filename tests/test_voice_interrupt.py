import asyncio
import os
import tempfile
import threading
import unittest
import wave
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock,AsyncMock,patch
import numpy as np
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from core.voice_interrupt import VoiceInterruptGate
from core.echo import EchoGuard,band_energies
from core.application_context import ApplicationContext
import main


class GateTests(unittest.TestCase):
    def test_cancelled_mouth_schedule_cannot_keep_animating(self):
        from ui import HudCanvas
        hud=NS(_visemes=([(.8,.6,.3)],0.,.02),_vis_i=0,_live_amp=.8,_amp_disp=.8)
        HudCanvas.cancel_audio_animation(hud)
        self.assertIsNone(hud._visemes);self.assertIsNone(hud._vis_i)
        self.assertEqual(hud._live_amp,0.);self.assertEqual(hud._amp_disp,0.)

    def setUp(self):
        self.vad=Mock();self.vad.is_speech.return_value=True
        self.gate=VoiceInterruptGate(self.vad)
        self.pcm=np.full((1024,1),500,dtype=np.int16)

    def test_short_click_and_low_volume_never_cancel(self):
        self.assertIsNone(self.gate.feed(self.pcm,16000,.8,True))
        self.assertIsNone(self.gate.feed(self.pcm,16000,0.,True))
        for _ in range(30):self.assertIsNone(self.gate.feed(self.pcm,16000,.02,True))

    def test_volume_without_voice_or_echo_separation_is_not_enough(self):
        self.vad.is_speech.return_value=False
        for _ in range(30):self.assertIsNone(self.gate.feed(self.pcm,16000,1.,True))
        self.vad.is_speech.return_value=True
        for _ in range(30):self.assertIsNone(self.gate.feed(self.pcm,16000,1.,False))

    def test_confirmed_speech_preserves_onset_and_only_triggers_once(self):
        for _ in range(4):self.assertIsNone(self.gate.feed(self.pcm,16000,.3,True))
        chunks=self.gate.feed(self.pcm,16000,.3,True)
        self.assertEqual(len(chunks),5);self.assertEqual(chunks[0],self.pcm.tobytes())
        self.assertIsNone(self.gate.feed(self.pcm,16000,.3,True))
        self.gate.reset()
        self.assertIsNone(self.gate.feed(self.pcm,16000,.3,True))

    def test_noisy_room_demands_longer_evidence(self):
        for _ in range(11):self.assertIsNone(self.gate.feed(self.pcm,16000,.3,True,12))
        self.assertIsNotNone(self.gate.feed(self.pcm,16000,.3,True,12))

    def test_ambient_floor_adapts_without_unbounded_growth(self):
        self.vad.is_speech.return_value=False
        for _ in range(100):self.gate.observe_ambient(self.pcm,.1)
        self.assertGreater(self.gate.threshold,.07);self.assertLessEqual(self.gate.threshold,.20)

    def test_classifier_error_fails_closed(self):
        self.vad.is_speech.side_effect=RuntimeError('Teste')
        self.assertIsNone(self.gate.feed(self.pcm,16000,.9,True))

    def test_actual_vad_rejects_silence(self):
        gate=VoiceInterruptGate()
        self.assertTrue(gate.available)
        for _ in range(20):self.assertIsNone(gate.feed(np.zeros(1024,dtype=np.int16),16000,1.,True))

    def test_actual_vad_with_locally_synthesized_speech(self):
        import win32com.client
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'speech.wav'
            stream=win32com.client.Dispatch('SAPI.SpFileStream')
            stream.Format.Type=18
            stream.Open(str(path),3)
            try:
                voice=win32com.client.Dispatch('SAPI.SpVoice');voice.AudioOutputStream=stream
                voice.Speak('Jarvis, e outra coisa. Eu quero corrigir o pedido anterior.')
            finally:stream.Close()
            with wave.open(str(path),'rb') as audio:
                self.assertEqual(audio.getframerate(),16000);self.assertEqual(audio.getnchannels(),1)
                samples=np.frombuffer(audio.readframes(audio.getnframes()),dtype=np.int16)
            gate=VoiceInterruptGate();accepted=None
            for offset in range(0,len(samples),1024):
                block=samples[offset:offset+1024]
                accepted=gate.feed(block,16000,main._pcm_level(block),True)
                if accepted:break
            self.assertIsNotNone(accepted)

    def test_microphone_column_vector_has_same_echo_signature(self):
        signal=(np.sin(np.arange(1024)*.31)*1500).astype(np.int16)
        np.testing.assert_allclose(band_energies(signal,16000),band_energies(signal[:,None],16000))
        guard=EchoGuard();guard.note_output(signal,16000,.5,when=1.)
        for _ in range(20):self.assertFalse(guard.is_user_speech(signal[:,None],16000,.5,when=1.1))


def assistant_fixture():
    assistant=main.JarvisLive.__new__(main.JarvisLive)
    assistant.ui=Mock();assistant.ui.muted=False
    assistant._manual_rest=False;assistant._phone_active=False;assistant._ptt_enabled=False;assistant._ptt_held=False
    assistant._is_speaking=True;assistant._speaking_lock=threading.Lock()
    assistant._interrupted=False;assistant._response_epoch=0;assistant._barge_pending=False
    assistant._server_turn_open=True
    assistant._cancelled_tool_ids=set();assistant._resume_handle=None
    assistant._out_latency=.1;assistant._tail_until=0.;assistant._out_level=.2;assistant._play_cursor=0.
    assistant._voice_interrupt=VoiceInterruptGate(Mock());assistant._echo=EchoGuard();assistant._visemes=Mock()
    assistant._cancel_context_refresh=Mock();assistant._queue_daily_briefing=Mock()
    assistant._turn_done_event=asyncio.Event();assistant.audio_in_queue=asyncio.Queue();assistant.out_queue=asyncio.Queue(maxsize=8)
    assistant._application_context=ApplicationContext();assistant._session_log=[];assistant._last_out_logged='';assistant._asst_name='DIEF JARVIS'
    assistant._dashboard=None;assistant._vision_close_pending=False
    return assistant


def content(**updates):
    return NS(**dict({'interrupted':False,'turn_complete':False,'input_transcription':None,'output_transcription':None},**updates))


def response(**updates):
    return NS(**dict({'data':None,'server_content':None,'tool_call':None,'tool_call_cancellation':None},**updates))


def session_for(responses):
    async def stream():
        for item in responses:yield item
        raise asyncio.CancelledError()
    session=Mock();session.receive=stream;session.send_tool_response=AsyncMock()
    return session


class InterruptionIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_keyword_stop_discards_prior_greeting_without_losing_next_request(self):
        assistant=assistant_fixture()
        async def stream():
            yield response(server_content=content(input_transcription=NS(text='Bom dia Jarvis')))
            assistant._drop_prior_input=True
            assistant.interrupt()
            yield response(server_content=content(interrupted=True,turn_complete=True))
            yield response(data=b'new',server_content=content(input_transcription=NS(text='Quero o clima'),output_transcription=NS(text='Aqui esta o clima'),turn_complete=True))
            raise asyncio.CancelledError()
        assistant.session=Mock();assistant.session.receive=stream
        with self.assertRaises(asyncio.CancelledError):await assistant._receive_audio()
        self.assertIn('User: Quero o clima',assistant._session_log)
        self.assertFalse(any('Bom dia' in entry for entry in assistant._session_log))

    async def test_any_confirmed_speech_wakes_rest_without_keyword(self):
        assistant=assistant_fixture();assistant._manual_rest=True;assistant._is_speaking=False
        def resume(*args):
            assistant._manual_rest=False
            return {'ok':True}
        assistant.ui.control_interface.side_effect=resume
        assistant._wake_from_speech([b'quero',b'outro assunto'])
        assistant.ui.control_interface.assert_called_once_with('rest','off','')
        self.assertFalse(assistant._manual_rest)
        self.assertEqual(assistant.out_queue.get_nowait()['data'],b'quero')

    async def test_rest_noise_does_not_schedule_wake(self):
        assistant=assistant_fixture();assistant._manual_rest=True
        loop=Mock()
        for _ in range(20):assistant._consider_rest_wake(np.zeros((1024,1),dtype=np.int16),loop)
        loop.call_soon_threadsafe.assert_not_called()

    async def test_saved_legacy_modes_do_not_require_keyword_or_key(self):
        from memory.config_manager import get_wake_word_enabled,get_push_to_talk_enabled
        with patch('memory.config_manager.load_api_keys',return_value={'wake_word_enabled':True,'push_to_talk_enabled':True}):
            self.assertFalse(get_wake_word_enabled());self.assertFalse(get_push_to_talk_enabled())
    async def test_interrupt_after_generation_finished_does_not_drop_next_answer(self):
        assistant=assistant_fixture();assistant._server_turn_open=False
        assistant.audio_in_queue.put_nowait(b'old')
        assistant.interrupt()
        self.assertFalse(assistant._interrupted)
        assistant.session=session_for([response(data=b'new',server_content=content(output_transcription=NS(text='Nova resposta'),turn_complete=True))])
        with patch('core.fish_audio.enabled',return_value=False),patch('memory.config_manager.load_api_keys',return_value={'speech_provider':'gemini'}):
            with self.assertRaises(asyncio.CancelledError):await assistant._receive_audio()
        self.assertEqual(assistant.audio_in_queue.get_nowait(),b'new')
        self.assertFalse(assistant._server_turn_open)
    async def test_acceptance_drains_old_audio_replays_prefix_and_cancels_cues(self):
        assistant=assistant_fixture();assistant.audio_in_queue.put_nowait(b'old')
        assistant.out_queue.put_nowait({'data':b'stale'})
        assistant._accept_voice_interruption([b'Jarvis',b'outra coisa'])
        self.assertTrue(assistant.audio_in_queue.empty());self.assertTrue(assistant._interrupted)
        self.assertEqual(assistant.out_queue.get_nowait()['data'],b'Jarvis')
        self.assertEqual(assistant.out_queue.get_nowait()['data'],b'outra coisa')
        assistant.ui.cancel_presentation_speech.assert_called_once()
        assistant._visemes.reset.assert_called_once();self.assertEqual(assistant._tail_until,0.)

    async def test_mute_rest_ptt_and_phone_do_not_allow_voice_interruption(self):
        for flag in ('muted','rest','phone','ptt'):
            assistant=assistant_fixture()
            if flag=='muted':assistant.ui.muted=True
            if flag=='rest':assistant._manual_rest=True
            if flag=='phone':assistant._phone_active=True
            if flag=='ptt':assistant._ptt_enabled=True
            assistant._accept_voice_interruption([b'speech'])
            self.assertFalse(assistant._interrupted);self.assertTrue(assistant.out_queue.empty())

    async def test_input_queue_is_bounded_without_callback_exception(self):
        assistant=assistant_fixture()
        for index in range(100):assistant._queue_microphone_audio(bytes([index]))
        self.assertEqual(assistant.out_queue.qsize(),8)
        self.assertEqual(assistant.out_queue.get_nowait()['data'],bytes([92]))

    async def test_server_ack_preserves_correction_and_rejects_old_subtitles(self):
        assistant=assistant_fixture()
        assistant.session=session_for([
            response(data=b'old',server_content=content(interrupted=True,output_transcription=NS(text='Resposta antiga errada'),input_transcription=NS(text='Jarvis, e outra coisa'))),
            response(server_content=content(turn_complete=True)),
            response(data=b'new',server_content=content(output_transcription=NS(text='Nova resposta corrigida'),turn_complete=True)),
        ])
        with patch('core.fish_audio.enabled',return_value=False),patch('memory.config_manager.load_api_keys',return_value={'speech_provider':'gemini'}):
            with self.assertRaises(asyncio.CancelledError):await assistant._receive_audio()
        self.assertEqual(assistant.audio_in_queue.get_nowait(),b'new')
        assistant.ui.narration_text.assert_called_once()
        self.assertEqual(assistant.ui.narration_text.call_args.args[0],'Nova resposta corrigida')
        self.assertIn('User: Jarvis, e outra coisa',assistant._session_log)
        self.assertFalse(assistant._interrupted)

    async def test_cancelled_tool_id_is_not_executed(self):
        assistant=assistant_fixture();assistant._cancelled_tool_ids.add('cancelled')
        assistant._execute_tool_body=AsyncMock()
        result=await assistant._execute_tool(NS(id='cancelled',name='send',args={}))
        self.assertTrue(result.response['result']['cancelled']);assistant._execute_tool_body.assert_not_awaited()

    async def test_interruption_does_not_start_dependent_steps(self):
        assistant=assistant_fixture();assistant._flush_pending_vision=AsyncMock()
        async def execute(call):
            assistant.interrupt()
            return main.types.FunctionResponse(id=call.id,name=call.name,response={'result':{'ok':True}})
        assistant._execute_tool=AsyncMock(side_effect=execute)
        assistant.session=session_for([response(tool_call=NS(function_calls=[NS(id='1',name='first'),NS(id='2',name='second')]))])
        with self.assertRaises(asyncio.CancelledError):await assistant._receive_audio()
        self.assertEqual(assistant._execute_tool.await_count,1)
        sent=assistant.session.send_tool_response.call_args.kwargs['function_responses']
        self.assertTrue(sent[1].response['result']['cancelled'])

    async def test_late_device_write_does_not_advance_cancelled_presentation(self):
        assistant=assistant_fixture();assistant.set_speaking=Mock()
        assistant._turn_done_event.set();assistant._fish_voice=None
        assistant.audio_in_queue.get=AsyncMock(side_effect=[b'\0'*2400,asyncio.CancelledError()])
        stream=Mock();stream.latency=.1
        def write(data):
            assistant._response_epoch+=1
            return False
        stream.write.side_effect=write
        async def thread(function,*args):
            return function(*args)
        with patch.object(main.sd,'RawOutputStream',return_value=stream),patch.object(main,'get_output_device',return_value=''),patch.object(main.audio_devices,'resolve',return_value=None),patch.object(main.asyncio,'to_thread',side_effect=thread):
            with self.assertRaises(asyncio.CancelledError):await assistant._play_audio()
        assistant.ui.presentation_audio.assert_not_called()
        # Abort the stale write, restart for fresh audio, then abort on teardown.
        self.assertEqual(stream.abort.call_count,2)
        self.assertEqual(stream.start.call_count,2)
        operations=[call[0] for call in stream.method_calls]
        self.assertEqual(operations.count('write'),1)
        self.assertLess(operations.index('abort'),operations.index('stop'))
        stream.close.assert_called_once()
