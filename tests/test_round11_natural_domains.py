import unittest
from core.system_knowledge import execution_guide


class NaturalDomains(unittest.TestCase):
    def test_common_plural_requests_keep_their_domain(self):
        examples={
            'veja os emails completos':'gmail_control',
            'leia meus e-mails':'gmail_control',
            'quais tarefas tenho':'organizer',
            'mostre meus compromissos':'organizer',
            'buscar nas lembrancas':'memory_control',
            'consulte minhas memorias':'memory_control',
            'liste meus projetos':'local_resources',
            'busque meus contatos':'local_resources',
            'consulte as transcricoes':'local_resources',
            'veja minhas notas pessoais':'local_resources',
            'liste meus backups':'resource_backups',
        }
        for phrase,tool in examples.items():
            with self.subTest(phrase=phrase):
                result=execution_guide(phrase)
                self.assertEqual(result['suggested_tool'],tool)
                self.assertFalse(result['execution_started'])

    def test_word_boundaries_still_prevent_accidental_domains(self):
        for phrase in ('programas educativos','ramificacoes','contatosfera','memoriam',
                       'projetores coloridos','tarefasse','telegramas antigos'):
            with self.subTest(phrase=phrase):
                self.assertIsNone(execution_guide(phrase)['suggested_tool'])

    def test_specific_service_overrides_generic_plural_domain(self):
        self.assertEqual(execution_guide('meus compromissos na agenda do google')['suggested_tool'],'google_calendar')
        self.assertEqual(execution_guide('projetos na forja')['suggested_tool'],'forge_protocol')
        self.assertEqual(execution_guide('meus e-mails no outlook')['suggested_tool'],'outlook_service')

    def test_compound_request_exposes_availability_without_inventing_connection(self):
        result=execution_guide('fixar meus emails no painel',declarations=[{'name':'interface_control'}])
        self.assertEqual(result['candidate_availability'],{'interface_control':True,'gmail_control':False})
        self.assertTrue(result['multiple_domains'])
        self.assertFalse(result['execution_started'])
        unknown=execution_guide('emails')
        self.assertIsNone(unknown['candidate_availability']['gmail_control'])


if __name__=='__main__':unittest.main()
