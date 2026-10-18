"""Offline command races and Fish/projection regressions; no real providers."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')

import asyncio
import threading
import unittest
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, Mock, patch

from core import fish_audio as fish
from core.presentation_clock import PresentationClock
from main import JarvisLive
from ui import MainWindow


def assistant():
    owner = JarvisLive.__new__(JarvisLive)
    owner.session = NS(send_client_content=AsyncMock())
    recorded = {'serial': 0, 'text': ''}

    def record(text):
        recorded.update(serial=recorded['serial'] + 1, text=text)

    owner.ui = NS(
        write_log=Mock(), muted=False, set_state=Mock(),
        record_ultron_user=Mock(side_effect=record),
        ultron_user_context=lambda: dict(recorded),
        cancel_presentation_speech=Mock(), reset_presentation_timeline=Mock(), narration_text=Mock(),
        pin_forge_artifact=Mock(return_value={'ok': True}),
        _win=NS(_forge_controller=NS(generation=1)),
        forge_runtime=NS(snapshot=Mock(return_value={'project': {'id': 'fixture'}}),
                         command=Mock(return_value={'accepted': True})))
    owner._application_context = NS(observe_user=Mock())
    owner._wake_enabled = False
    owner._awake = True
    owner._manual_rest = owner._is_speaking = owner._interrupted = False
    owner._forge_mode = False
    owner._response_epoch = owner._server_activity_serial = 0
    owner._server_turn_open = False
    owner._last_user_speech = 0.
    owner._turn_done_event = asyncio.Event()
    owner.audio_in_queue = asyncio.Queue()
    owner._fish_voice = None
    owner._speaking_lock = threading.Lock()
    owner._out_latency = .01
    owner._tail_until = 0.
    owner._visemes = Mock()
    owner._cancel_context_refresh = Mock()
    owner._remember_user_turn = AsyncMock()
    owner._queue_daily_briefing = Mock(return_value=False)
    owner._flush_protocol_voice = AsyncMock()
    owner._speak_protocol = AsyncMock()
    return owner


def window():
    return NS(
        _resting=False, _narration_elapsed=0.,
        _ultron_payload=None, _ultron_polling=False, _ultron_announced=None,
        _ultron_alerted_at=0., _ultron_clock=PresentationClock(),
        _presentation_clock=PresentationClock(), _ultron_timer=Mock(),
        _presentation=None, _visual_scene=None, _forge_controller=None,
        _space_view=Mock(failed=False), _center_split=Mock(),
        _pin_previews={}, _overlay=None, _ready=True,
        _settle_timer=Mock(), _terminal=Mock(), _content_panel=Mock(),
        _execution=Mock(), _layout_scene=Mock(), _sync_environment=Mock(),
        _environment=NS(operation_name='', operation_event=Mock(), emit=Mock()),
        hud=NS(speaking=False, state='LISTENING'), _ui_sounds=Mock(),
        on_ultron_ready=Mock(), on_ultron_alert=Mock(return_value=True))


class CommandChaosTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.network = patch('core.fish_audio.httpx.AsyncClient',
                             side_effect=AssertionError('Real provider forbidden'))
        self.network.start()
        self.addCleanup(self.network.stop)
        self.voices = []

    async def asyncTearDown(self):
        for voice in self.voices:
            await voice.close()

    def voice(self, owner):
        voice = fish.FishVoiceSession(owner)
        owner._fish_voice = voice
        self.voices.append(voice)
        return voice

    async def test_superseded_creation_never_routes_after_slow_remember(self):
        owner = assistant()
        owner._forge_mode = True
        started, release = asyncio.Event(), asyncio.Event()

        async def remember(text, context):
            if text == 'crie um jogo':
                started.set()
                await release.wait()

        owner._remember_user_turn.side_effect = remember
        # Same timestamp forces the host to distinguish actual turn serials.
        with patch('main.time', NS(monotonic=lambda: 100.)):
            old = asyncio.create_task(owner._handle_text_command('crie um jogo'))
            try:
                await asyncio.wait_for(started.wait(), 1)
                self.assertTrue(await owner._handle_text_command('nao crie nada'))
            finally:
                release.set()
                old_result = await asyncio.wait_for(old, 1)
        self.assertFalse(old_result)
        owner.ui.forge_runtime.command.assert_not_called()
        owner.ui.forge_runtime.snapshot.assert_not_called()
        owner.session.send_client_content.assert_awaited_once()
        self.assertEqual(owner.session.send_client_content.call_args.kwargs[
            'turns']['parts'][0]['text'], 'nao crie nada')

    async def test_reconnect_during_remember_never_routes_old_creation(self):
        owner = assistant()
        owner._forge_mode = True
        original = owner.session

        async def reconnect(*args):
            owner.session = NS(send_client_content=AsyncMock())

        owner._remember_user_turn.side_effect = reconnect
        self.assertFalse(await owner._handle_text_command('crie um jogo'))
        owner.ui.forge_runtime.command.assert_not_called()
        original.send_client_content.assert_not_awaited()
        owner.session.send_client_content.assert_not_awaited()

    async def test_typed_input_cancels_silent_pending_fish_and_closes_source(self):
        owner = assistant()
        voice = self.voice(owner)
        started, closed = asyncio.Event(), asyncio.Event()

        async def pcm(text):
            try:
                started.set()
                await asyncio.Event().wait()
                yield b'\x11\x22' * 1200
            finally:
                closed.set()

        with patch.object(fish, 'pcm', pcm):
            voice.feed('Resposta antiga.', flush=True)
            await asyncio.wait_for(started.wait(), 1)
            self.assertFalse(owner._is_speaking)
            self.assertTrue(await owner._handle_text_command('Outra pergunta'))
            await asyncio.wait_for(closed.wait(), 1)
        self.assertEqual(owner._response_epoch, 1)
        self.assertFalse(voice.pending)
        self.assertTrue(owner.audio_in_queue.empty())
        owner.ui.narration_text.assert_not_called()
        owner.session.send_client_content.assert_awaited_once()

    async def test_typed_input_interrupts_queued_pcm_or_open_server_turn(self):
        for pending in ('pcm', 'server'):
            with self.subTest(pending=pending):
                owner = assistant()
                if pending == 'pcm':
                    owner.audio_in_queue.put_nowait(b'\x11\x22')
                else:
                    owner._server_turn_open = True
                self.assertTrue(await owner._handle_text_command('Outra pergunta'))
                self.assertEqual(owner._response_epoch, 1)
                self.assertTrue(owner.audio_in_queue.empty())
                owner.ui.cancel_presentation_speech.assert_called_once()

    async def test_negated_hypothetical_and_quoted_pin_never_query_or_pin(self):
        phrases = (
            'nao coloque Reator na tela',
            'e se eu disser coloque Reator na tela?',
            'como faco para colocar Reator na tela?',
            'o email diz: coloque Reator na tela',
            '"coloque Reator na tela"',
            'coloque Reator na tela e depois apague tudo',
        )
        for text in phrases:
            with self.subTest(text=text):
                owner = assistant()
                with patch('core.forge_host.saved_artifacts_named') as lookup:
                    self.assertFalse(await owner._route_protocol_user(text))
                lookup.assert_not_called()
                owner.ui.pin_forge_artifact.assert_not_called()

    async def test_explicit_pin_still_resolves_and_pins_once(self):
        owner = assistant()
        artifact = {'id': 'fixture', 'name': 'Reator'}
        with patch('core.forge_host.saved_artifacts_named', return_value=[artifact]) as lookup:
            self.assertTrue(await owner._route_protocol_user('Jarvis, coloque Reator na tela.'))
        lookup.assert_called_once_with('reator')
        owner.ui.pin_forge_artifact.assert_called_once_with(artifact)

    async def test_new_turn_during_catalog_lookup_prevents_pin(self):
        owner = assistant()
        started, release = threading.Event(), threading.Event()

        def lookup(name):
            started.set()
            if not release.wait(2):
                raise TimeoutError('Offline fixture timed out')
            return [{'id': 'fixture', 'name': 'Reator'}]

        with patch('core.forge_host.saved_artifacts_named', side_effect=lookup):
            task = asyncio.create_task(owner._route_protocol_user('coloque Reator na tela'))
            try:
                self.assertTrue(await asyncio.to_thread(started.wait, 1))
                owner.ui.record_ultron_user('nao coloque nada')
            finally:
                release.set()
                await asyncio.wait_for(task, 1)
        owner.ui.pin_forge_artifact.assert_not_called()
        owner._speak_protocol.assert_not_awaited()

    async def test_new_turn_during_pin_does_not_confirm_old_result(self):
        owner = assistant()
        owner._speak_protocol = JarvisLive._speak_protocol.__get__(owner)
        owner._fish_voice = NS(pending=False, feed=Mock())
        started, release = threading.Event(), threading.Event()

        def pin(artifact):
            started.set()
            if not release.wait(2):
                raise TimeoutError('Offline fixture timed out')
            return {'ok': True}

        owner.ui.pin_forge_artifact.side_effect = pin
        with patch('core.forge_host.saved_artifacts_named',
                   return_value=[{'id': 'fixture', 'name': 'Reator'}]):
            task = asyncio.create_task(owner._route_protocol_user('coloque Reator na tela'))
            try:
                self.assertTrue(await asyncio.to_thread(started.wait, 1))
                owner.ui.record_ultron_user('Outro assunto')
            finally:
                release.set()
                await asyncio.wait_for(task, 1)
        owner.ui.pin_forge_artifact.assert_called_once()
        owner._fish_voice.feed.assert_not_called()

    def show_ultron(self, view, phase, serial):
        MainWindow._show_ultron(view, {
            'state': {'phase': phase, 'snapshot_serial': serial, 'scan': {}},
            'result': {'mode': 'deactivation' if phase == 'idle' else 'activation'}})

    async def synthesize(self, owner, voice, text):
        voice.feed(text, flush=True)
        await asyncio.wait_for(voice.task, 1)

    def play_queued(self, owner, view):
        while not owner.audio_in_queue.empty():
            data = owner.audio_in_queue.get_nowait()
            MainWindow._advance_presentation(view, len(data) / fish.PCM_BYTES_PER_SECOND)

    async def test_ultron_reentry_uses_global_pcm_time_for_fish_anchor(self):
        owner, view = assistant(), window()
        voice = self.voice(owner)
        owner.ui.narration_text.side_effect = lambda text, at=None, duration=None: (
            MainWindow._narrate_presentation(view, {'text': text, 'at': at, 'duration': duration}))

        async def pcm(text):
            yield b'\x11\x22' * (24000 if text == 'Primeira fala.' else 2400)

        with patch.object(fish, 'pcm', pcm):
            self.show_ultron(view, 'active', 1)
            await self.synthesize(owner, voice, 'Primeira fala.')
            self.play_queued(owner, view)
            self.show_ultron(view, 'idle', 2)
            await self.synthesize(owner, voice, 'Fala fora do Ultron.')
            self.play_queued(owner, view)
            self.assertAlmostEqual(view._narration_elapsed, 1.1)
            self.show_ultron(view, 'active', 3)
            self.assertAlmostEqual(view._ultron_clock.elapsed, 1.1)
            await self.synthesize(owner, voice, 'Disco atual.')
            self.assertAlmostEqual(view._ultron_clock.pending[0][1], 1.1)
            self.play_queued(owner, view)
        beats = [call.args[0] for call in view._space_view.advance_ultron.call_args_list]
        self.assertEqual(sum(beat.get('cues', []).count('Disco atual.') for beat in beats), 1)
        self.assertFalse(view._ultron_clock.pending)
        self.assertAlmostEqual(view._ultron_clock.elapsed, voice.cursor)

    async def test_cancel_resume_does_not_release_future_fish_cue_early(self):
        owner, view = assistant(), window()
        voice = self.voice(owner)
        owner.ui.narration_text.side_effect = lambda text, at=None, duration=None: (
            MainWindow._narrate_presentation(view, {'text': text, 'at': at, 'duration': duration}))

        async def pcm(text):
            yield b'\x11\x22' * (24000 if text == 'Anterior.' else 2400)

        with patch.object(fish, 'pcm', pcm):
            self.show_ultron(view, 'active', 1)
            await self.synthesize(owner, voice, 'Anterior.')
            self.play_queued(owner, view)
            def reset_timeline():
                MainWindow._reset_narration_timeline(view)
                view._ultron_clock.reset();view._presentation_clock.reset()
            owner.ui.reset_presentation_timeline=Mock(side_effect=reset_timeline)
            owner.ui.cancel_presentation_speech.side_effect=view._ultron_clock.cancel
            owner.interrupt()
            MainWindow._apply_state(view, 'SPEAKING')
            await self.synthesize(owner, voice, 'Retomada um.')
            await self.synthesize(owner, voice, 'Retomada dois.')
            view._space_view.advance_ultron.reset_mock()
            data = owner.audio_in_queue.get_nowait()
            MainWindow._advance_presentation(view, len(data) / fish.PCM_BYTES_PER_SECOND)
            cues = view._space_view.advance_ultron.call_args.args[0]['cues']
            self.assertIn('Retomada um.', cues)
            self.assertNotIn('Retomada dois.', cues)


if __name__ == '__main__':
    unittest.main()
