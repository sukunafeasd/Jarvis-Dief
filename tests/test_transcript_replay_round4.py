import asyncio
import random
import unittest
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, Mock, patch
from core.transcript_replay import TranscriptReplay
from tests.test_voice_interrupt import assistant_fixture, content, response


class ReplayTests(unittest.TestCase):
    def known(self):
        replay=TranscriptReplay();replay.feed('Esta resposta ja foi falada antes.');replay.finish()
        return replay

    def test_fragment_boundaries_do_not_change_replay_detection(self):
        replay=self.known()
        result=''.join(replay.feed(part) for part in ['Esta ','resposta ','ja foi ','falada ','antes.'])+replay.flush()
        self.assertEqual(result,'')

    def test_four_hundred_random_fragmentations_preserve_novel_reply(self):
        randomizer=random.Random(10416)
        previous='Esta resposta ja foi falada antes.'
        for _ in range(400):
            replay=self.known();fragments=[];offset=0
            while offset<len(previous):
                size=randomizer.randint(1,9);fragments.append(previous[offset:offset+size]);offset+=size
            self.assertEqual(''.join(replay.feed(part) for part in fragments)+replay.flush(),'')
            replay.finish()
            self.assertEqual(replay.feed('Uma nova resposta sem relacao.'),'Uma nova resposta sem relacao.')

    def test_divergent_prefix_keeps_all_novel_text_and_digits(self):
        replay=self.known();parts=['Esta ','resposta ','foi alterada: ','1','1','2','.']
        self.assertEqual(''.join(replay.feed(part) for part in parts)+replay.flush(),''.join(parts))

    def test_short_legitimate_replies_are_never_suppressed(self):
        replay=self.known()
        self.assertEqual(replay.feed('Esta ')+replay.flush(),'Esta ')
        replay.finish();self.assertEqual(replay.feed('Sim, sim. '),'Sim, sim. ')

    def test_extended_numeric_token_is_not_a_replayed_code(self):
        for fragments in (['1234567890123'],['123456789012','3'],['123456','789012','3']):
            replay=TranscriptReplay();replay.feed('Codigo 123456789012');replay.finish()
            self.assertEqual(''.join(replay.feed(part) for part in fragments)+replay.flush(),'1234567890123')

    def test_replayed_tail_with_novel_suffix_keeps_only_new_words(self):
        replay=self.known()
        self.assertEqual(replay.feed('ja foi falada antes. Agora vamos continuar.'),' Agora vamos continuar.')

    def test_explicit_new_request_allows_same_answer_and_memory_is_bounded(self):
        replay=self.known();replay.reset()
        self.assertEqual(replay.feed('Esta resposta ja foi falada antes.'),'Esta resposta ja foi falada antes.')
        replay.feed('x'*30000);self.assertLessEqual(len(replay.current),replay.LIMIT)


class ReceiveReplayTests(unittest.IsolatedAsyncioTestCase):
    async def test_replayed_small_fragments_never_reach_synthesis(self):
        owner=assistant_fixture();owner._is_speaking=False
        owner._remember_assistant_turn=AsyncMock()
        voice=Mock(pending=False);voice.close=AsyncMock()
        async def stream():
            yield response(server_content=content(output_transcription=NS(text='Esta resposta ja foi falada antes.'),turn_complete=True))
            for fragment in ['Esta ','resposta ','ja foi ','falada ','antes.']:
                yield response(server_content=content(output_transcription=NS(text=fragment)))
            yield response(server_content=content(turn_complete=True))
            raise asyncio.CancelledError()
        owner.session=Mock();owner.session.receive=stream
        with patch('core.fish_audio.enabled',return_value=True),patch('core.fish_audio.FishVoiceSession',return_value=voice):
            with self.assertRaises(asyncio.CancelledError):await owner._receive_audio()
        spoken=[call.args[0] for call in voice.feed.call_args_list if call.kwargs.get('incremental')]
        self.assertEqual(spoken,['Esta resposta ja foi falada antes.'])
