import asyncio
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock,AsyncMock,patch

from core.speech_text import speech_text
from core.spectro_commands import request
from core.spectro_observer import matching_controls


class SpeechAndTargets(unittest.TestCase):
    def test_visual_syntax_is_not_read_literally(self):
        self.assertEqual(speech_text('## **Clima**\n- 20°C & chuva 80%'),
                         'Clima 20 graus Celsius e chuva 80 por cento')
        self.assertEqual(speech_text('[Fonte](https://example.test/x) custa R$ 12,50'),
                         'Fonte custa 12,50 reais')

    def test_numbers_negation_and_accents_are_preserved(self):
        self.assertEqual(speech_text('3 < 5 e 10 > 7'),'3 < 5 e 10 > 7')
        self.assertEqual(speech_text('Não caiu: -2,5%. São 12 km/h.'),
                         'Não caiu: -2,5 por cento. São 12 quilometros por hora.')

    def test_natural_named_marking(self):
        for phrase in ('marca configuracoes nessa aba aberta','marque o icone de configuracoes','pode destacar configuracoes'):
            self.assertEqual(request(phrase,True),('highlight',{'query':'configuracoes','shape':'outline'}))
        self.assertIsNone(request('nao marque configuracoes',True))

    def test_unique_observed_target_and_ambiguity(self):
        controls=[{'name':'Abrir Configurações','control_id':'a'}, {'name':'Salvar arquivo','control_id':'b'}]
        self.assertEqual(matching_controls(controls,'configuracoes'),[controls[0]])
        self.assertEqual(matching_controls(controls,'config'),[controls[0]])
        self.assertEqual(matching_controls(controls,'excluir'),[])
        controls.append({'name':'Configurações da conta','control_id':'c'})
        self.assertEqual(len(matching_controls(controls,'configuracoes')),2)


class SessionRenewal(unittest.IsolatedAsyncioTestCase):
    def briefing_owner(self):
        from main import JarvisLive
        owner=JarvisLive.__new__(JarvisLive)
        owner.session=Mock(send_client_content=AsyncMock())
        owner.ui=Mock();owner.ui.show_verified_manifestation.return_value=True
        owner._manual_rest=False;owner._awake=True;owner._is_speaking=False
        owner._response_epoch=0;owner._played_audio_seconds=0.
        owner.audio_in_queue=asyncio.Queue();owner._tail_active=lambda:False
        owner._fish_voice=Mock(pending=False,_failed=False)
        owner._fish_voice.feed.side_effect=lambda *a,**kw:setattr(owner,'_played_audio_seconds',owner._played_audio_seconds+1)
        return owner

    async def test_three_news_chapters_are_presented_before_their_audio(self):
        owner=self.briefing_owner();events=[]
        package={'data':{'news':{'model':{'kind':'news','items':[
            {'title':'Noticia A'},{'title':'Noticia B'},{'title':'Noticia C'}]}}},'unavailable':[]}
        def present(model):events.append(('screen',model['focus']));return True
        def speak(text,**kw):
            owner._played_audio_seconds+=1
            events.append(('speech',text))
        owner.ui.show_verified_manifestation.side_effect=present
        owner._fish_voice.feed.side_effect=speak
        with patch('core.session_refresh.collect_updates',AsyncMock(return_value=package)),patch('core.daily_briefing.mark_delivered') as mark:
            await owner._send_startup_briefing()
        self.assertEqual([kind for kind,_ in events],['speech','screen','speech','screen','speech','screen','speech'])
        self.assertEqual([item for kind,item in events if kind=='screen'],[0,1,2])
        mark.assert_called_once()

    async def test_rejected_visual_cannot_be_narrated_or_marked_delivered(self):
        owner=self.briefing_owner();owner.ui.show_verified_manifestation.return_value=False
        package={'data':{'weather':{'temperature':25}},'unavailable':[]}
        with patch('core.session_refresh.collect_updates',AsyncMock(return_value=package)),patch('core.daily_briefing.mark_delivered') as mark:
            with self.assertRaisesRegex(RuntimeError,'interface nao confirmou'):
                await owner._send_startup_briefing()
        self.assertEqual(owner._fish_voice.feed.call_count,1)
        mark.assert_not_called();self.assertFalse(owner._refresh_in_progress)

    async def test_interruption_cannot_continue_other_news(self):
        owner=self.briefing_owner()
        def interrupt(text,**kw):
            owner._played_audio_seconds+=1;owner._response_epoch+=1
        owner._fish_voice.feed.side_effect=interrupt
        package={'data':{'weather':{'temperature':25}},'unavailable':[]}
        with patch('core.session_refresh.collect_updates',AsyncMock(return_value=package)),patch('core.daily_briefing.mark_delivered') as mark:
            await owner._send_startup_briefing()
        owner.ui.show_verified_manifestation.assert_not_called()
        mark.assert_not_called();self.assertFalse(owner._refresh_in_progress)

    async def test_real_receiver_requests_renewal_on_goaway(self):
        from tests.test_voice_interrupt import assistant_fixture,response
        owner=assistant_fixture()
        owner.request_reconnect=Mock()
        owner._fish_native_fallback=True
        async def receive():
            packet=response()
            packet.go_away=NS(time_left='20s')
            yield packet
            raise asyncio.CancelledError()
        owner.session=Mock();owner.session.receive=receive
        with patch('core.fish_audio.enabled',return_value=False):
            with self.assertRaises(asyncio.CancelledError):await owner._receive_audio()
        owner.request_reconnect.assert_called_once_with(keep_context=True,reason='renovacao da sessao de voz')

    async def test_native_recovery_does_not_recreate_failed_fish(self):
        from tests.test_voice_interrupt import assistant_fixture
        owner=assistant_fixture();owner._fish_native_fallback=True;owner.session=Mock()
        with patch('core.fish_audio.enabled',return_value=True),patch('core.fish_audio.FishVoiceSession') as fish:
            owner._initialize_voice()
        fish.assert_not_called()
        self.assertIsNone(owner._fish_voice)


if __name__=='__main__':unittest.main()
