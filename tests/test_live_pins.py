import json
import queue
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from core.live_pins import LivePins, specification, fetch


class LivePinTests(unittest.TestCase):
    def test_wrong_source_kind_is_reported_as_stale_instead_of_silent_success(self):
        out=queue.Queue();clock=[0.]
        live=LivePins(out.put,loader=lambda _:{'kind':'news','items':[]},clock=lambda:clock[0])
        previews={'weather':{'live_token':'one','data':{'kind':'weather','city':'Recife'}}}
        try:
            live.tick(previews);result=out.get(timeout=2)
            self.assertTrue(result['error']);self.assertIsNone(result['model'])
            self.assertTrue(live.accept(result,previews))
            clock[0]=119;live.tick(previews);self.assertTrue(out.empty())
            clock[0]=120;live.tick(previews);self.assertTrue(out.get(timeout=2)['error'])
        finally:live.close()

    def test_search_refresh_uses_real_text_contract_and_readonly_capture(self):
        from actions import web_search
        params={'query':'temperatura do oceano','mode':'research'}
        def answer(parameters,player=None):
            self.assertEqual(parameters,params)
            player.write_log('Pesquisa em andamento')
            player.show_manifestation({'kind':'data','title':'PESQUISA','text':'Dados verificados'})
            return 'Dados verificados'
        with patch.object(web_search,'web_search',side_effect=answer):
            result=fetch({'provider':'search','parameters':params})
        self.assertEqual(result['text'],'Dados verificados')

    def test_failed_search_refresh_is_not_a_successful_empty_card(self):
        with patch('actions.web_search.web_search',return_value='Nenhum resultado para a pesquisa'):
            with self.assertRaises(ValueError):fetch({'provider':'search','parameters':{'query':'teste'}})

    def test_only_readonly_operations_are_eligible(self):
        for provider,kind,action in [('organizer','tasks','delete'),('gmail','gmail','disconnect'),
                                     ('whatsapp','whatsapp','read_chat'),('google_calendar','calendar','create')]:
            self.assertIsNone(specification({'kind':kind,'refresh':{'provider':provider,'parameters':{'action':action,'domain':kind}}}))
        self.assertIsNone(specification({'kind':'weather','refresh':{'provider':[]}}))
        self.assertIsNone(specification({'kind':'files','text':'Snapshot without a refreshable query'}))
        self.assertEqual(specification({'kind':'search','refresh':{'provider':'search','parameters':{'query':'clima espacial','mode':'search'}}})['parameters']['query'],'clima espacial')

    def test_timer_uses_real_sources_and_ignores_removed_or_replaced_pin(self):
        out=queue.Queue();clock=[0.]
        live=LivePins(out.put,loader=lambda spec:{'kind':'system','cpu_percent':21},clock=lambda:clock[0])
        previews={'system':{'live_token':'one','data':{'kind':'system'}}}
        live.tick(previews);result=out.get(timeout=2)
        self.assertEqual(result['model']['cpu_percent'],21)
        self.assertTrue(live.accept(result,previews))
        live.tick(previews);self.assertTrue(out.empty())
        clock[0]=1.;live.tick(previews);result=out.get(timeout=2)
        previews['system']['live_token']='replacement'
        self.assertFalse(live.accept(result,previews))
        live.tick(previews);result=out.get(timeout=2)
        previews.clear()
        self.assertFalse(live.accept(result,previews))
        live.close()

    def test_failure_backs_off_and_keeps_last_data(self):
        out=queue.Queue();clock=[0.]
        def fail(_):raise OSError('offline')
        live=LivePins(out.put,loader=fail,clock=lambda:clock[0])
        previous={'kind':'system','cpu_percent':20}
        previews={'system':{'live_token':'one','data':previous}}
        live.tick(previews);result=out.get(timeout=2)
        self.assertTrue(live.accept(result,previews))
        self.assertIsNone(result['model']);self.assertTrue(result['error'])
        self.assertEqual(previews['system']['data'],previous)
        clock[0]=1.;live.tick(previews);self.assertTrue(out.empty())
        live.close()

    def test_local_query_filters_and_changes_remain_live(self):
        from actions import organizer
        with tempfile.TemporaryDirectory() as folder,patch.object(organizer,'DATABASE',Path(folder)/'tasks.db'):
            organizer.organizer_action({'domain':'tasks','action':'create','title':'Projeto Alfa'})
            organizer.organizer_action({'domain':'tasks','action':'create','title':'Outro projeto'})
            model=json.loads(organizer.organizer_action({'domain':'tasks','action':'list','query':'Alfa'}))['data']
            spec=specification(model)
            self.assertEqual(spec['parameters']['query'],'Alfa')
            identifier=model['items'][0]['id']
            organizer.organizer_action({'domain':'tasks','action':'complete','id':identifier})
            latest=fetch(spec)
            self.assertEqual(latest['count'],0)
            self.assertEqual(latest['items'],[])

    def test_slow_provider_cannot_flood_jobs_and_close_drops_late_result(self):
        out=queue.Queue();release=threading.Event();started=threading.Event()
        def slow(_):started.set();release.wait(2);return {'kind':'weather'}
        live=LivePins(out.put,loader=slow)
        previews={'weather':{'live_token':'one','data':{'kind':'weather','city':'Recife'}}}
        live.tick(previews);self.assertTrue(started.wait(1))
        for _ in range(10):live.tick(previews)
        self.assertEqual(len(live.pending),1)
        live.close();release.set()

    def test_replacing_a_blocked_city_does_not_wait_for_old_request(self):
        out=queue.Queue();release=threading.Event();started=threading.Event()
        def load(spec):
            city=spec['parameters']['city']
            if city=='Recife':started.set();release.wait(2)
            return {'kind':'weather','city':city}
        live=LivePins(out.put,loader=load)
        previews={'weather':{'live_token':'old','data':{'kind':'weather','city':'Recife'}}}
        try:
            live.tick(previews);self.assertTrue(started.wait(1))
            previews['weather']={'live_token':'new','data':{'kind':'weather','city':'Manaus'}}
            live.tick(previews);result=out.get(timeout=1)
            self.assertEqual(result['model']['city'],'Manaus')
            self.assertTrue(live.accept(result,previews))
        finally:live.close();release.set()

    def test_timeout_marks_stale_without_creating_unbounded_workers(self):
        out=queue.Queue();release=threading.Event();clock=[0.]
        def load(_):release.wait(2);return {'kind':'system'}
        live=LivePins(out.put,loader=load,clock=lambda:clock[0])
        previews={'system':{'live_token':'same','data':{'kind':'system'}}}
        try:
            live.tick(previews);clock[0]=31;live.tick(previews)
            timeout=out.get(timeout=1)
            self.assertTrue(timeout['timeout'])
            self.assertTrue(live.accept(timeout,previews))
            for _ in range(10):clock[0]+=30;live.tick(previews)
            self.assertEqual(len(live.workers),1)
        finally:live.close();release.set()

