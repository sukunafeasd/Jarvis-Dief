import unittest
from types import SimpleNamespace
from unittest.mock import Mock,patch
from core.forge_controller import ForgeController
import test_scene


class StaleForgeTests(unittest.TestCase):
    def test_delayed_validation_worker_does_not_start_browser_after_exit(self):
        owner=SimpleNamespace(phase='ready',generation=1,_validating=None,_validated_revisions=set(),
            window=SimpleNamespace(_forge_runtime=Mock()),interceptor=SimpleNamespace(preview_port=None),
            view=None,validation_ready=Mock())
        with patch('core.forge_controller.threading.Thread') as thread:
            ForgeController._update(owner,{'phase':'idle','project':{'id':'project'},
                'candidate_revision':'r','candidate_preview_url':'http://127.0.0.1:8001/candidate'})
        worker=thread.call_args.kwargs['target']
        owner.generation=2;owner.phase='normal'
        with patch('core.forge_validation.validate_candidate') as validate:
            worker()
        validate.assert_not_called()
        owner.window._forge_runtime.command.assert_not_called()
        owner.validation_ready.emit.assert_not_called()

    def test_snapshot_after_exit_cannot_mutate_scene_or_start_validation(self):
        token=object();old={'project':{'id':'current'}}
        owner=SimpleNamespace(phase='normal',generation=2,_polling=token,_snapshot=old)
        ForgeController._update(owner,{'poll_token':token,'generation':1,'snapshot':{'project':{'id':'old'},'candidate_revision':'r','candidate_preview_url':'http://127.0.0.1/old'}})
        self.assertIs(owner._snapshot,old)

    def test_old_poll_cannot_release_new_poll_or_replace_new_snapshot(self):
        token=object();old={'project':{'id':'current'}}
        owner=SimpleNamespace(phase='ready',generation=2,_polling=token,_snapshot=old)
        ForgeController._update(owner,{'poll_token':object(),'generation':1,'snapshot':{'project':{'id':'old'}}})
        self.assertIs(owner._polling,token)
        self.assertIs(owner._snapshot,old)

    def test_validation_after_exit_does_not_clear_new_validation(self):
        owner=SimpleNamespace(phase='ready',generation=2,_validating=('new','r','url'))
        ForgeController._validated(owner,{'generation':1,'key':('old','r','url'),'result':{'accepted':True}})
        self.assertEqual(owner._validating,('new','r','url'))


class NativeModeTests(unittest.TestCase):
    setUpClass=classmethod(test_scene.SceneTests.setUpClass.__func__)
    setUp=test_scene.SceneTests.setUp
    tearDown=test_scene.SceneTests.tearDown

    def test_late_refresh_during_forge_never_reopens_loading(self):
        self.window._forge_controller=SimpleNamespace(active=True)
        self.window._daily_refresh_view=Mock()
        self.window._show_manifestation({'kind':'status','refreshTransaction':True,'id':'old','items':[]})
        self.window._daily_refresh_view.update_model.assert_not_called()
        self.assertIsNone(getattr(self.window,'_refresh_lock',None))
        self.window._forge_controller=None

    def test_loading_is_hidden_at_forge_entry_and_not_restored_as_stale(self):
        self.window._show_manifestation({'kind':'status','refreshTransaction':True,'id':'refresh','items':[]})
        view=self.window._daily_refresh_view
        self.assertTrue(view.isVisible())
        widgets=ForgeController._ordinary_widgets(SimpleNamespace(window=self.window))
        self.assertFalse(view.isVisible())
        self.assertNotIn(view,widgets)

    def test_deferred_restore_does_not_read_cache_or_create_pins_in_forge(self):
        self.window._forge_controller=SimpleNamespace(active=True)
        self.window._pins_restored=False
        with patch.object(self.window,'_load_pin_snapshots') as load:
            self.window._restore_saved_pins()
        load.assert_not_called()
        self.window._forge_controller=None

    def test_hidden_and_forge_windows_do_not_start_background_pin_queries(self):
        self.window._ready=True
        with patch.object(self.window._live_pins,'tick') as tick:
            self.window.hide();self.window._tick_live_pins()
            self.window.show();self.window._forge_controller=SimpleNamespace(active=True)
            self.window._tick_live_pins()
            tick.assert_not_called()
        self.window._forge_controller=None

    def test_explicit_focus_displays_text_after_speech_ended(self):
        from core.visual_scene import VisualSceneController
        scene=VisualSceneController(self.window)
        scene.apply({'action':'compose','elements':[{'id':'later','text':'Mensagem fixada','cue':'depois','pinned':True}]})
        scene.clock.advance(.1);scene.finish()
        scene.apply({'action':'focus','id':'later'})
        self.assertEqual(scene.labels['later'].text(),'Mensagem fixada')
        self.assertTrue(scene.clock.finished)
        scene.clear_all();scene.layer.deleteLater()

    def test_update_after_cancel_rebases_to_current_played_audio(self):
        from core.visual_scene import VisualSceneController
        scene=VisualSceneController(self.window)
        scene.apply({'action':'compose','elements':[{'id':'later','text':'Mensagem','cue':'mensagem'}]})
        scene.cancel();self.window._presentation_clock.advance(2.)
        scene.apply({'action':'update','id':'later','text':'Mensagem nova'})
        scene.enqueue({'text':'mensagem','at':2.,'duration':.1})
        scene.advance(.1)
        self.assertTrue(scene.items['later']['revealed'])
        self.assertGreaterEqual(scene.clock.elapsed,2.)
        scene.clear_all();scene.layer.deleteLater()
