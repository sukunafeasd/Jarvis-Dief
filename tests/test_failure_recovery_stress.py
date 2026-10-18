"""Regression proofs for failed disk writes and permanently delayed providers."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import asyncio
import copy
import threading
import time
import unittest
from unittest.mock import patch
from PyQt6.QtTest import QTest
import test_settings_connections
import test_fui_screens
import test_scene
from core.bounded_work import BoundedWork


class PinFailureTests(unittest.TestCase):
    setUpClass=classmethod(test_scene.SceneTests.setUpClass.__func__)
    setUp=test_fui_screens.AllSettingsPagesTests.setUp
    tearDown=test_fui_screens.AllSettingsPagesTests.tearDown
    command=test_scene.SceneTests.command

    def test_failed_unpin_preserves_widget_cache_disk_and_allows_retry(self):
        self.window._pin_data({'kind':'tasks','title':'Tarefas','items':[{'title':'Exemplo'}]})
        preview=self.window._pin_previews['tasks'];saved=copy.deepcopy(self.window._pin_store.load())
        with patch.object(self.window._pin_store,'save',side_effect=OSError('Synthetic disk error')):
            response=self.command('unpin','tasks')
        self.assertFalse(response['ok'])
        self.assertIs(self.window._pin_previews['tasks'],preview)
        self.assertFalse(preview['widget'].isHidden())
        self.assertEqual(self.window._pin_store.load(),saved)
        self.assertTrue(self.command('unpin','tasks')['ok'])
        self.assertNotIn('tasks',self.window._pin_previews)
        self.assertEqual(self.window._pin_store.load(),[])

    def test_corner_move_with_three_implicit_slots_reaches_real_target(self):
        self.window.resize(1600,1000);self.app.processEvents()
        for kind in ('weather','tasks','calendar'):
            self.window._pin_data({'kind':kind,'title':kind,'items':[]})
        self.window._content_panel.hide()
        result=self.command('move_pin','calendar','bottom_left')
        self.assertTrue(result['ok'],result)
        self.window._layout_scene(False)
        rect=self.window._pin_previews['calendar']['widget'].geometry()
        self.assertEqual(rect.x(),12)
        self.assertEqual(rect.bottom(),self.window._scene_stage.height()-13)


class ConnectionTimeoutTests(unittest.TestCase):
    setUpClass=classmethod(test_settings_connections.ConnectionsTests.setUpClass.__func__)
    cleanup_widgets=test_settings_connections.ConnectionsTests.cleanup_widgets

    def setUp(self):
        verify=patch('ui.MainWindow._verify_saved_connections');verify.start();self.addCleanup(verify.stop)
        test_settings_connections.ConnectionsTests.setUp(self)

    def test_manual_timeout_releases_controls_and_discards_old_success(self):
        import core.settings_hub as settings
        gate=threading.Event();entered=threading.Event();done=threading.Event()
        pool=BoundedWork(workers=2,capacity=2,name='SyntheticConnection')
        def stalled():
            entered.set();gate.wait(timeout=5);done.set();return True,'Old success'
        try:
            with patch.object(settings,'CONNECTION_TIMEOUT',.08),patch.object(settings,'_CONNECTION_WORK',pool):
                self.hub._connection_worker(stalled,'gmail')
                self.assertTrue(entered.wait(timeout=2))
                deadline=time.monotonic()+3
                while self.hub._connection_checks.get('gmail').get('busy') and time.monotonic()<deadline:QTest.qWait(20)
                QTest.qWait(30)
                self.assertEqual(self.hub._connection_checks.get('gmail')['state'],'error')
                self.hub._connection_worker(lambda:(True,'New confirmed result'),'gmail')
                deadline=time.monotonic()+3
                while self.hub._connection_checks.get('gmail').get('busy') and time.monotonic()<deadline:QTest.qWait(20)
                gate.set();self.assertTrue(done.wait(timeout=2));QTest.qWait(80)
                self.assertEqual(self.hub._connection_checks.get('gmail')['message'],'New confirmed result')
                self.assertEqual(self.hub.connection_notice.text(),'New confirmed result')
        finally:gate.set();pool.close()

    def test_save_during_expired_authorization_never_waits_on_gui_thread(self):
        from core import gmail_connection as gmail
        held=threading.Event();release=threading.Event()
        def authorization():
            with gmail.LOCK:
                held.set();release.wait(timeout=4)
        worker=threading.Thread(target=authorization,daemon=True);worker.start()
        try:
            self.assertTrue(held.wait(timeout=2))
            started=time.monotonic()
            self.assertFalse(self.hub.save_gmail_credentials())
            self.assertLess(time.monotonic()-started,.2)
            self.assertIn('ainda está encerrando',self.hub.connection_notice.text())
        finally:release.set();worker.join(timeout=2)


class RefreshTimeoutTests(unittest.IsolatedAsyncioTestCase):
    async def test_stalled_refresh_does_not_own_default_executor_or_grow_workers(self):
        from core import session_refresh
        gate=threading.Event();pool=BoundedWork(workers=2,capacity=3,name='SyntheticRefresh')
        def stalled():gate.wait(timeout=5);return {'count':1}
        try:
            with patch.object(session_refresh,'_SOURCE_WORK',pool):
                for _ in range(30):
                    result=await session_refresh.collect_updates(None,lambda value:None,sources={'tasks':('Synthetic',stalled)},timeout=.015)
                    self.assertEqual(result['unavailable'],['tasks'])
                self.assertEqual(len(pool.threads),2)
                await asyncio.wait_for(asyncio.get_running_loop().shutdown_default_executor(),timeout=.2)
        finally:
            gate.set();pool.close()
            for thread in pool.threads:thread.join(timeout=2)


if __name__=='__main__':unittest.main()
