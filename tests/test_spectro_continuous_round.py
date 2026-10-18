import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock,patch
import numpy as np
from core.voice_interrupt import VoiceInterruptGate
from core.spectro_store import SpectroStore
from core.spectro_observer import Observer
from core.task_execution import ExecutionLedger
from core.spectro_commands import request
from test_spectro import SpectroTests


class VoiceContinuity(unittest.TestCase):
    def test_natural_pauses_preserve_voice_evidence(self):
        vad=Mock();gate=VoiceInterruptGate(vad);pcm=np.full(1024,800,dtype=np.int16)
        accepted=None
        for i in range(12):
            speaking=i%4!=3;vad.is_speech.return_value=speaking
            accepted=gate.feed(pcm,16000,.3 if speaking else .01,True)
            if accepted:break
        self.assertIsNotNone(accepted)
        self.assertGreater(len(accepted),5)

    def test_separated_clicks_never_accumulate(self):
        vad=Mock();gate=VoiceInterruptGate(vad);pcm=np.ones(1024,dtype=np.int16)
        for i in range(100):
            speaking=i%5==0;vad.is_speech.return_value=speaking
            self.assertIsNone(gate.feed(pcm,16000,.3 if speaking else .01,True))


class ContinuousObservation(unittest.TestCase):
    def test_structured_notes_keep_values_errors_and_empty_results(self):
        from core.spectro_summary import summary
        self.assertIn('0 C',summary({'kind':'weather','temperature':0,'condition':'Frio'}))
        self.assertIn('offline',summary({'kind':'weather','error':'offline'}))
        self.assertIn('Nenhum item',summary({'kind':'tasks','items':[]}))
        self.assertIn('Revisar',summary({'kind':'tasks','items':[{'title':'Revisar'}]}))
        self.assertLessEqual(len(summary({'text':'A'*10000})),220)

    def test_privacy_stops_even_when_disk_fails(self):
        with tempfile.TemporaryDirectory() as folder:
            observer=Observer(SpectroStore(Path(folder)/'state.json'),automatic=True)
            observer.current={'ok':True};generation=observer.generation
            with patch.object(observer.store,'update',side_effect=OSError('disk')):observer.privacy()
            self.assertFalse(observer.enabled);self.assertEqual(observer.current,{})
            self.assertGreater(observer.generation,generation);observer.close()

    def test_all_plans_remain_discoverable(self):
        ledger=ExecutionLedger()
        ids=[ledger.run({'action':'create','title':str(i),'steps':['Consultar']})['id'] for i in range(20)]
        self.assertEqual([p['id'] for p in ledger.run({'action':'list'})['plans']],ids)
        self.assertEqual(len(ledger.context()['plans']),3)

    def test_privacy_survives_restart_and_close_is_not_privacy(self):
        with tempfile.TemporaryDirectory() as folder:
            store=SpectroStore(Path(folder)/'state.json')
            observer=Observer(store,automatic=True)
            self.assertTrue(observer.enabled);self.assertEqual(observer.permissions(),{'*'})
            observer.close()
            observer=Observer(store,automatic=True);self.assertTrue(observer.enabled)
            observer.privacy();observer.close()
            observer=Observer(store,automatic=True);self.assertFalse(observer.enabled)
            observer.resume();observer.close()
            observer=Observer(store,automatic=True);self.assertTrue(observer.enabled);observer.close()

    def test_observation_commands_work_outside_espectro(self):
        self.assertEqual(request('pare de observar',False),('privacy',{}))
        self.assertEqual(request('volte a observar',False),('resume_observation',{}))
        self.assertEqual(request('o que voce esta vendo',False),('context',{}))

    def test_failure_and_checkpoint_recoverable_without_claiming_success(self):
        ledger=ExecutionLedger();plan=ledger.run({'action':'create','title':'Trabalho','steps':['Ler','Alterar','Verificar']})
        evidence=ledger.record('fixture',{'ok':False,'error':'Falha real'})
        ledger.run({'action':'attach','id':plan['id'],'step':2,'evidence_id':evidence})
        result=ledger.run({'action':'checkpoint','id':plan['id'],'step':2,'note':'Consultar destino antes de tentar outra vez'})
        self.assertEqual(result['steps'][1]['last_outcome'],'failed')
        self.assertEqual(ledger.context()['plans'][0]['current_step'],2)
        self.assertNotIn('completed',result)
        for _ in range(130):ledger.record('fixture',{'ok':True})
        result=ledger.run({'action':'read','id':plan['id']})
        self.assertTrue(result['steps'][1]['evidence_expired'])
        self.assertEqual(result['steps'][1]['last_outcome'],'unverified')


class DesktopContinuity(SpectroTests):
    def test_freehand_drawing_is_bounded_and_clickthrough(self):
        self.start()
        marks=self.controller.annotations
        marks.draw([[.1,.2],[.2,.3],[.4,.1]],'verde','Este ponto')
        self.app.processEvents()
        snapshot=marks.snapshot()
        self.assertEqual(snapshot['count'],1);self.assertTrue(snapshot['click_through'])
        self.assertEqual(snapshot['items'][0]['shape'],'path')
        self.assertEqual(len(snapshot['items'][0]['points']),3)
        for points in ([[0,0]],[[0,0],[float('nan'),1]],[[0,0],[2,1]],[[0,0]]*33):
            with self.assertRaises(ValueError):marks.draw(points)
        self.assertEqual(marks.snapshot()['count'],1)

    def test_exit_preserves_observation_and_privacy_works_in_base(self):
        self.start();observer=self.controller.observer
        self.controller.apply('exit',{})
        self.assertIs(self.controller.observer,observer)
        self.assertTrue(observer.enabled)
        self.controller.apply('privacy',{})
        self.assertFalse(observer.enabled)
        self.controller.apply('resume_observation',{})
        self.assertTrue(observer.enabled)

    def test_all_new_shapes_render_with_requested_color(self):
        from core.spectro_annotations import AnnotationWindow,annotation_color
        from PyQt6.QtCore import QRect
        self.start();window=self.controller.window
        for shape in ('marker','underline','cross','circle','arrow'):
            layer=AnnotationWindow(window.screen(),window)
            try:
                layer.present(QRect(20,20,100,50),'Destaque',shape,'amarelo')
                self.app.processEvents()
                image=layer.grab().toImage()
                self.assertFalse(image.isNull());self.assertEqual(layer.color,'#ffe45c')
            finally:layer.close();layer.deleteLater()
        with self.assertRaises(ValueError):annotation_color('invalid')


if __name__=='__main__':unittest.main()
