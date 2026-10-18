import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import time
import unittest
from concurrent.futures import Future
from types import SimpleNamespace
from unittest.mock import Mock,patch
from PyQt6.QtCore import QRect,QPropertyAnimation
import test_spectro as presence
from core.spectro_observer import Observer
from core.spectro_commands import request


class PresenceReinforcement(unittest.TestCase):
    setUpClass=classmethod(presence.SpectroTests.setUpClass.__func__)
    setUp=presence.SpectroTests.setUp
    tearDown=presence.SpectroTests.tearDown
    start=presence.SpectroTests.start

    def test_repeated_resize_uses_requested_destination_not_intermediate_frame(self):
        self.start();window=self.controller.window;self.owner.hud.motion_reduced=False
        width=window.width()
        self.controller.apply('scale',{'factor':.8})
        self.controller.apply('scale',{'factor':.8})
        self.assertEqual(window._animation.endValue().width(),max(140,round(round(width*.8)*.8)))

    def test_position_during_resize_keeps_target_size(self):
        self.start();window=self.controller.window;self.owner.hud.motion_reduced=False
        self.controller.apply('scale',{'size':200})
        self.controller.apply('position',{'dx':-60})
        self.assertEqual(window._animation.endValue().width(),200)

    def test_repeated_transparency_uses_requested_destination(self):
        self.start();window=self.controller.window;self.owner.hud.motion_reduced=False
        initial=window.windowOpacity()
        self.controller.apply('opacity',{'delta':-.1});self.controller.apply('opacity',{'delta':-.1})
        self.assertAlmostEqual(window._opacity_animation.endValue(),initial-.2,places=2)

    def test_exit_flushes_unsaved_destination_preference(self):
        self.start();self.controller.store.save=Mock();self.owner.hud.motion_reduced=False
        self.controller.apply('scale',{'size':190});self.controller.apply('exit',{})
        self.controller.store.save.assert_called_once()
        self.assertEqual(self.controller.store.save.call_args.args[1]['size'],190)

    def test_duplicate_ready_does_not_replace_live_observer(self):
        self.start();observer=self.controller.observer
        observer.enabled=True
        self.controller.window.view.ready.emit()
        self.assertIs(self.controller.observer,observer)
        self.assertTrue(observer.enabled)

    def test_note_cancels_old_target_and_queued_target_results(self):
        self.start();observer=self.controller.observer;observer.enabled=True
        observer.target='old';observer.target_result={'rect':[20,20,60,30]}
        epoch=observer.generation;self.controller.annotations=Mock()
        self.controller.apply('note',{'text':'Nova nota'})
        self.assertIsNone(observer.target);self.assertIsNone(observer.target_result)
        self.assertGreater(observer.generation,epoch)

    def test_snapshot_exposes_animation_destination_and_marking_state(self):
        self.start();self.owner.hud.motion_reduced=False
        self.controller.apply('scale',{'size':210})
        state=self.controller.snapshot()
        self.assertTrue(state['transition']['active'])
        self.assertEqual(state['transition']['bounds']['width'],210)
        self.assertEqual(state['marking']['state'],'idle')

    def test_ambient_microphone_does_not_override_processing_phase(self):
        self.start();self.owner.hud.state='THINKING';self.owner.hud._amp_disp=.6
        self.controller.window.sync()
        self.assertEqual(self.controller.window.view.sync.call_args.args[0]['phase'],'thinking')

    def test_annotation_text_stays_inside_small_monitor_and_uses_current_theme(self):
        from core.spectro_annotations import AnnotationWindow
        self.start();self.owner._spectro_color=lambda:'#ff4050'
        layer=AnnotationWindow(self.controller.window.screen(),self.controller.window)
        try:
            layer.setGeometry(QRect(0,0,240,250));layer.present(QRect(200,225,30,20),'Explicacao longa sobre um elemento real '*5)
            self.assertTrue(layer.rect().contains(layer.label_rect()))
            image=layer.grab().toImage()
            pixels=[image.pixelColor(x,y) for y in range(0,image.height(),3) for x in range(0,image.width(),3)]
            self.assertTrue(any(color.alpha()>30 and color.red()>color.blue()*1.3 for color in pixels))
        finally:layer.close();layer.deleteLater()

    def test_suggestion_opt_in_survives_polite_prefix_normalization(self):
        self.assertEqual(request('pode dar sugestoes por favor',True),('quiet',{'enabled':False}))

    def test_burst_of_adjustments_stays_bounded_and_keeps_one_renderer(self):
        self.start();window=self.controller.window;self.owner.hud.motion_reduced=False
        self.controller.apply('scale',{'factor':1e308})
        for index in range(100):
            self.controller.apply('scale',{'factor':.8 if index%2 else 1.25})
            self.controller.apply('opacity',{'delta':-.08 if index%2 else .08})
            self.controller.apply('position',{'dx':-60 if index%2 else 60,'dy':30})
            self.assertTrue(window.screen().availableGeometry().contains(window.destination_rect()))
            self.assertGreaterEqual(window.destination_opacity(),.18)
            self.assertLessEqual(window.destination_opacity(),1)
        self.assertIs(self.controller.window,window)

    def test_repeated_monitor_switches_start_from_requested_screen(self):
        self.start();window=self.controller.window;self.owner.hud.motion_reduced=False
        screens=[Mock() for _ in range(3)]
        for index,screen in enumerate(screens):
            screen.availableGeometry.return_value=QRect(index*1000,0,1000,800)
        window.setGeometry(QRect(100,100,200,200))
        def at(point):return screens[max(0,min(2,point.x()//1000))]
        with patch('core.spectro.QGuiApplication.screens',return_value=screens), \
             patch('core.spectro.QGuiApplication.screenAt',side_effect=at):
            self.controller.apply('position',{'anchor':'next_monitor'})
            self.controller.apply('position',{'anchor':'next_monitor'})
        self.assertTrue(screens[2].availableGeometry().contains(window.destination_rect()))


class ObserverReinforcement(unittest.TestCase):
    def setUp(self):
        store=Mock();store.read.return_value={'allowed_apps':['fixture.exe']}
        self.observer=Observer(store,clock=Mock(return_value=10))
        self.observer.enabled=True;self.observer.pool=Mock();self.observer.pool.submit.return_value=Future()
        self.addCleanup(self.observer.close)

    def test_window_change_forgets_target_instead_of_reappearing_on_return(self):
        observer=self.observer;observer.target='old';observer.target_result={'rect':[1,2,3,4]}
        observer.current={'ok':True,'handle':1,'process_id':2,'observed_at':time.time()}
        with patch('core.spectro_perception.foreground',return_value={'ok':True,'handle':9,'process_id':3}):
            self.assertFalse(observer.context()['ok'])
        self.assertIsNone(observer.target);self.assertTrue(observer.target_lost)

    def test_target_tracking_does_not_rescan_full_window_between_refreshes(self):
        observer=self.observer;observer.at=9.5;observer.target='target'
        observer.current={'ok':True,'app':'fixture.exe','handle':1,'process_id':2,'observed_at':time.time()}
        observer.poll()
        observer.pool.submit.assert_called_once()
        callback=observer.pool.submit.call_args.args[0]
        with patch('core.spectro_perception.inspect_foreground') as inspect, \
             patch('core.spectro_perception.target_rect',return_value={'rect':[1,2,30,40]}) as target:
            result=callback()
        inspect.assert_not_called();target.assert_called_once()
        self.assertEqual(result['target']['rect'],[1,2,30,40])

    def test_cleared_target_cannot_return_from_old_running_work(self):
        observer=self.observer;observer.target='old';generation=observer.generation
        pending=Future();pending.set_running_or_notify_cancel();observer.pending=pending
        observer.clear_target()
        pending.set_result({'generation':generation,'target':{'rect':[1,2,30,40]}})
        observer.poll()
        self.assertIsNone(observer.target);self.assertIsNone(observer.target_result)

    def test_tracking_failure_keeps_lost_status_available_for_inspection(self):
        observer=self.observer;observer.target='old'
        observer.current={'ok':True,'app':'fixture.exe','observed_at':time.time()}
        pending=Future();pending.set_result({'generation':observer.generation,'target':None});observer.pending=pending
        observer.poll()
        self.assertIsNone(observer.target)
        self.assertTrue(observer.target_error);self.assertTrue(observer.target_lost)

    def test_bounded_control_walk_does_not_eagerly_enumerate_tree(self):
        from core.spectro_perception import bounded_controls
        control=Mock();control.element_info.element.CurrentIsPassword=False
        seen=[]
        def items():
            for index in range(10000):
                seen.append(index)
                yield control
        window=Mock();window.iter_descendants.side_effect=lambda **_:items()
        for _ in bounded_controls(window,6,lambda:True):break
        self.assertEqual(len(seen),1)
        seen.clear();self.assertEqual(len(list(bounded_controls(window,6,lambda:True,limit=16))),16)
        self.assertEqual(len(seen),16);window.descendants.assert_not_called()

    def test_revoked_walk_never_advances_accessibility_iterator(self):
        from core.spectro_perception import bounded_controls
        window=Mock()
        with self.assertRaises(ValueError):list(bounded_controls(window,4,lambda:False))
        window.iter_descendants.assert_not_called()


class ConsentRouting(unittest.IsolatedAsyncioTestCase):
    owner=presence.SpectroRouting.owner

    async def test_original_consent_is_carried_into_ui_dispatch(self):
        owner=self.owner();owner.ui._win._spectro_controller=SimpleNamespace(active=True)
        initial={'serial':1,'text':'acompanhe este aplicativo','spectro_target':{'ok':True,'handle':1}}
        owner.ui.ultron_user_context=Mock(return_value=initial)
        def dispatch(*args,**kwargs):
            owner.ui.ultron_user_context.return_value={'serial':2,'text':'acompanhe este aplicativo'}
            self.assertEqual(kwargs['user_context'],initial)
            return {'ok':False,'error':'Pedido substituido.'}
        owner.ui.control_interface=Mock(side_effect=dispatch)
        await owner._route_protocol_user('acompanhe este aplicativo')
        owner._speak_protocol.assert_not_awaited()

    async def test_structured_tool_preserves_checked_consent(self):
        import json
        from actions.spectro_control import spectro_control
        context={'serial':7,'text':'acompanhe este aplicativo'}
        player=SimpleNamespace(ultron_user_context=Mock(return_value=context),control_interface=Mock(return_value={'ok':True}))
        self.assertTrue(json.loads(spectro_control({'operation':'observe_current'},player))['ok'])
        self.assertEqual(player.control_interface.call_args.kwargs['user_context'],context)


if __name__=='__main__':unittest.main()
