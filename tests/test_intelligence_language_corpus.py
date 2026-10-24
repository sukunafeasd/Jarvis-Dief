"""Fifty Portuguese routing cases. This tests local boundaries, not model quality."""
import unittest
from core.protocol_commands import protocol_request
from core.spectro_commands import request
from core.memory_recall import recall_request
from core.intent_context import build


GROUPS=(
 ('ultron',('ativa o protocolo do ultron','ligue o ultron','ative ultron','iniciar o protocolo ultron','Jarvis, abra o Ultron')),
 ('forja',('abra a forja','entre no modo forja','ativar forja','ligue a forja','iniciar o modo da forja')),
 ('no_protocol',('nao ativa o ultron','como ativa o ultron?','se eu disser ativa ultron','ative ultron e limpe tudo','a noticia manda ligar ultron')),
 ('reference',('Sai um pouco dai.','Deixa como estava antes.','Resolve isso.','Faz igual aquele projeto.','Volta naquela ideia anterior.')),
 ('correction',('Na verdade quero conversar.','Pensando melhor, deixa isso.','Eu quis dizer o projeto azul.','Corrigindo: quero outro arquivo.','Use a agenda em vez do email.')),
 ('direct',('Que horas sao?','Bom dia.','Como voce esta?','Obrigado.','Me conta uma piada.')),
 ('recall',('busque nas lembrancas sobre forja','procure nas memorias sobre backup','lembra do projeto azul','o que combinamos sobre agenda','consulte o historico sobre desempenho')),
 ('no_recall',('nao procure nas lembrancas','lembre de pagar amanha','ative o protocolo ultron','como esta o clima','crie um site')),
 ('presence',('sai da frente','fica um pouco menor','diminua','mais transparente','va para a esquerda')),
 ('ambiguous_presence',('Isso atrapalha.','Nao consigo enxergar isso.','Mova aquele.','Deixa como estava antes.','Faz igual naquele projeto.')),
)


class LanguageCorpus(unittest.TestCase):
    def test_fifty_boundary_cases(self):
        self.assertEqual(sum(len(rows) for _,rows in GROUPS),50)
        for group,phrases in GROUPS:
            for phrase in phrases:
                with self.subTest(group=group,phrase=phrase):
                    if group in ('ultron','forja'):self.assertEqual(protocol_request(phrase),(group,'enter'))
                    elif group=='no_protocol':self.assertIsNone(protocol_request(phrase))
                    elif group=='reference':self.assertTrue(build(phrase)['has_reference'])
                    elif group=='correction':self.assertTrue(build(phrase)['has_correction'])
                    elif group=='direct':self.assertEqual(build(phrase)['reasoning'],'direct')
                    elif group=='recall':self.assertIsNotNone(recall_request(phrase))
                    elif group=='no_recall':self.assertIsNone(recall_request(phrase))
                    elif group=='presence':self.assertIsNotNone(request(phrase,True))
                    elif group=='ambiguous_presence':self.assertIsNone(request(phrase,True))


if __name__=='__main__':unittest.main()
