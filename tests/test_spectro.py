import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import unittest
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from PyQt6.QtWidgets import QApplication,QWidget
from PyQt6.QtCore import pyqtSignal,QRect
from core.spectro import SpectroController,SpectroWindow,clamped_rect
from core.spectro_commands import request
import test_forge_host_routing as host


class FakeView(QWidget):
    ready=pyqtSignal();unavailable=pyqtSignal()
    def __init__(self,parent):super().__init__(parent);self.sync=Mock();self.sync_environment=Mock();self.stop=Mock()


class SpectroTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])

    def setUp(self):
        self.owner=QWidget();self.owner.resize(1000,700)
        self.owner.hud=SimpleNamespace(motion_reduced=True,state='LISTENING',speaking=False,
            _amp_disp=.2,muted=False,resting=False,append_log=Mock())
        self.owner._do_interrupt=Mock();self.owner.show()
        self.controller=SpectroController(self.owner,lambda owner:SpectroWindow(owner,FakeView))
        from core.spectro_store import SpectroStore
        folder=tempfile.TemporaryDirectory();self.addCleanup(folder.cleanup)
        self.controller.store=SpectroStore(Path(folder.name)/'spectro.json')

    def tearDown(self):self.controller.close();self.owner.close();self.app.processEvents()

    def start(self):
        result=self.controller.apply('enter',{})
        self.assertFalse(result['completed']);self.assertTrue(self.owner.isVisible())
        self.assertEqual(self.controller.window.windowOpacity(),0.)
        self.controller.window.view.ready.emit()
        self.assertFalse(self.owner.isVisible());self.assertTrue(self.controller.ready)

    def test_ready_transition_and_return_preserve_owner_and_voice(self):
        hud=self.owner.hud;self.start();window=self.controller.window
        self.assertEqual(window.view.sync.call_args.args[0]['phase'],'listening')
        self.controller.apply('exit',{})
        self.assertTrue(self.owner.isVisible());self.assertIs(self.owner.hud,hud)
        self.assertFalse(window.timer.isActive());self.assertFalse(self.controller.active)

    def test_failed_renderer_restores_base_and_stops_timer(self):
        self.start();window=self.controller.window;window.view.unavailable.emit()
        self.assertTrue(self.owner.isVisible());self.assertFalse(self.controller.active)
        self.assertFalse(window.timer.isActive())

    def test_bounds_mask_opacity_and_size_are_constrained(self):
        self.start();window=self.controller.window
        self.assertFalse(window.mask().contains(window.rect().topLeft()))
        self.assertTrue(window.mask().contains(window.rect().center()))
        self.controller.apply('opacity',{'value':-.5});self.assertGreaterEqual(window.windowOpacity(),.17)
        self.controller.apply('scale',{'factor':.01});self.assertGreaterEqual(window.width(),140)
        self.controller.apply('position',{'anchor':'left'})
        self.assertTrue(window.screen().availableGeometry().contains(window.geometry()))
        with self.assertRaises(ValueError):self.controller.apply('opacity',{'value':float('nan')})

    def test_emergency_interrupts_voice_and_restores_base(self):
        self.start();self.controller.window.return_requested.emit()
        self.owner._do_interrupt.assert_called_once();self.assertTrue(self.owner.isVisible())

    def test_system_close_of_overlay_returns_to_base(self):
        self.start();self.controller.window.close()
        self.assertTrue(self.owner.isVisible());self.assertFalse(self.controller.active)

    def test_old_window_signals_cannot_close_new_presence(self):
        self.start();old=self.controller.window
        self.controller.apply('exit',{});self.start();new=self.controller.window
        self.controller._failed(old);self.controller._ready(old)
        self.assertIs(self.controller.window,new);self.assertTrue(self.controller.ready)

    def test_old_emergency_request_does_not_interrupt_new_presence(self):
        self.start();old=self.controller.window
        self.controller.apply('exit',{});self.start();new=self.controller.window
        old.return_requested.emit();old.request_return()
        self.assertIs(self.controller.window,new);self.assertTrue(self.controller.active)
        self.owner._do_interrupt.assert_not_called()

    def test_closed_controller_cannot_reopen(self):
        self.controller.close()
        with self.assertRaises(ValueError):self.controller.apply('enter',{})
        self.assertIsNone(self.controller.window)

    def test_queued_ui_activation_is_rejected_during_shutdown(self):
        import threading
        from ui import MainWindow
        self.owner._closed_for_shutdown=True;self.owner._spectro_controller=None
        self.owner.interface_snapshot=Mock(return_value={})
        packet={'action':'spectro','value':'enter','setting':'{}','done':threading.Event()}
        MainWindow._apply_interface_request(self.owner,packet)
        self.assertFalse(packet['result']['ok']);self.assertTrue(packet['done'].is_set())
        self.assertIsNone(self.owner._spectro_controller)

    def test_voice_mapping_is_bounded_by_active_mode(self):
        self.assertEqual(request('Jarvis, ativa o modo espectro')[0],'enter')
        for text in ('fica menor','mais transparente','vai para a esquerda'):
            self.assertIsNone(request(text,False))
        self.assertEqual(request('fica menor',True)[0],'scale')
        self.assertEqual(request('fica mais transparente',True)[0],'opacity')
        self.assertEqual(request('vai para a esquerda',True)[1]['anchor'],'left')
        for text in ('nao ative o espectro','como ativar o espectro?','e se ativar o espectro','ative o espectro e apague tudo'):
            self.assertIsNone(request(text,True))

    def test_secondary_monitor_negative_origin_is_supported(self):
        area=QRect(-1920,0,1920,1040)
        self.assertTrue(area.contains(clamped_rect(QRect(-3000,1500,320,320),area)))


class SpectroRouting(unittest.IsolatedAsyncioTestCase):
    owner=host.RoutingTests.owner

    async def test_voice_enters_through_ui_and_keeps_same_session(self):
        owner=self.owner();session=object();owner.session=session
        owner.ui.control_interface=Mock(return_value={'ok':True,'completed':False})
        self.assertTrue(await owner._route_protocol_user('ativa o modo espectro'))
        owner.ui.control_interface.assert_called_once_with('spectro','enter','{}')
        self.assertIs(owner.session,session)

    async def test_question_is_not_activation(self):
        owner=self.owner();owner.ui.control_interface=Mock()
        self.assertFalse(await owner._route_protocol_user('como ativar modo espectro?'))
        owner.ui.control_interface.assert_not_called()

    async def test_followup_adjustment_only_when_presence_active(self):
        owner=self.owner();owner.ui._win._spectro_controller=SimpleNamespace(active=True)
        owner.ui.control_interface=Mock(return_value={'ok':True,'completed':True})
        self.assertTrue(await owner._route_protocol_user('mais transparente'))
        self.assertEqual(owner.ui.control_interface.call_args.args[:2],('spectro','opacity'))


if __name__=='__main__':unittest.main()
