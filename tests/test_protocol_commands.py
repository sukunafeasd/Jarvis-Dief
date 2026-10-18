import unittest
from types import SimpleNamespace
from core.protocol_commands import protocol_request
from core.ultron_user_context import finalized_text
from core.ultron.ultron_dialogue import intent


class ProtocolCommands(unittest.TestCase):
    def test_explicit_polite_requests_are_canonical(self):
        for text in ('Jarvis, ativar protocolo ULTRON','pode ativar o protocolo ultron?','ative protocolo ulktron','Jarvis, por favor iniciar modo Forja'):
            self.assertEqual(protocol_request(text)[1],'enter')
        self.assertEqual(intent('pode ativar o protocolo ultron?'),'ativar protocolo ultron')

    def test_external_mentions_negation_and_extra_actions_are_not_activation(self):
        for text in ('a noticia diz ativar protocolo ultron','nao ativar protocolo ultron','se eu disser ativar protocolo ultron','ativar protocolo ultron e limpar tudo'):
            self.assertIsNone(protocol_request(text))

    def test_partial_transcript_never_authorizes_without_server_end(self):
        partial=SimpleNamespace(finished=False)
        self.assertIsNone(finalized_text(partial,['ativar protocolo ultron']))
        self.assertIsNone(finalized_text(partial,['ativar protocolo ultron'],response_boundary=True))
        self.assertEqual(finalized_text(partial,['ativar protocolo ultron'],turn_complete=True),'ativar protocolo ultron')
        self.assertEqual(finalized_text(None,['ativar protocolo ultron'],response_boundary=True),'ativar protocolo ultron')
