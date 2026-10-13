import asyncio
import json
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import Mock
import numpy as np
from core.stop_keyword import is_stop_command, MODEL_DIR


class StopKeywordTests(unittest.TestCase):
    def test_only_explicit_stop_phrase_matches(self):
        for phrase in ['para', 'Para!', 'Jarvis, para.', 'para por favor', 'para Jarvis']:
            self.assertTrue(is_stop_command(phrase), phrase)
        for phrase in ['', 'barulho', 'Jarvis outra coisa', 'prepara', 'para amanha',
                       'uma tarefa para hoje', 'para mim isso esta errado']:
            self.assertFalse(is_stop_command(phrase), phrase)

    def test_unavailable_listener_does_not_queue_or_cancel(self):
        from core.stop_keyword import StopKeywordListener
        callback = Mock()
        listener = StopKeywordListener(callback, Mock())
        listener.feed(bytes(2048))
        self.assertTrue(listener.pending.empty())
        callback.assert_not_called()

    def test_speech_activity_is_not_itself_an_interruption(self):
        from main import JarvisLive
        assistant = JarvisLive.__new__(JarvisLive)
        assistant._stop_keyword = Mock()
        assistant._echo = Mock()
        assistant._echo.is_user_speech.return_value = True
        assistant.interrupt = Mock()
        loop = Mock()
        assistant._consider_voice_interruption(np.full((1024, 1), 9000, dtype=np.int16), loop)
        assistant._stop_keyword.feed.assert_called_once()
        assistant.interrupt.assert_not_called()
        loop.call_soon_threadsafe.assert_not_called()

    def test_old_or_muted_keyword_does_not_interrupt(self):
        from main import JarvisLive
        assistant = JarvisLive.__new__(JarvisLive)
        assistant._stop_keyword = Mock(generation=4)
        assistant._is_speaking = True
        assistant._manual_rest = False
        assistant._phone_active = False
        assistant.ui = Mock(muted=False)
        assistant.interrupt = Mock()
        assistant._cancel_context_refresh = Mock()
        assistant._stop_from_keyword(3)
        assistant.interrupt.assert_not_called()
        assistant.ui.muted = True
        assistant._stop_from_keyword(4)
        assistant.interrupt.assert_not_called()
        assistant.ui.muted = False
        assistant._stop_from_keyword(4)
        assistant.interrupt.assert_called_once()
        assistant._cancel_context_refresh.assert_called_once()
        self.assertTrue(assistant._drop_prior_input)

    @unittest.skipUnless((MODEL_DIR / 'final.mdl').exists(), 'Modelo local ainda nao preparado')
    def test_real_portuguese_recognizer_with_synthesized_voice_and_silence(self):
        import win32com.client
        from vosk import Model, KaldiRecognizer, SetLogLevel
        SetLogLevel(-1)
        model = Model(str(MODEL_DIR))
        voice = win32com.client.Dispatch('SAPI.SpVoice')
        portuguese = next((v for v in voice.GetVoices() if v.GetAttribute('Language') == '416'), None)
        if portuguese is None:
            self.skipTest('Voz pt-BR nao instalada')
        voice.Voice = portuguese
        with tempfile.TemporaryDirectory() as folder:
            for phrase, expected in [('para', True), ('quero saber as noticias', False), ('uma tarefa para amanha', False)]:
                path = Path(folder) / 'voice.wav'
                stream = win32com.client.Dispatch('SAPI.SpFileStream')
                stream.Format.Type = 18
                stream.Open(str(path), 3)
                try:
                    voice.AudioOutputStream = stream
                    voice.Speak(phrase)
                finally:
                    stream.Close()
                with wave.open(str(path), 'rb') as audio:
                    pcm = audio.readframes(audio.getnframes())
                recognizer = KaldiRecognizer(model, 16000)
                recognizer.SetWords(True)
                recognizer.AcceptWaveform(pcm + bytes(32000))
                result = json.loads(recognizer.FinalResult())
                self.assertEqual(is_stop_command(result.get('text', '')), expected, result)
            recognizer = KaldiRecognizer(model, 16000)
            recognizer.AcceptWaveform(bytes(64000))
            self.assertFalse(is_stop_command(json.loads(recognizer.FinalResult()).get('text', '')))
