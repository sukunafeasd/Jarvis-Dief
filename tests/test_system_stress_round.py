"""Deterministic load/chaos checks; no providers, shell operations or live data."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import json
import queue
import random
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch
from core.bounded_work import BoundedWork
from core.connection_states import ConnectionChecks
from core.environment_director import EnvironmentDirector
from core.live_pins import LivePins
from core.pin_layout import arrange
from core.presentation_clock import PresentationClock
from core.task_execution import ExecutionLedger


class SystemStressTests(unittest.TestCase):
    def test_pool_saturation_and_shutdown_resolve_all_futures(self):
        gate=threading.Event();entered=threading.Barrier(4)
        pool=BoundedWork(workers=3,capacity=12,name='StressBounded')
        def blocked():entered.wait(timeout=3);gate.wait(timeout=4);return 7
        running=[pool.submit(blocked) for _ in range(3)]
        try:
            entered.wait(timeout=3)
            queued=[pool.submit(lambda:99) for _ in range(12)]
            for _ in range(1000):
                with self.assertRaises(queue.Full):pool.submit(lambda:99)
            self.assertEqual(len(pool.threads),3)
            pool.close();self.assertTrue(all(f.cancelled() for f in queued))
            with self.assertRaises(RuntimeError):pool.submit(lambda:99)
        finally:gate.set();pool.close()
        self.assertEqual([f.result(timeout=3) for f in running],[7,7,7])
        for thread in pool.threads:thread.join(timeout=2)
        self.assertTrue(all(not thread.is_alive() for thread in pool.threads))

    def test_connection_generations_reject_5000_late_results(self):
        checks=ConnectionChecks()
        for index in range(5000):
            provider='synthetic-'+str(index%8)
            old=checks.begin(provider);self.assertIsNotNone(old)
            self.assertIsNone(checks.begin(provider))
            checks.invalidate(provider);current=checks.begin(provider)
            self.assertFalse(checks.finish(provider,old,'connected','Old result'))
            self.assertTrue(checks.finish(provider,current,'error','Current result'))
            self.assertEqual(checks.get(provider)['state'],'error')
        self.assertEqual(len(checks.records),8)

    def test_cue_queue_is_bounded_and_stops_after_cancel_and_finish(self):
        clock=PresentationClock()
        for index in range(10000):clock.enqueue('Noticia '+str(index))
        self.assertEqual(len(clock.pending),clock.MAX_PENDING)
        self.assertEqual(clock.dropped,10000-clock.MAX_PENDING)
        for invalid in (float('nan'),float('inf'),-1,True,None,'2'):
            self.assertEqual(clock.advance(invalid)['cues'],[])
        clock.cancel();self.assertEqual(clock.advance(100)['cues'],[])
        clock.resume();clock.enqueue('Resposta nova',at=0)
        self.assertEqual(clock.advance(.02)['cues'],['Resposta nova'])
        clock.finish();self.assertEqual(clock.advance(100)['cues'],[])
        self.assertEqual(len(clock.pending),0)

    def test_randomized_six_pin_layouts_stay_inside_and_never_overlap(self):
        rng=random.Random(20261015)
        kinds=('weather','tasks','calendar','gmail','news','system')
        for _ in range(500):
            width=rng.randint(800,2560);height=rng.randint(580,1440)
            entries={kind:{'data':{'kind':kind,'items':[{}]*rng.randrange(8)},
                          'placement':{'x':rng.random(),'y':rng.random(),'width':rng.uniform(.1,.7),'height':rng.uniform(.1,.7)}} for kind in kinds}
            rects=list(arrange(entries,width,height).values())
            self.assertTrue(all(x>=0 and y>=0 and w>0 and h>0 and x+w<=width and y+h<=height for x,y,w,h in rects))
            for i,(x,y,w,h) in enumerate(rects):
                self.assertFalse(any(x<bx+bw and x+w>bx and y<by+bh and y+h>by for bx,by,bw,bh in rects[i+1:]))

    def test_rapid_modes_and_out_of_order_operations_end_consistently(self):
        director=EnvironmentDirector();director.start()
        for index in range(2000):
            director.command(('terra','analise','foco','normal')[index%4])
            director.operation_event('running','first:'+str(index))
            director.operation_event('running','second:'+str(index))
            director.operation_event('completed','first:'+str(index))
            self.assertEqual(director.operation_name,'second')
            director.interrupt()
            self.assertFalse(director.operation_event('completed','second:'+str(index)))
            self.assertLessEqual(len(director._cancelled_operations),64)
            self.assertEqual(director._operations,{})
        director.command('normal');self.assertEqual(director.payload()['mode'],'assistant')

    def test_concurrent_evidence_is_bounded_and_cannot_claim_completion(self):
        ledger=ExecutionLedger()
        with ThreadPoolExecutor(max_workers=12) as executor:
            ids=list(executor.map(lambda i:ledger.record('synthetic',{'ok':True,'completed':False}),range(5000)))
        self.assertEqual(len(set(ids)),5000);self.assertEqual(len(ledger.events),128)
        self.assertEqual({item['evidence'] for item in ledger.events},{'pending'})
        for _ in range(20):ledger.run({'action':'create','title':'Synthetic','steps':['Verify']})
        with self.assertRaises(ValueError):ledger.run({'action':'create','title':'Overflow','steps':['Verify']})

    def test_personality_and_history_survive_600_concurrent_turns(self):
        from core import personality,conversation_memory
        from memory import memory_manager
        with tempfile.TemporaryDirectory() as folder,patch.object(memory_manager,'MEMORY_PATH',Path(folder)/'memory/long_term.json'):
            with ThreadPoolExecutor(max_workers=8) as executor:
                list(executor.map(lambda i:conversation_memory.observe_user('Conversa sintetica '+str(i),'stress:'+str(i)),range(600)))
            state=personality.snapshot()
            self.assertTrue(state['available']);self.assertEqual(state['turns'],600)
            self.assertEqual(len(state['recent_turns']),64)
            total=0;offset=0
            while True:
                page=conversation_memory.search('sintetica',limit=20,offset=offset);total+=len(page['items'])
                if page['complete']:break
                offset=page['next_offset']
            self.assertEqual(total,600)
            self.assertLess(len(conversation_memory.prompt_context()),4000)

    def test_stalled_pin_queries_never_exhaust_local_telemetry_slot(self):
        gate=threading.Event();results=queue.Queue()
        def loader(spec):
            if spec['provider']!='system':gate.wait(timeout=5)
            return {'kind':'system' if spec['provider']=='system' else 'weather'}
        pins=LivePins(results.put,loader=loader)
        previews={str(i):{'live_token':str(i),'data':{'kind':'weather','city':'Synthetic '+str(i)}} for i in range(6)}
        previews['system']={'live_token':'system','data':{'kind':'system'}}
        try:
            for _ in range(1000):pins.tick(previews)
            self.assertLessEqual(len(pins.workers),4)
            deadline=time.monotonic()+3;found=False
            while time.monotonic()<deadline:
                result=results.get(timeout=3)
                pins.accept(result,previews)
                if result['key']=='system':found=True;break
            self.assertTrue(found)
            self.assertEqual(sum(job['provider']!='system' for job in pins.workers.values()),3)
        finally:gate.set();pins.close()


if __name__=='__main__':unittest.main()
