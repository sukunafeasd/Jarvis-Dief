"""Auxiliary controls and stalled-turn recovery, using disposable data only."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import asyncio
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch,AsyncMock
from PyQt6.QtWidgets import QApplication,QWidget,QPushButton,QLineEdit
from PyQt6.QtTest import QTest
import ui
from core.elevation_dialog import ElevationDialog
from core.workspace_panels import WorkspacePanel
from core.daily_refresh_view import DailyRefreshView
from test_voice_interrupt import assistant_fixture

OUTPUT=Path(tempfile.mkdtemp(prefix='dief-auxiliary-theme-'))


class AuxiliaryThemeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication(['DIEF visual check'])
        cls.app.setStyle('Fusion')

    def test_auxiliary_forms_keep_controls_and_private_inputs(self):
        cases=[ui.SetupOverlay(),ui.CustomizeOverlay(),ui.PluginManagerOverlay([]),
            ui.ConfirmBanner('Confirmação de demonstração','Nenhuma operação será executada.'),
            ui.AudioDeviceOverlay(),ui.MemoryOverlay(),ui.PluginSettingsOverlay([]),
            ui.RemoteKeyOverlay('http://127.0.0.1:8765','DEMO-SEM-ACESSO'),
            ui.ClipboardPanel(),ui._CameraPreview(),ElevationDialog(lambda:False)]
        try:
            for widget in cases:
                widget.show();widget.adjustSize();QTest.qWait(100)
                self.assertTrue(widget.property('independentTheme'),type(widget).__name__)
                self.assertFalse(widget._plate.isNull(),type(widget).__name__)
                self.assertTrue(widget.grab().save(str(OUTPUT/(type(widget).__name__+'.png'))))
                for button in widget.findChildren(QPushButton):
                    if not button.isVisible() or button.visibleRegion().isEmpty():continue
                    corner=button.mapTo(widget,button.rect().bottomRight())
                    self.assertTrue(widget.rect().contains(corner),(type(widget).__name__,button.text(),corner))
                widget.hide()
            setup=cases[0]
            self.assertEqual(setup._key_input.echoMode(),QLineEdit.EchoMode.Password)
            self.assertEqual(setup._key_input.text(),'')
            self.assertEqual(sum(button.isChecked() for button in setup._os_btns.values()),1)
            self.assertEqual(sum(button.isChecked() for button in cases[1]._voice_btns.values()),1)
        finally:
            for widget in cases:widget.close();widget.deleteLater()
            self.app.processEvents()

    def test_workspace_and_refresh_use_actual_content_and_stop_when_hidden(self):
        stage=QWidget();stage.resize(1000,700);stage.show()
        try:
            for mode in ('terminal','execution'):
                panel=WorkspacePanel(stage,mode);panel.setGeometry(0,0,500,600)
                panel.show_panel(reduced=False);QTest.qWait(300)
                panel.add_line('Texto de demonstração <sem executar comandos>')
                if mode=='execution':panel.record('web_search:search','running')
                self.assertIn('<sem executar comandos>',panel.transcript.toPlainText())
                self.assertTrue(panel.grab().save(str(OUTPUT/(mode+'.png'))))
                panel.close_panel()
                self.assertNotEqual(panel.surface._light.state(),panel.surface._light.State.Running)
            progress=DailyRefreshView(stage)
            progress.update_model({'id':'demo','total':4,'completed':2,'items':[{'title':'Agenda','status':'working'}]})
            QTest.qWait(100)
            self.assertTrue(progress.grab().save(str(OUTPUT/'daily-refresh.png')))
            self.assertIn('Agenda',progress.detail.text());self.assertFalse(progress.findChildren(QPushButton))
            progress.finish('outro');self.assertTrue(progress.isVisible())
            progress.finish('demo');self.assertFalse(progress.isVisible())
            self.assertNotEqual(progress._light.state(),progress._light.State.Running)
        finally:stage.close();stage.deleteLater();self.app.processEvents()

    def test_hidden_log_does_not_replay_characters_or_lose_lines(self):
        log=ui.LogWidget()
        try:
            lines=['Jarvis: '+str(i)+' '+('texto '*100) for i in range(12)]
            for line in lines:log.append_log(line)
            QTest.qWait(650)
            self.assertFalse(log._typing)
            self.assertEqual(log.toPlainText().rstrip('\n'),'\n'.join(lines))
            self.assertFalse(log._tmr.isActive())
        finally:log.close();log.deleteLater()


class ResponseProgressTests(unittest.TestCase):
    def owner(self):
        owner=assistant_fixture();owner._is_speaking=False
        owner._fish_voice=None;owner._server_activity_serial=1
        owner._tools_inflight=0
        return owner

    def test_silent_turn_expires_but_new_activity_restarts_deadline(self):
        owner=self.owner()
        self.assertFalse(owner._response_stalled(0))
        self.assertFalse(owner._response_stalled(29))
        self.assertTrue(owner._response_stalled(30))
        owner._server_activity_serial+=1
        self.assertFalse(owner._response_stalled(31))
        self.assertFalse(owner._response_stalled(60))


class FirstResponseTests(unittest.IsolatedAsyncioTestCase):
    def owner(self):
        owner=assistant_fixture();owner._is_speaking=False
        owner._fish_voice=None;owner._wake_enabled=False;owner._awake=True
        owner._route_protocol_user=AsyncMock(return_value=False)
        owner._remember_user_turn=AsyncMock()
        owner.session=AsyncMock();owner._turn_done_event.set()
        return owner

    async def test_first_response_is_tracked_before_any_server_packet(self):
        owner=self.owner()
        self.assertTrue(await owner._handle_text_command('Que horas sao?'))
        self.assertTrue(owner._server_turn_open)
        self.assertFalse(owner._response_stalled(0))
        self.assertTrue(owner._response_stalled(30))
        owner.session.send_client_content.assert_awaited_once()

    async def test_failed_send_releases_its_wait_without_retry(self):
        owner=self.owner();owner.session.send_client_content.side_effect=OSError('offline')
        with self.assertRaises(OSError):await owner._handle_text_command('Pedido de teste')
        self.assertFalse(owner._server_turn_open);self.assertTrue(owner._turn_done_event.is_set())
        owner.session.send_client_content.assert_awaited_once()

    async def test_failed_old_send_cannot_clear_a_newer_response(self):
        owner=self.owner()
        async def replacement(**kwargs):
            owner._response_epoch+=1
            raise OSError('offline')
        owner.session.send_client_content.side_effect=replacement
        with self.assertRaises(OSError):await owner._handle_text_command('Pedido antigo')
        self.assertTrue(owner._server_turn_open)
        self.assertFalse(owner._turn_done_event.is_set())

    def test_tools_audio_and_native_routes_are_not_cancelled_as_silent_turns(self):
        for attr,value in (('_tools_inflight',1),('_is_speaking',True),('_routing_protocol_input',True),
            ('_refresh_in_progress',True),('_fish_voice',SimpleNamespace(pending=True))):
            owner=self.owner();owner._response_stalled(0);setattr(owner,attr,value)
            self.assertFalse(owner._response_stalled(100),attr)
        owner=self.owner();owner._response_stalled(0);owner.audio_in_queue.put_nowait(b'pcm')
        self.assertFalse(owner._response_stalled(100))

    def test_finished_and_replaced_turns_do_not_inherit_old_deadline(self):
        owner=self.owner();owner._response_stalled(0)
        owner._server_turn_open=False
        self.assertFalse(owner._response_stalled(100))
        owner._server_turn_open=True;owner._response_epoch+=1
        self.assertFalse(owner._response_stalled(200))

    def test_incomplete_fish_text_does_not_block_stall_recovery(self):
        owner=self.owner()
        owner._fish_voice=SimpleNamespace(pending=True,synthesizing=False)
        self.assertFalse(owner._response_stalled(0))
        self.assertTrue(owner._response_stalled(30))


if __name__=='__main__':
    print('Capturas:',OUTPUT,flush=True)
    unittest.main()
