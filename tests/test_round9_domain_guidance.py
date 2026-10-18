import unittest
from core.system_knowledge import execution_guide
from core.action_outcome import assess
from core.application_context import ApplicationContext
from core.task_execution import ExecutionLedger


class DomainGuidance(unittest.TestCase):
    def test_recent_outcomes_survive_followup_but_expire_and_exclude_payloads(self):
        from unittest.mock import Mock
        clock=Mock(return_value=0);context=ApplicationContext(clock)
        context.record_tool_result('gmail_control',{'action':'read','body':'private payload'},
                                   {'ok':False,'error':'private error'})
        context.observe_user('por que nao funcionou?')
        item=context.snapshot()['recent_operations'][0]
        self.assertEqual(item,{'tool':'gmail_control','action':'read','outcome':'failed','age_seconds':0})
        self.assertNotIn('private',str(context.snapshot()))
        for index in range(20):context.record_tool_result('test',{}, {'ok':True})
        self.assertEqual(len(context.snapshot()['recent_operations']),12)
        clock.return_value=601
        self.assertEqual(context.snapshot()['recent_operations'],[])

    def test_word_fragments_do_not_choose_unrelated_tools(self):
        for request in ('qual programa usar?', 'gosto de fotografia', 'vamos conversar sobre telegramas',
                        'minha ramificacao de ideias', 'quero falar sobre sistemas complexos'):
            with self.subTest(request=request):
                self.assertIsNone(execution_guide(request)['suggested_tool'])
        self.assertEqual(execution_guide('consumo de RAM')['suggested_tool'],'system_status')

    def test_google_calendar_uses_explicit_service_before_generic_agenda(self):
        for request in ('minha agenda do Google', 'calendario do Google', 'agenda   google'):
            with self.subTest(request=request):
                guide=execution_guide(request)
                self.assertEqual(guide['suggested_tool'],'google_calendar')
                self.assertFalse(guide['execution_started'])
        self.assertEqual(execution_guide('minha agenda local')['suggested_tool'],'organizer')

    def test_protocol_mention_is_guidance_not_activation(self):
        for request,tool in (('como esta o projeto da Forja?','forge_protocol'),
                             ('o que o Ultron faz?','ultron_protocol')):
            guide=execution_guide(request,declarations=[])
            self.assertEqual(guide['suggested_tool'],tool)
            self.assertFalse(guide['tool_available'])
            self.assertFalse(guide['execution_started'])

    def test_multiple_domains_remain_visible_to_interpreter(self):
        guide=execution_guide('fixar o clima no painel')
        self.assertTrue(guide['multiple_domains'])
        self.assertEqual(guide['candidate_tools'],['interface_control','weather_report'])
        self.assertFalse(guide['execution_started'])

    def test_rejected_adapter_result_is_failure_in_all_consumers(self):
        result={'accepted':False,'mode':'rejected','speech':'Indisponivel'}
        self.assertEqual(assess(result)['state'],'failed')
        ledger=ExecutionLedger();ledger.record('ultron_protocol',result)
        self.assertEqual(ledger.events[-1]['evidence'],'failed')
        context=ApplicationContext()
        for _ in range(2):context.record_tool_result('ultron_protocol',{},result)
        self.assertTrue(context.tool_retry_check('ultron_protocol',{}))


if __name__=='__main__':unittest.main()
