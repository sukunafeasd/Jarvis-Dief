import unittest
from core.forge_commands import command_for
from core.action_outcome import assess
import test_forge_host_routing as host


class ConditionalCommands(unittest.TestCase):
    def test_nested_new_project_text_does_not_create_another_project(self):
        for text in ('crie um botao para abrir um novo projeto',
                     'crie uma nova textura no projeto',
                     'crie um menu chamado novo projeto'):
            with self.subTest(text=text):self.assertEqual(command_for(text)['action'],'steer')

    def test_direct_new_project_requests_still_create(self):
        for text in ('crie outro projeto chamado Atlas', 'crie um novo projeto',
                     'crie um projeto novo', 'inicie uma nova cena'):
            with self.subTest(text=text):self.assertEqual(command_for(text)['action'],'create')

    def test_conditions_and_sequences_return_to_interpreter(self):
        for text in ('salve o projeto se os testes passarem',
                     'exporte apenas quando terminar', 'cancele o trabalho e crie um site',
                     'salve na biblioteca e exporte para a area de trabalho',
                     'crie um jogo caso o projeto esteja vazio'):
            with self.subTest(text=text):self.assertIsNone(command_for(text))

    def test_terminal_and_partial_statuses_never_mean_success(self):
        for status,expected in (('partial','uncertain'),('failed','failed'),('error','failed'),
                                ('rejected','failed'),('cancelled','failed'),
                                ('pending','pending'),('in_progress','pending')):
            with self.subTest(status=status):
                self.assertEqual(assess({'ok':True,'state':status})['state'],expected)
        self.assertIn('parcial',assess({'state':'partial'})['guidance'])


class HostConditionalCommands(unittest.IsolatedAsyncioTestCase):
    owner=host.RoutingTests.owner

    async def test_host_does_not_drop_condition_or_second_action(self):
        owner=self.owner();owner._forge_mode=True
        for text in ('salve o projeto se os testes passarem','cancele o trabalho e crie um site'):
            self.assertFalse(await owner._route_protocol_user(text))
        owner._dispatch_forge.assert_not_awaited()


if __name__=='__main__':unittest.main()
