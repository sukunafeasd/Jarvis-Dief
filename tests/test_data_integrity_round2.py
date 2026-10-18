"""Real SQLite concurrency with disposable records, never personal storage."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from core import resource_store as store,local_resources


class DataIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        change=patch.object(store,'DATABASE',Path(self.temp.name)/'records.sqlite3')
        change.start();self.addCleanup(change.stop)

    def test_write_locks_before_validating_record_kind_and_capacity(self):
        original=store.connection;statements=[]
        def connection():
            db=original();db.set_trace_callback(statements.append);return db
        with patch.object(store,'connection',side_effect=connection):
            store.put('note','Synthetic',identifier='shared')
        normalized=[line.upper() for line in statements]
        self.assertIn('BEGIN IMMEDIATE',normalized)
        lock=normalized.index('BEGIN IMMEDIATE')
        validation=next(i for i,line in enumerate(normalized) if line.startswith('SELECT KIND'))
        self.assertLess(lock,validation)

    def test_concurrent_shared_ids_cannot_mutate_another_kind(self):
        def save(value):
            kind='note' if value%2 else 'contact'
            try:return store.put(kind,kind,body=kind,identifier='shared-'+str(value//2))
            except ValueError:return None
        with ThreadPoolExecutor(max_workers=8) as pool:results=list(pool.map(save,range(100)))
        self.assertEqual(sum(item is not None for item in results),50)
        for kind in ('note','contact'):
            page=store.search(kind,limit=100,full=True)
            self.assertTrue(all(item['title']==kind and item['body']==kind for item in page['items']))

    def test_project_cannot_move_under_its_own_descendant(self):
        a=local_resources.run({'kind':'project','action':'create','title':'Root'})['item']
        b=local_resources.run({'kind':'project','action':'create','title':'Child','parent_id':a['id']})['item']
        c=local_resources.run({'kind':'project','action':'create','title':'Leaf','parent_id':b['id']})['item']
        with self.assertRaises(ValueError):
            local_resources.run({'kind':'project','action':'update','id':a['id'],'parent_id':c['id']})
        self.assertNotIn('parent_id',store.read('project',a['id'])['metadata'])

    def test_parallel_project_parent_changes_cannot_form_a_cycle(self):
        a=store.put('project','A');b=store.put('project','B')
        def move(pair):
            child,parent=pair
            try:store.put('project',child['title'],metadata={'parent_id':parent['id']},identifier=child['id']);return True
            except ValueError:return False
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(move,[(a,b),(b,a)]))
        self.assertEqual(sum(results),1)

    def test_invalid_metadata_does_not_change_saved_record(self):
        record=store.put('note','Original',identifier='existing')
        for metadata in ([1],42,'bad'):
            with self.assertRaises(ValueError):store.put('note','Changed',metadata=metadata,identifier='existing')
            self.assertEqual(store.read('note','existing'),record)


if __name__=='__main__':unittest.main()
