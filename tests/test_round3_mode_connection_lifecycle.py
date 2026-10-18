"""Mode recovery and opt-out regressions; no accounts, GPU or Windows commands."""
import asyncio
import queue
import threading
import time
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock,patch
from core.live_pins import LivePins,fetch
from core.connection_verifier import saved_checks,ConnectionVerifier


class DisabledConnectionTests(unittest.TestCase):
    def preview(self):
        return {'gmail':{'live_token':'one','data':{'kind':'gmail','refresh':{'provider':'gmail','parameters':{'action':'list'}}}}}

    def test_disabled_pin_result_is_discarded_and_reenable_refreshes_immediately(self):
        out=queue.Queue();live=LivePins(out.put,loader=lambda _:{'kind':'gmail','items':[]});previews=self.preview()
        with patch('memory.config_manager.get_plugin_enabled',return_value=True):
            live.tick(previews);result=out.get(timeout=2)
        with patch('memory.config_manager.get_plugin_enabled',return_value=False):
            self.assertFalse(live.accept(result,previews));live.tick(previews);self.assertTrue(out.empty())
        with patch('memory.config_manager.get_plugin_enabled',return_value=True):
            live.tick(previews);self.assertTrue(live.accept(out.get(timeout=2),previews))
        live.close()

    def test_disable_while_fetching_rejects_the_returned_account_data(self):
        spec={'provider':'gmail','parameters':{'action':'list'}}
        allowed=[True]
        def listing(_,player=None):
            player.show_manifestation({'kind':'gmail','items':[]});allowed[0]=False
            return {'ok':True}
        with patch('memory.config_manager.get_plugin_enabled',side_effect=lambda _:allowed[0]),patch('plugins.gmail_control.run',side_effect=listing):
            with self.assertRaisesRegex(ValueError,'desativada'):fetch(spec)

    def test_saved_inventory_does_not_even_inspect_disabled_special_accounts(self):
        plugins=[{'name':name,'valid':True,'enabled':False} for name in ('gmail_control','whatsapp_web')]
        with patch('core.gmail_connection.status') as status,patch('core.whatsapp_web.PROFILE') as profile,patch('memory.config_manager.get_plugin_enabled',return_value=True):
            self.assertEqual(list(saved_checks(plugins)),[])
            status.assert_not_called();profile.exists.assert_not_called()

    def test_queued_special_check_rechecks_current_optout(self):
        allowed=[True]
        with patch('memory.config_manager.get_plugin_enabled',side_effect=lambda _:allowed[0]),patch('core.gmail_connection.status',return_value={'connected':True}),patch('core.gmail_connection.verify') as verify,patch('core.whatsapp_web.PROFILE') as profile:
            profile.exists.return_value=False
            _,callback=next(saved_checks([]));allowed[0]=False
            self.assertEqual(callback()['state'],'disabled');verify.assert_not_called()

    def test_verifier_rechecks_optout_before_and_after_the_callback(self):
        for initial in (False,True):
            allowed=[initial];finished=threading.Event();verifier=ConnectionVerifier()
            original=verifier.checks.finish
            def finish(*args):
                value=original(*args);finished.set();return value
            verifier.checks.finish=finish
            def callback():allowed[0]=False;return True,'Validacao sintetica'
            checked=Mock(side_effect=callback)
            with patch('memory.config_manager.get_plugin_enabled',side_effect=lambda _:allowed[0]):
                verifier.submit('google_drive',checked);self.assertTrue(finished.wait(2))
            self.assertEqual(verifier.checks.get('google_drive')['state'],'disabled')
            self.assertEqual(checked.call_count,int(initial))


class ModeRecoveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_renderer_failure_restores_routing_but_cannot_reset_a_new_entry(self):
        from main import JarvisLive
        owner=JarvisLive.__new__(JarvisLive);owner._loop=asyncio.get_running_loop();owner._forge_mode=True
        controller=NS(active=False,generation=4);owner.ui=NS(_win=NS(_forge_controller=controller))
        owner._on_forge_scene_failure(4);await asyncio.sleep(0)
        self.assertFalse(owner._forge_mode)
        owner._forge_mode=True;owner._on_forge_scene_failure(4)
        controller.active=True;controller.generation=5
        await asyncio.sleep(0);self.assertTrue(owner._forge_mode)

    async def test_forja_entry_cancels_memory_before_taking_over_the_core(self):
        from core.forge_controller import ForgeController
        owner=Mock();owner.active=False;owner.generation=0;owner.window._ready=True
        owner._ordinary_widgets.return_value=[]
        owner.window._scene_animations=[]
        owner._take_core.side_effect=lambda:owner.window._cancel_neural_memory.assert_called_once()
        ForgeController.request(owner,{'action':'enter'})
        owner._take_core.assert_called_once()

    async def test_controller_failure_notifies_the_assistant_with_restored_generation(self):
        from core.forge_controller import ForgeController
        owner=Mock();owner._request={'done':Mock()};owner.generation=3
        def restore():owner.generation=4
        owner._restore.side_effect=restore
        ForgeController._fail(owner,'Falha sintetica')
        owner.window.on_forge_scene_failure.assert_called_once_with(4)

    async def test_failed_view_is_reloaded_without_recreating_the_project(self):
        from core.forge_controller import ForgeController
        owner=NS(view=Mock(),_view_failed=True,_command_serial=7)
        ForgeController._create_view(owner)
        owner.view.load.assert_called_once();self.assertFalse(owner._view_failed)
        self.assertEqual(owner._command_serial,-1)
        ForgeController._create_view(owner);owner.view.load.assert_called_once()

    async def test_hidden_renderer_failure_does_not_rearrange_the_normal_interface(self):
        from core.forge_controller import ForgeController
        owner=NS(active=False,_view_failed=False,_fail=Mock())
        ForgeController._renderer_failed(owner)
        self.assertTrue(owner._view_failed);owner._fail.assert_not_called()

    async def test_camera_waits_for_neural_return_and_ignores_old_completion(self):
        from core.forge_controller import ForgeController
        core=Mock();owner=NS(generation=1,phase='preparing',window=NS(hud=NS(_spatial_core=core,motion_reduced=False),_space_view=None),_take_core=Mock())
        owner._start_travel=lambda settled,token:ForgeController._start_travel(owner,settled,token)
        ForgeController._begin_travel(owner,True,1)
        callback=core.page().runJavaScript.call_args.args[1]
        callback(False);self.assertEqual(owner.phase,'preparing');owner._take_core.assert_not_called()
        callback(True);self.assertEqual(owner.phase,'travelling');owner._take_core.assert_called_once()
        owner.phase='preparing';owner.generation=2
        callback(True);self.assertEqual(owner.phase,'preparing')


class NeuralCompletionTests(unittest.TestCase):
    def test_health_releases_only_the_matching_finished_request(self):
        from core.spatial_view import SpatialCoreView
        view=NS(_alive=lambda:True,failed=False,_loaded=True,_ready=True,_created=time.monotonic(),
                _neural_payload={'requestId':'new','active':True},neural_finished=Mock())
        SpatialCoreView._health_result(view,{'ready':True,'neural':{'requestId':'old','active':False}})
        view.neural_finished.emit.assert_not_called()
        SpatialCoreView._health_result(view,{'ready':True,'neural':{'requestId':'new','active':False}})
        self.assertIsNone(view._neural_payload);view.neural_finished.emit.assert_called_once_with('new')

    def test_finished_memory_releases_the_gate_for_the_next_projection(self):
        import ui
        window=NS(_neural_request='old',_neural_clock=Mock(),_update_neural_memory=Mock())
        ui.MainWindow._finish_neural_memory(window,'stale');self.assertEqual(window._neural_request,'old')
        ui.MainWindow._finish_neural_memory(window,'old');self.assertIsNone(window._neural_request)
        ui.MainWindow._show_manifestation(window,{'kind':'memory','items':[{'id':'next','detail':'Um fato registrado.'}]})
        self.assertEqual(window._update_neural_memory.call_count,2)
        self.assertEqual(window._update_neural_memory.call_args.args[0]['items'][0]['id'],'next')

    def test_no_renderer_fallback_releases_the_request_gate(self):
        import ui
        for core in (None,NS(failed=True)):
            window=NS(_resting=False,_forge_controller=None,_settings_hub=None,_ultron_payload=None,
                      hud=NS(_spatial_core=core),_neural_request='fallback',_neural_clock=Mock(),_show_content=Mock())
            window._finish_neural_memory=lambda identifier:ui.MainWindow._finish_neural_memory(window,identifier)
            ui.MainWindow._update_neural_memory(window,{'requestId':'fallback','active':True,'items':[{'id':'a','detail':'Registro'}]})
            window._show_content.assert_called_once();self.assertIsNone(window._neural_request)


class UltronClosingTests(unittest.TestCase):
    def test_shutdown_state_rejects_work_admitted_from_the_async_queue(self):
        from unittest.mock import AsyncMock
        from core.ultron import Runtime
        runtime=Runtime();callback=AsyncMock(return_value={'accepted':True})
        try:
            with patch.object(runtime,'_closed',True):
                future=asyncio.run_coroutine_threadsafe(runtime._invoke(callback,()),runtime._loop)
                with self.assertRaisesRegex(RuntimeError,'closed'):future.result(timeout=2)
            callback.assert_not_awaited()
        finally:runtime.close()
