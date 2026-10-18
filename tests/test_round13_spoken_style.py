import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch,Mock
from types import SimpleNamespace
from core import personality
from core.spoken_style import protocol_text


class SpokenStyle(unittest.TestCase):
    def test_protocol_polish_preserves_data_and_questions(self):
        self.assertEqual(protocol_text('Encontrei 3 projetos, senhor.'),'Encontrei 3 projetos.')
        self.assertEqual(protocol_text('Deseja continuar, senhor?'),'Deseja continuar?')
        for text in ('Bem-vindo, senhor.', 'O titulo e Senhor dos Aneis.',
                     'Mensagem: "Obrigado, senhor."', 'Falha 401: conexao indisponivel.'):
            self.assertEqual(protocol_text(text),text)

    def test_explicit_natural_style_survives_reload_without_learning_quotes(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(personality,'path',return_value=Path(folder)/'personality.json'):
            personality.observe('Fale de forma mais natural.',1)
            state=personality.snapshot()
            self.assertEqual(state['dimensions']['familiarity']['value'],75)
            self.assertEqual(state['dimensions']['familiarity']['source'],'explicit')
            personality.observe('O texto diz "seja mais formal".',2)
            self.assertEqual(personality.snapshot()['dimensions']['familiarity']['value'],75)

    def test_style_guidance_changes_with_profile_without_new_permissions(self):
        low=personality.style_guidance(dict.fromkeys(personality.BASE,10))
        high=personality.style_guidance(dict.fromkeys(personality.BASE,90))
        for key in personality.BASE:self.assertNotEqual(low[key],high[key])
        self.assertIn('nao autoriza executar',high['initiative'])
        self.assertIn('sofrimento',high['humor'])


class HostSpeech(unittest.IsolatedAsyncioTestCase):
    async def test_same_polished_text_is_logged_and_sent_to_fish(self):
        from main import JarvisLive
        owner=JarvisLive.__new__(JarvisLive)
        owner._protocol_voice_context=Mock(return_value='current')
        owner._protocol_voice_valid=Mock(return_value=True)
        owner.ui=SimpleNamespace(write_log=Mock())
        owner._fish_voice=Mock()
        await owner._speak_protocol('Projeto salvo, senhor.')
        owner.ui.write_log.assert_called_once_with('DIEF JARVIS: Projeto salvo.')
        owner._fish_voice.feed.assert_called_once_with('Projeto salvo.',flush=True)


if __name__=='__main__':unittest.main()
