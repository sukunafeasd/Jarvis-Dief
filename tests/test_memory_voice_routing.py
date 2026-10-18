"""Actual Live receiver -> local recall -> visual events, with no provider calls."""
import asyncio
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock,AsyncMock,patch
from core import fish_audio
from tests.test_voice_interrupt import assistant_fixture,content,response


class MemoryVoiceRoutingTests(unittest.IsolatedAsyncioTestCase):
    async def run_request(self,phrase,result):
        owner=assistant_fixture();owner._is_speaking=False;owner._forge_mode=False
        owner._remember_user_turn=AsyncMock();owner._remember_assistant_turn=AsyncMock()
        owner._protocol_voice_context=Mock(return_value=('offline-session',))
        owner._protocol_voice_valid=Mock(return_value=True)
        voice=Mock();voice.pending=False;voice.close=AsyncMock()
        split=phrase.index(' ',10)
        async def stream():
            # Streamed ASR and a model promise in the same final packet.
            yield response(server_content=content(input_transcription=NS(text=phrase[:split],finished=False)))
            yield response(server_content=content(input_transcription=NS(text=phrase[split:],finished=True),
                output_transcription=NS(text='Posso buscar isso nas lembrancas.'),turn_complete=True))
            raise asyncio.CancelledError()
        owner.session=Mock();owner.session.receive=stream
        with patch.object(fish_audio,'enabled',return_value=True),patch.object(fish_audio,'FishVoiceSession',return_value=voice),patch('core.memory_recall.retrieve',return_value=result):
            with self.assertRaises(asyncio.CancelledError):await owner._receive_audio()
        self.assertTrue(owner._protocol_input_consumed)
        events=[call.args[0] for call in owner.ui.show_neural_memory.call_args_list]
        self.assertTrue(events[0]['pending']);self.assertTrue(events[-1]['active'])
        spoken=' '.join(call.args[0] for call in voice.feed.call_args_list)
        self.assertNotIn('Posso buscar isso',spoken)
        return events[-1],spoken

    async def test_real_voice_phrase_enters_mode_instead_of_only_promising(self):
        payload,spoken=await self.run_request('Meu querido, procura na lembranca uma coisa para mim.',{'ok':True,'items':[]})
        self.assertTrue(payload['awaitingTopic']);self.assertIn('Qual assunto',spoken)

    async def test_voice_search_with_no_records_does_not_hide_the_brain(self):
        payload,spoken=await self.run_request('Quero que voce busque na lembranca algo sobre musica que eu falei.',{'ok':True,'items':[]})
        self.assertEqual(payload['outcome'],'empty');self.assertIn('Nao encontrei',spoken)


if __name__=='__main__':unittest.main()
