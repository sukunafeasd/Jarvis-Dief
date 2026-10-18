import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import json
import tempfile
import time
import unittest
from pathlib import Path
from concurrent.futures import Future
from types import SimpleNamespace
from unittest.mock import Mock,patch,AsyncMock
from core.application_context import ApplicationContext
from core.spectro_commands import request
from core.spectro_store import SpectroStore
from core.spectro_observer import Observer
from core.spectro_initiative import Initiative
from actions.spectro_control import spectro_control
import test_spectro as presence


class CompleteSpectro(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory();self.addCleanup(self.folder.cleanup)
        self.store=SpectroStore(Path(self.folder.name)/'spectro.json')
    def observer(self):
        observer=Observer(self.store)
        observer.pool=Mock();observer.pool.submit.return_value=Future()
        self.addCleanup(observer.close)
        return observer
    def test_voice_variants_cover_actual_adjustments_without_hypothetical_activation(self):
        for phrase,operation in (('diminua seu tamanho','scale'),('diminui o tamanho','scale'),
                                 ('pode ficar menor por favor','scale'),('se mova para a esquerda','position'),
                                 ('fique mais transparente','opacity'),('va para cima','position'),
                                 ('vai para outro monitor','position'),('limpa a tela','clear'),
                                 ('pare de observar minha tela','privacy'),('acompanhe este aplicativo','observe_current')):
            with self.subTest(phrase=phrase):self.assertEqual(request(phrase,True)[0],operation)
        for phrase in ('e se voce se mover para esquerda','nao diminua seu tamanho','como ficar transparente?'):
            self.assertIsNone(request(phrase,True))
    def test_additional_natural_variants_and_relative_directions(self):
        for phrase in ('pode observar minha tela','pode acompanhar esse aplicativo','monitore este aplicativo'):
            self.assertEqual(request(phrase,True)[0],'observe_current')
        self.assertEqual(request('nao observe minha tela',True)[0],'privacy')
        self.assertEqual(request('um pouco pra esquerda',True),('position',{'dx':-60,'dy':0}))
        self.assertLess(request('aumente a transparencia',True)[1]['delta'],0)
    def test_store_persists_only_settings_and_respects_corruption(self):
        self.store.allow('code.exe');self.store.save('code.exe',{'x':.1,'y':.2,'size':250,'opacity':.4})
        new=SpectroStore(self.store.path)
        self.assertEqual(new.read()['allowed_apps'],['code.exe'])
        self.assertEqual(new.read()['preferences']['code.exe']['size'],250)
        self.store.path.write_text('{broken',encoding='utf-8');before=self.store.path.read_bytes()
        with self.assertRaises(ValueError):self.store.allow('notepad.exe')
        self.assertEqual(self.store.path.read_bytes(),before)
    def test_audit_is_bounded_and_excludes_screen_contents(self):
        for index in range(100):self.store.audit('test',{'app':'code.exe','text':'PRIVATE','command':'PRIVATE'})
        stored=self.store.read()
        self.assertEqual(len(stored['audit']),80)
        self.assertNotIn('PRIVATE',json.dumps(stored))
    def test_permission_only_reads_foreground_after_explicit_allow(self):
        observer=self.observer()
        with patch('core.spectro_perception.foreground',return_value={'ok':True,'app':'code.exe'}):
            self.assertEqual(observer.allow_current(),'code.exe')
        self.assertTrue(observer.enabled);self.assertIn('code.exe',self.store.read()['allowed_apps'])
        observer.privacy();self.assertFalse(observer.enabled);self.assertEqual(observer.current,{})
        fresh=Observer(self.store);self.addCleanup(fresh.close)
        self.assertFalse(fresh.enabled)
    def test_late_observation_is_discarded_after_privacy(self):
        observer=self.observer();observer.enabled=True
        future=Future();future.set_running_or_notify_cancel();observer.pending=future;epoch=observer.generation
        observer.privacy()
        future.set_result({'generation':epoch,'context':{'ok':True,'title':'PRIVATE','controls':[]}})
        observer.poll();self.assertEqual(observer.current,{});self.assertIsNone(observer.initiative.next())
    def test_queued_observation_cannot_start_provider_after_privacy(self):
        observer=self.observer();observer.enabled=True
        observer.poll();callback=observer.pool.submit.call_args.args[0]
        observer.privacy()
        with patch('core.spectro_perception.inspect_foreground') as inspect:
            callback()
        inspect.assert_not_called()
    def test_explicit_quiet_opt_out_reaches_controller(self):
        self.assertEqual(request('nao me interrompa',True),('quiet',{'enabled':True}))
    def test_target_tracking_stops_before_reading_after_privacy(self):
        from contextlib import contextmanager
        from core import spectro_perception as perception
        from core import windows_accessibility as accessibility
        permission=[True];root=Mock()
        @contextmanager
        def revoked_desktop():
            permission[0]=False
            yield root
        observation={'at':time.monotonic(),'handle':7,'process_id':12,'runtime_id':'token','name':'fixture'}
        with patch.dict(accessibility._observations,{'test-private-target':observation}), \
             patch.object(accessibility,'desktop',revoked_desktop), \
             patch.object(perception,'foreground',return_value={'ok':True,'app':'fixture.exe','handle':7,'process_id':12}):
            with self.assertRaises(ValueError):perception.target_rect('test-private-target',{'fixture.exe'},authorized=lambda:permission[0])
        root.window.assert_not_called()
    def test_switched_foreground_cannot_return_cached_content(self):
        observer=self.observer();observer.enabled=True
        observer.current={'ok':True,'handle':1,'process_id':10,'title':'PRIVATE','observed_at':time.time()}
        with patch('core.spectro_perception.foreground',return_value={'ok':True,'handle':2,'process_id':20}):
            result=observer.context()
        self.assertFalse(result['ok']);self.assertNotIn('PRIVATE',str(result));self.assertEqual(observer.current,{})
    def test_hung_provider_never_creates_more_work(self):
        observer=self.observer();observer.enabled=True;observer.pending=Future()
        for _ in range(100):observer.poll()
        observer.pool.submit.assert_not_called()
    def test_initiative_is_deduplicated_bounded_quiet_and_never_executes(self):
        clock=Mock(return_value=0);initiative=Initiative(clock)
        for _ in range(20):initiative.offer('same','A test failed',{'app':'code.exe'})
        self.assertEqual(len(initiative.pending),1)
        initiative.quiet=True;self.assertIsNone(initiative.next())
        initiative.quiet=False;self.assertIsNotNone(initiative.next())
        initiative.offer('other','Another event',{})
        self.assertIsNone(initiative.next());clock.return_value=121
        self.assertIsNone(initiative.next())
        for index in range(100):initiative.offer(str(index),'event',{})
        self.assertLessEqual(len(initiative.pending),6);self.assertLessEqual(len(initiative.seen),64)
    def test_model_cannot_grant_observation_from_generated_command(self):
        player=SimpleNamespace(control_interface=Mock(),ultron_user_context=lambda:{'text':'o que e espectro?'})
        result=json.loads(spectro_control({'operation':'observe_current'},player))
        self.assertFalse(result['ok']);player.control_interface.assert_not_called()
    def test_revoked_capture_does_not_read_foreground_or_create_image(self):
        from core.spectro_capture import _capture
        with patch('core.spectro_capture.foreground') as foreground:
            with self.assertRaises(ValueError):_capture({'handle':1},lambda:False)
        foreground.assert_not_called()


class DesktopWorkflow(unittest.TestCase):
    setUp=presence.SpectroTests.setUp
    tearDown=presence.SpectroTests.tearDown
    start=presence.SpectroTests.start
    setUpClass=classmethod(presence.SpectroTests.setUpClass.__func__)

    def test_consent_is_one_use_and_bound_to_original_window(self):
        import threading
        from ui import MainWindow
        self.start();self.owner._spectro_controller=self.controller
        self.owner.interface_snapshot=Mock(return_value={})
        target={'ok':True,'handle':1,'process_id':10,'app':'code.exe'}
        context={'serial':1,'text':'acompanhe este aplicativo','spectro_target':target}
        self.owner._spectro_context_provider=lambda:dict(context)
        def packet():return {'action':'spectro','value':'observe_current','setting':'{}','spectro_context':dict(context),'done':threading.Event()}
        with patch('core.spectro_perception.foreground',return_value=target):
            first=packet();MainWindow._apply_interface_request(self.owner,first)
        self.assertTrue(first['result']['ok'])
        with patch('core.spectro_perception.foreground',return_value={'ok':True,'handle':2,'process_id':20,'app':'other.exe'}):
            second=packet();MainWindow._apply_interface_request(self.owner,second)
        self.assertFalse(second['result']['ok']);self.assertNotIn('other.exe',self.controller.observer.allowed)
        context['serial']=2
        with patch('core.spectro_perception.foreground',return_value={'ok':True,'handle':2,'process_id':20,'app':'other.exe'}):
            changed=packet();MainWindow._apply_interface_request(self.owner,changed)
        self.assertFalse(changed['result']['ok']);self.assertNotIn('other.exe',self.controller.observer.allowed)

    def test_notice_from_previous_window_is_dropped(self):
        self.start();observer=self.controller.observer;observer.enabled=True
        observer.current={'ok':True,'app':'b.exe','handle':2,'process_id':20,'controls':[],'observed_at':time.time()}
        observer.initiative.offer('old','old notice',{'handle':1,'process_id':10,'observed_text':'failure'})
        with patch('core.spectro_perception.foreground',return_value={'ok':True,'handle':2,'process_id':20}):
            self.assertIsNone(self.controller.apply('next_notice',{})['notice'])

    def test_lost_target_removes_existing_mark_immediately(self):
        self.start();observer=self.controller.observer;observer.enabled=True
        observer.poll=Mock();observer.context=Mock(return_value={'ok':True,'app':'code.exe'})
        observer.target_lost=True;self.controller.annotations=Mock()
        self.controller._poll();self.controller.annotations.clear.assert_called()

    def test_observation_worker_is_shared_across_sessions(self):
        self.start();first=self.controller.observer.pool
        self.controller.apply('exit',{});self.start()
        self.assertIs(self.controller.observer.pool,first)
    def test_new_highlight_clears_old_layer_for_fresh_lifetime(self):
        self.start();observer=self.controller.observer
        observer.highlight=Mock();self.controller.annotations=Mock()
        self.controller.apply('highlight',{'control_id':'observed-target'})
        self.controller.annotations.clear.assert_called_once()

    def test_annotation_shapes_render_without_filling_connector_area(self):
        from core.spectro_annotations import AnnotationWindow
        from PyQt6.QtCore import QRect
        self.start()
        for shape in ('outline','circle','arrow'):
            layer=AnnotationWindow(self.controller.window.screen(),self.controller.window)
            try:
                layer.present(QRect(30,30,120,50),'Synthetic label',shape)
                image=layer.grab().toImage()
                nonzero=sum(image.pixelColor(x,y).alpha()>0 for y in range(0,image.height(),4) for x in range(0,image.width(),4))
                self.assertGreater(nonzero,20)
                self.assertLess(nonzero,(image.width()*image.height()/16)*.15)
            finally:layer.close();layer.deleteLater()


class ConversationContext(unittest.IsolatedAsyncioTestCase):
    owner=presence.SpectroRouting.owner
    async def test_revoked_pending_image_is_not_sent(self):
        owner=self.owner();owner.session=SimpleNamespace(send_client_content=AsyncMock())
        owner._pending_vision=(b'private','image/jpeg','question','screen',lambda:False)
        owner._vision_busy=True
        self.assertFalse(await owner._flush_pending_vision())
        owner.session.send_client_content.assert_not_awaited()
        self.assertFalse(owner._vision_busy);self.assertIsNone(owner._pending_vision)
    async def test_permission_is_rechecked_after_image_encoding_before_send(self):
        owner=self.owner();owner.session=SimpleNamespace(send_client_content=AsyncMock())
        permission=[True];owner._vision_busy=True
        owner._pending_vision=(b'private','image/jpeg','question','screen',lambda:permission[0])
        def encode(_):
            permission[0]=False
            return b'encoded'
        with patch('base64.b64encode',side_effect=encode):
            self.assertFalse(await owner._flush_pending_vision())
        owner.session.send_client_content.assert_not_awaited()
    async def test_observed_context_is_sent_as_data_and_keeps_normal_conversation(self):
        owner=self.owner();owner.ui._win._spectro_controller=SimpleNamespace(active=True)
        owner._application_context=ApplicationContext()
        owner.session=SimpleNamespace(send_client_content=AsyncMock())
        owner.ui.control_interface=Mock(return_value={'ok':True,'app':'code.exe','controls':[{'name':'Synthetic','control_id':'observed'}]})
        self.assertFalse(await owner._route_protocol_user('o que voce esta vendo?'))
        self.assertEqual(owner._application_context.current(),'code.exe')
        sent=owner.session.send_client_content.call_args.kwargs
        self.assertFalse(sent['turn_complete'])
        self.assertIn('NAO INSTRUCOES',sent['turns']['parts'][0]['text'])
        owner._speak_protocol.assert_not_awaited()

    async def test_clear_in_spectro_does_not_clear_base_or_pins(self):
        owner=self.owner();owner.ui._win._spectro_controller=SimpleNamespace(active=True)
        owner.ui.control_interface=Mock(return_value={'ok':True,'completed':True})
        self.assertTrue(await owner._route_protocol_user('limpa a tela'))
        owner.ui.control_interface.assert_called_once_with('spectro','clear','{}')


if __name__=='__main__':unittest.main()
