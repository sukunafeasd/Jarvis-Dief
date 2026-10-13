import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import unittest
from unittest.mock import patch
from PyQt6.QtCore import Qt, QEvent
from PyQt6.QtWidgets import QApplication, QWidget
from core.window_behavior import IdleCursor
from core import elevation


class WindowBehaviorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])

    def test_cursor_hides_at_twenty_seconds_and_returns_on_input(self):
        window=QWidget(); child=QWidget(window); clock=[0]
        cursor=IdleCursor(window,clock=lambda:clock[0]); cursor.timer.stop()
        try:
            with patch.object(QApplication,'activeWindow',return_value=window),patch.object(QApplication,'widgetAt',return_value=child):
                clock[0]=19.9;cursor.check();self.assertFalse(cursor.hidden)
                clock[0]=20;cursor.check();self.assertTrue(cursor.hidden)
                self.assertEqual(self.app.overrideCursor().shape(),Qt.CursorShape.BlankCursor)
                cursor.eventFilter(child,QEvent(QEvent.Type.MouseMove))
                self.assertFalse(cursor.hidden);self.assertIsNone(self.app.overrideCursor())
                clock[0]=40;cursor.check();self.assertTrue(cursor.hidden)
                cursor.eventFilter(window,QEvent(QEvent.Type.WindowDeactivate))
                self.assertFalse(cursor.hidden)
        finally:
            cursor.restore();self.app.removeEventFilter(cursor);window.deleteLater();self.app.processEvents()

    def test_cursor_never_hides_over_another_app(self):
        window=QWidget();other=QWidget();clock=[0]
        cursor=IdleCursor(window,clock=lambda:clock[0]);cursor.timer.stop()
        try:
            with patch.object(QApplication,'activeWindow',return_value=window),patch.object(QApplication,'widgetAt',return_value=other):
                clock[0]=100;cursor.check();self.assertFalse(cursor.hidden)
        finally:
            cursor.restore();self.app.removeEventFilter(cursor);window.deleteLater();other.deleteLater();self.app.processEvents()

    def test_destroyed_owner_removes_global_filter_and_stops_timer(self):
        from PyQt6 import sip
        window=QWidget();other=QWidget();cursor=IdleCursor(window)
        cursor.eventFilter(window,QEvent(QEvent.Type.Close))
        self.assertTrue(cursor.disposed);self.assertFalse(cursor.timer.isActive())
        sip.delete(window)
        self.assertFalse(cursor.owns(other))
        self.assertFalse(cursor.eventFilter(other,QEvent(QEvent.Type.MouseMove)))
        other.deleteLater();self.app.processEvents()

    def test_admin_entry_can_proceed_only_when_elevated(self):
        with patch.object(elevation,'is_admin',return_value=True),patch.dict('sys.modules',{'tkinter':None}):
            self.assertTrue(elevation.require_admin())

    def test_main_panel_opens_fullscreen(self):
        import ui
        window=QWidget()
        try:
            with patch.object(ui,'MainWindow',return_value=window):
                ui.JarvisUI('unused-test-asset')
            self.assertTrue(window.isFullScreen())
            window._idle_cursor.timer.stop()
            self.app.removeEventFilter(window._idle_cursor)
        finally:
            window.close();window.deleteLater();self.app.processEvents()

    def test_elevation_quotes_script_and_reports_uac_cancellation(self):
        with patch.object(elevation.sys,'argv',[r'C:\Jarvis Folder\main.py','two words']),patch.object(elevation.sys,'executable',r'C:\Python Folder\python.exe'),patch.object(elevation.ctypes.windll.shell32,'ShellExecuteW',return_value=5) as launch:
            self.assertFalse(elevation.restart_elevated())
            args=launch.call_args.args
            self.assertEqual(args[1],'runas')
            self.assertIn('"two words"',args[3])
            self.assertIn('"C:\\Jarvis Folder\\main.py"',args[3])
