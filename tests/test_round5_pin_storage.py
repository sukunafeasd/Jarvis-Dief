"""Concurrent encrypted snapshots use disposable storage, never personal pins."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import os
import tempfile
import threading
import unittest
from unittest.mock import patch

from core.pinned_scene_store import PinnedSceneStore


class PinStorageTests(unittest.TestCase):
    def pins(self,title):
        return [{'key':'weather','data':{'kind':'weather','title':title},'slot':0}]

    def test_overlapping_saves_do_not_share_a_temporary_file(self):
        with tempfile.TemporaryDirectory() as folder:
            store=PinnedSceneStore(folder);barrier=threading.Barrier(2)
            original=os.replace;sources=[];lock=threading.Lock()
            def replace(source,target):
                with lock:sources.append(str(source))
                return original(source,target)
            def save(title):
                barrier.wait(timeout=3)
                store.save(self.pins(title))
            with patch('os.replace',side_effect=replace),ThreadPoolExecutor(max_workers=2) as pool:
                futures=[pool.submit(save,title) for title in ('First','Second')]
                for future in futures:future.result(timeout=5)
            self.assertEqual(len(set(sources)),2)
            self.assertIn(store.load(),[self.pins('First'),self.pins('Second')])
            self.assertEqual(list(Path(folder).glob('*.tmp')),[])

    def test_failed_replace_preserves_previous_encrypted_snapshot(self):
        with tempfile.TemporaryDirectory() as folder:
            store=PinnedSceneStore(folder);store.save(self.pins('Original'))
            previous=store.path.read_bytes()
            with patch('os.replace',side_effect=OSError('Synthetic disk failure')):
                with self.assertRaises(OSError):store.save(self.pins('Changed'))
            self.assertEqual(store.path.read_bytes(),previous)
            self.assertEqual(store.load(),self.pins('Original'))
            self.assertEqual(list(Path(folder).glob('*.tmp')),[])

    def test_parallel_writers_and_readers_only_observe_complete_snapshots(self):
        with tempfile.TemporaryDirectory() as folder:
            store=PinnedSceneStore(folder);store.save(self.pins('Seed'))
            def save(index):
                PinnedSceneStore(folder).save(self.pins('Snapshot '+str(index)))
                return PinnedSceneStore(folder).load()
            with ThreadPoolExecutor(max_workers=8) as pool:results=list(pool.map(save,range(120)))
            self.assertEqual(len(results),120)
            self.assertTrue(all(len(pins)==1 and pins[0]['data']['title'].startswith('Snapshot ') for pins in results))
            self.assertEqual(list(Path(folder).glob('*.tmp')),[])

    def test_slots_must_be_real_integers_or_unspecified(self):
        store=PinnedSceneStore('unused')
        for value in (True,False,1.0,'1',[],{}):
            pins=self.pins('Invalid');pins[0]['slot']=value
            with self.subTest(slot=value),self.assertRaises(ValueError):store.validate(pins)
        for value in (None,0,5):
            pins=self.pins('Valid');pins[0]['slot']=value
            self.assertEqual(store.validate(pins),pins)
