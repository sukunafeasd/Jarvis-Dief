import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock,patch

from core import resource_store as store,resource_jobs as jobs,confirm
from core import local_resources,file_library,office_resources,resource_backups
from core.task_execution import ExecutionLedger


class ResourceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.patch=patch.object(store,'DATABASE',self.root/'resources.sqlite3');self.patch.start()
    def tearDown(self):
        self.patch.stop();self.temp.cleanup()

    def test_contact_ambiguity_and_persistence(self):
        for name in ('Ana A','Ana B'):
            local_resources.run({'kind':'contact','action':'create','title':name,'aliases':['Ana'],'email':'test@example.com'})
        result=local_resources.run({'kind':'contact','action':'resolve','query':'Ana'})
        self.assertTrue(result['ambiguous']);self.assertEqual(len(result['matches']),2)
        result=local_resources.run({'kind':'contact','action':'resolve','query':'Ana A'})
        self.assertFalse(result['ambiguous'])
        self.assertEqual(store.read('contact',result['selected']['id'])['title'],'Ana A')

    def test_project_and_meeting_have_no_implicit_actions(self):
        parent=local_resources.run({'kind':'project','action':'create','title':'Projeto'})['item']
        child=local_resources.run({'kind':'project','action':'create','title':'Etapa','parent_id':parent['id']})['item']
        result=local_resources.run({'kind':'project','action':'complete','id':child['id']})
        self.assertTrue(result['item']['metadata']['done'])
        meeting=local_resources.run({'kind':'meeting','action':'summarize','title':'Reuniao','text':'Combinado: enviar proposta\nPrazo: sexta'})
        self.assertFalse(meeting['item']['metadata']['tasks_created'])
        with self.assertRaises(ValueError):local_resources.run({'kind':'project','action':'update','id':parent['id'],'parent_id':parent['id']})

    def test_search_index_stale_source_and_duplicates(self):
        a=self.root/'a.txt';a.write_text('Ciencia e estudos',encoding='utf-8')
        b=self.root/'b.txt';b.write_text(a.read_text(),encoding='utf-8')
        result=file_library.run({'action':'search','folder':str(self.root),'query':'ciencia','content':True})
        self.assertEqual(result['total_found'],2)
        result=file_library.run({'action':'duplicates','folder':str(self.root)})
        self.assertEqual(len(result['groups']),1)
        file_library.run({'action':'index','path':str(a)})
        a.write_text('Alterado',encoding='utf-8')
        result=file_library.run({'action':'recall','query':'ciencia'})
        self.assertTrue(result['items'][0]['source_changed'])
        self.assertEqual(result['items'][0]['metadata']['path'],str(a))

    def test_file_credentials_and_root_are_not_scanned(self):
        with self.assertRaises(ValueError):list(file_library.files(self.root.anchor))
        with self.assertRaises(ValueError):file_library.safe_path(self.root/'config/token.bin')
        with self.assertRaises(ValueError):file_library.safe_path('')

    def test_plans_only_accept_recorded_evidence(self):
        ledger=ExecutionLedger()
        plan=ledger.run({'action':'create','title':'Pesquisa','steps':['Inspecionar','Verificar']})
        self.assertFalse(plan['execution_started'])
        with self.assertRaises(ValueError):ledger.run({'action':'attach','id':plan['id'],'step':1,'evidence_id':'invented'})
        evidence=ledger.record('app_control',{'ok':True,'completed':False})
        ledger.run({'action':'attach','id':plan['id'],'step':1,'evidence_id':evidence})
        self.assertEqual(ledger.events[0]['evidence'],'pending')
        self.assertNotIn('completed',ledger.run({'action':'read','id':plan['id']}))
        for _ in range(200):ledger.record('tool',{'ok':True})
        self.assertEqual(len(ledger.events),128)

    def test_job_refuses_without_ui_and_confirmed_result(self):
        with patch.object(confirm,'_show_cb',None):
            result=jobs.request('Acao','Detalhe',lambda: {'ok':True})
            self.assertFalse(result['ok'])
        callbacks=[]
        def gate(key,title,detail,run,on_resolve=None):
            callbacks.extend([run,on_resolve]);return '[CONFIRMATION_PENDING]'
        with patch.object(confirm,'request',side_effect=gate):
            result=jobs.request('Acao','Detalhe',lambda: {'ok':False,'uncertain':True})
        self.assertFalse(result['completed']);callbacks[1](True);callbacks[0]()
        self.assertFalse(jobs.snapshot(result['job_id'])['completed'])

    def test_document_new_destination_and_spreadsheet_formula_literal(self):
        from openpyxl import Workbook,load_workbook
        def gate(title,detail,callback):return callback()
        with patch.object(office_resources,'request',side_effect=gate):
            path=self.root/'sheet.xlsx'
            result=office_resources.run({'action':'spreadsheet','path':str(path),'rows_json':json.dumps([['=SUM(A1:A2)',4],[None,6]])})
            self.assertTrue(result['verified_exists'])
            book=load_workbook(path);self.assertEqual(book.active['A1'].data_type,'s');book.close()
            with self.assertRaises(ValueError):office_resources.run({'action':'document','path':str(path),'text':'teste'})
            text=self.root/'document.txt'
            office_resources.run({'action':'document','path':str(text),'text':'Texto teste'})
            with self.assertRaises(ValueError):office_resources.run({'action':'document','path':str(text),'text':'sobrescrever'})
        result=office_resources.run({'action':'statistics','path':str(self.root/'unused.csv'),'rows_json':'[[4],[6]]'})
        self.assertEqual(result['mean'],5)

    def test_backup_excludes_credentials_and_stages_restore(self):
        (self.root/'memory').mkdir();(self.root/'config').mkdir()
        (self.root/'memory/long_term.json').write_text('{"identity":{}}')
        (self.root/'config/api_keys.json').write_text('{"private":"never-export"}')
        path=self.root/'backup.zip'
        with patch.object(resource_backups,'ROOT',self.root),patch('memory.memory_manager.MEMORY_PATH',self.root/'memory/long_term.json'),patch('memory.config_manager.CONFIG_FILE',self.root/'config/api_keys.json'):resource_backups.create(path)
        result=resource_backups.inspect(path)
        self.assertEqual(result['files'],['memory/long_term.json','preferences.json']);self.assertFalse(result['credentials_included'])
        import zipfile
        with zipfile.ZipFile(path) as archive:self.assertEqual(json.loads(archive.read('preferences.json')),{})
        restored=resource_backups.restore_to_folder(path,self.root/'recovery')
        self.assertFalse(restored['live_data_replaced'])
        import zipfile
        bad=self.root/'bad.zip'
        with zipfile.ZipFile(bad,'w') as archive:archive.writestr('../evil','text');archive.writestr('manifest.json','{}')
        with self.assertRaises(ValueError):resource_backups.inspect(bad)

    def test_plugin_discovery_and_json_contracts(self):
        from core.plugin_loader import discover_plugins
        registry=discover_plugins(Path(__file__).resolve().parents[1]/'plugins',set(),logger=lambda _:None)
        for name in ('local_resources','file_library','office_resources','task_execution','resource_backups'):
            self.assertTrue(registry.has(name),name)
            result=json.loads(registry.run(name,{'action':'history' if name=='task_execution' else 'status'}))
            self.assertTrue(result['ok'],name)

    def test_provided_calendar_never_claims_full_availability(self):
        from plugins.calendar_planning import execute
        events=[{'summary':'A','start':{'dateTime':'2026-10-12T10:00:00-03:00'},'end':{'dateTime':'2026-10-12T12:00:00-03:00'}},
                {'summary':'B','start':{'dateTime':'2026-10-12T11:00:00-03:00'},'end':{'dateTime':'2026-10-12T13:00:00-03:00'}}]
        result=execute({'source':'provided','start':'2026-10-12T09:00:00-03:00','end':'2026-10-12T15:00:00-03:00','events_json':json.dumps(events)})
        self.assertFalse(result['availability_confirmed']);self.assertEqual(len(result['conflicts']),1)
        self.assertEqual(len(result['free_intervals']),2)

    def test_diagnostics_never_installs_without_human_confirmation(self):
        from plugins.resource_diagnostics import execute
        with patch('core.startup.missing_dependencies',return_value=['missing-example-package']),patch('subprocess.run') as process,patch.object(confirm,'_show_cb',None):
            result=execute({'action':'repair_dependencies'})
        self.assertFalse(result['ok']);process.assert_not_called()

    def test_update_checker_does_not_install_or_claim_newer_version(self):
        from plugins.resource_updates import execute
        import urllib.error
        with patch('plugins.resource_updates.latest_release',side_effect=urllib.error.HTTPError('url',404,'missing',{},None)):
            result=execute({'action':'check'})
        self.assertFalse(result['installed']);self.assertFalse(result['update_available'])
