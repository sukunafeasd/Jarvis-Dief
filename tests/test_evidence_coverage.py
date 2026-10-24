import tempfile
import unittest
from pathlib import Path
from core.action_outcome import assess
from core.application_context import ApplicationContext
from core.task_execution import ExecutionLedger


class EvidenceCoverage(unittest.TestCase):
    def test_partial_read_is_not_failed_or_fully_read(self):
        for flag in ({'complete':False},{'partial':True},{'next_offset':100},
                     {'next_offset':0},{'has_more':True},{'truncated':True},
                     {'extraction_incomplete':True}):
            with self.subTest(flag=flag):
                result=assess({'ok':True,**flag})
                self.assertEqual(result['state'],'tool_reported')
                self.assertEqual(result['coverage'],'partial')

    def test_unknown_coverage_never_becomes_complete(self):
        for value in ({'ok':True},{'ok':True,'next_offset':None},
                      {'ok':True,'truncated':False},'Finished'):
            self.assertNotIn('coverage',assess(value))

    def test_failed_cancelled_pending_and_uncertain_keep_priority(self):
        cases=[({'ok':False},'failed'),({'ok':True,'cancelled':True},'failed'),
               ({'ok':True,'state':'running'},'pending'),
               ({'ok':False,'uncertain':True},'uncertain')]
        for value,state in cases:
            with self.subTest(value=value):
                result=assess({**value,'complete':False})
                self.assertEqual(result['state'],state)
                self.assertEqual(result['coverage'],'partial')

    def test_partial_page_does_not_block_next_page(self):
        context=ApplicationContext()
        for offset in (0,100,200):
            args={'action':'read','offset':offset}
            context.record_tool_result('reader',args,{'ok':True,'complete':False,'next_offset':offset+100})
            self.assertEqual(context.tool_retry_check('reader',args),'')
        self.assertEqual(context.snapshot()['recent_operations'][-1]['coverage'],'partial')

    def test_partial_evidence_survives_restart_and_plan_summary(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'ledger.json'
            ledger=ExecutionLedger(path)
            plan=ledger.run({'action':'create','title':'Review','steps':['Read the full document']})
            evidence=ledger.record('reader',{'ok':True,'extraction_incomplete':True,'text':'PRIVATE'})
            ledger.run({'action':'attach','id':plan['id'],'step':1,'evidence_id':evidence})
            reopened=ExecutionLedger(path)
            step=reopened.context()['plans'][0]['steps'][0]
            self.assertEqual(step['last_coverage'],'partial')
            self.assertEqual(step['last_outcome'],'tool_reported')
            self.assertNotIn('PRIVATE',path.read_text(encoding='utf-8'))


if __name__=='__main__':unittest.main()
