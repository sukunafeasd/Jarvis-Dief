import unittest
from unittest.mock import Mock
from core.application_context import ApplicationContext
from core.intent_context import build
from core.system_knowledge import execution_guide


class ContextualDecision(unittest.TestCase):
    def test_complex_reference_keeps_planning_budget(self):
        result=build('compare aquele projeto com o anterior')
        self.assertEqual(result['reasoning'],'planned')
        self.assertTrue(result['has_reference'])

    def test_correction_takes_precedence_over_complex_reference(self):
        result=build('compare aquele projeto, na verdade deixa como estava')
        self.assertEqual(result['reasoning'],'contextual')
        self.assertTrue(result['has_correction'])

    def test_followup_uses_failure_evidence_without_creating_command(self):
        for evidence in ({'outcome':'uncertain'},{'outcome':'pending'},
                         {'outcome':'tool_reported','presentation':'failed'}):
            for text in ('e agora?', 'nao apareceu', 'tenta de novo'):
                with self.subTest(evidence=evidence,text=text):
                    result=build(text,conversation={'recent_operations':[evidence]})
                    self.assertEqual(result['reasoning'],'contextual')
                    self.assertTrue(result['needs_recovery_context'])
                    self.assertNotIn('tool_call',result)

    def test_old_failure_does_not_make_unrelated_conversation_a_recovery(self):
        result=build('bom dia',conversation={'recent_operations':[{'outcome':'failed'}]})
        self.assertFalse(result['needs_recovery_context'])
        self.assertEqual(result['reasoning'],'direct')

    def test_malformed_optional_context_is_not_evidence(self):
        for conversation in (None,[],{'recent_operations':None,'unresolved_operations':'bad'}):
            result=build('e agora?',conversation=conversation)
            self.assertFalse(result['needs_recovery_context'])

    def test_multistep_request_has_guidance_for_data_and_presentation(self):
        result=execution_guide('fixar o clima no painel',declarations=[{'name':'weather_report'},{'name':'interface_control'}])
        self.assertEqual(set(result['candidate_guidance']),{'weather_report','interface_control'})
        self.assertTrue(result['selection_required'])
        self.assertFalse(result['execution_started'])
        self.assertIn('nao e prioridade',result['suggestion_basis'])

    def test_unavailable_tool_remains_distinct_from_available_display(self):
        result=execution_guide('fixar meus emails no painel',declarations=[{'name':'interface_control'}])
        self.assertFalse(result['candidate_availability']['gmail_control'])
        self.assertTrue(result['candidate_availability']['interface_control'])
        self.assertIn('gmail_control',result['candidate_guidance'])

    def test_reference_gets_selected_target_without_executing_it(self):
        context=ApplicationContext()
        context.record_collection('tasks',[{'id':'a','title':'Revisar projeto'}])
        context.resolve_record('tasks',1)
        for text in ('faz isso', 'e aquele?', 'por que nao deu?', 'na verdade deixa pra depois'):
            with self.subTest(text=text):
                context.observe_user(text)
                result=build(text,conversation=context.snapshot())
                self.assertEqual(result['conversation_state']['selections']['tasks']['id'],'a')
                self.assertNotIn('tool_call',result)

    def test_guide_keeps_failure_reference_not_private_payload(self):
        context=ApplicationContext()
        context.record_tool_result('worker',{'action':'execute','command':'PRIVATE'},
                                   {'ok':False,'uncertain':True,'job_id':'job-1','stderr':'PRIVATE'})
        context.observe_user('por que nao deu certo?')
        result=execution_guide(context.user_text,context,[])
        self.assertEqual(result['current_context']['unresolved_operations'][0]['references']['job_id'],'job-1')
        self.assertNotIn('PRIVATE',str(result))
        self.assertFalse(result['execution_started'])

    def test_expired_selection_is_not_given_as_current_target(self):
        clock=Mock(return_value=0);context=ApplicationContext(clock)
        context.remember_selection('tasks',{'id':'old'})
        clock.return_value=601
        result=execution_guide('faz aquele',context,[])
        self.assertEqual(result['current_context']['selections'],{})

    def test_browser_fallback_is_consistent_with_candidates(self):
        result=execution_guide('abra o navegador',declarations=[{'name':'structured_browser'}])
        self.assertEqual(result['candidate_tools'],['structured_browser'])
        self.assertIn('structured_browser',result['candidate_guidance'])
        self.assertFalse(result['selection_required'])


if __name__=='__main__':unittest.main()
