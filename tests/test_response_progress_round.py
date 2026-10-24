import unittest
from types import SimpleNamespace as NS

from core.response_progress import has_response_progress
from core.application_context import ApplicationContext


class ResponseProgressTests(unittest.TestCase):
    def packet(self, **content):
        return NS(server_content=NS(**content))

    def test_empty_and_thought_packets_do_not_extend_silence(self):
        for packet in (NS(), self.packet(model_turn=NS(parts=[])),
                       self.packet(output_transcription=NS(text='  ')),
                       self.packet(model_turn=NS(parts=[NS(text='thinking', thought=True)])),
                       NS(tool_call=NS(function_calls=[]))):
            with self.subTest(packet=packet):
                self.assertFalse(has_response_progress(packet))

    def test_real_output_tools_and_completion_are_progress(self):
        for packet in (NS(data=b'pcm'), self.packet(turn_complete=True),
                       self.packet(output_transcription=NS(text='Ola')),
                       NS(tool_call=NS(function_calls=[NS(name='status')])),
                       self.packet(model_turn=NS(parts=[NS(text='Resposta')])),
                       self.packet(model_turn=NS(parts=[NS(inline_data=NS(data=b'pcm'))]))):
            with self.subTest(packet=packet):
                self.assertTrue(has_response_progress(packet))

    def test_followup_cannot_duplicate_pending_send(self):
        context=ApplicationContext()
        key, previous=context.begin_send('mail','recipient','message')
        self.assertIsNone(previous)
        context.observe_user('deu certo?')
        _, previous=context.begin_send('mail','recipient','message')
        self.assertTrue(previous['uncertain'])
        context.finish_send(key,{'ok':False,'uncertain':True,'error':'timeout'})
        context.observe_user('e agora?')
        _, previous=context.begin_send('mail','recipient','message')
        self.assertEqual(previous['error'],'timeout')

    def test_confirmed_send_can_be_requested_again_in_new_turn(self):
        context=ApplicationContext()
        key,_=context.begin_send('mail','recipient','message')
        context.finish_send(key,{'ok':True})
        context.observe_user('envie novamente')
        _,previous=context.begin_send('mail','recipient','message')
        self.assertIsNone(previous)

    def test_old_uncertain_sends_do_not_consume_new_request_limit(self):
        context=ApplicationContext()
        for index in range(20):
            context.begin_send('mail','recipient',str(index))
        with self.assertRaisesRegex(ValueError,'mesmo pedido'):
            context.begin_send('mail','recipient','twenty-first')
        context.observe_user('envie uma mensagem diferente')
        _,previous=context.begin_send('mail','recipient','new')
        self.assertIsNone(previous)
        _,previous=context.begin_send('mail','recipient','0')
        self.assertTrue(previous['uncertain'])

    def test_pending_history_is_bounded_without_forgetting_uncertainty(self):
        context=ApplicationContext()
        for index in range(128):
            context.observe_user('new request')
            context.begin_send('mail','recipient',str(index))
        context.observe_user('one more')
        with self.assertRaisesRegex(ValueError,'sem resultado confirmado'):
            context.begin_send('mail','recipient','overflow')
        key,previous=context.begin_send('mail','recipient','0')
        self.assertTrue(previous['uncertain'])
        context.finish_send(key,{'ok':True})
        context.observe_user('new request after verification')
        self.assertIsNone(context.begin_send('mail','recipient','overflow')[1])


if __name__ == '__main__':
    unittest.main()
