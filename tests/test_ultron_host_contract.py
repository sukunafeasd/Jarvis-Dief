import unittest
from types import SimpleNamespace
from core.ultron_user_context import finalized_text
from core.ultron_presentation import projection,monitor_alerts

class UltronHostContractTests(unittest.TestCase):
    def test_partial_yes_never_authorizes(self):
        self.assertIsNone(finalized_text(SimpleNamespace(finished=False),['sim']))
        self.assertIsNone(finalized_text(SimpleNamespace(finished=None),['sim']))
        self.assertIsNone(finalized_text(None,['sim']))

    def test_final_text_includes_negative_continuation(self):
        self.assertEqual(finalized_text(SimpleNamespace(finished=True),['sim,','nao execute']), 'sim, nao execute')
        self.assertIsNone(finalized_text(SimpleNamespace(finished=True),[]))

    def test_projection_uses_real_records(self):
        value=projection({'vault':[{'file_count':3}],'telemetry':{'cpu_percent':None},'findings':[{'id':'defender','detail':'{"realtime":false}'}]})
        self.assertEqual(value['vault_count'],1);self.assertIsNone(value['telemetry']['cpu_percent'])
        self.assertFalse(value['findings'][0]['detail']['realtime'])

    def test_monitor_does_not_replay_old_pressure(self):
        state={'monitor':{'enabled':True,'events':[{'kind':'cpu_percent','threshold':90,'value':99}]},'telemetry':{'cpu_percent':12}}
        self.assertEqual(monitor_alerts(state),[])
        state['telemetry']['cpu_percent']=95;self.assertEqual(monitor_alerts(state)[0]['value'],95)
        state['monitor']['enabled']=False;self.assertEqual(monitor_alerts(state),[])
