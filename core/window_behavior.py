"""App-scoped cursor idling; never changes the cursor over other applications."""
import time
from PyQt6.QtCore import QObject, QEvent, QTimer, Qt
from PyQt6.QtGui import QCursor
from PyQt6.QtWidgets import QApplication, QWidget


class IdleCursor(QObject):
    def __init__(self, window, timeout=20, clock=time.monotonic):
        super().__init__(window)
        self.window, self.timeout, self.clock = window, timeout, clock
        self.last_activity = clock()
        self.hidden = False
        self.position = QCursor.pos()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.check)
        self.timer.start(250)
        QApplication.instance().installEventFilter(self)
        window.destroyed.connect(self.restore)

    def owns(self, widget):
        return isinstance(widget, QWidget) and (widget is self.window or self.window.isAncestorOf(widget))

    def restore(self, *_):
        if self.hidden:
            QApplication.restoreOverrideCursor()
            self.hidden = False

    def activity(self):
        self.last_activity = self.clock()
        self.restore()

    def check(self):
        position = QCursor.pos()
        if position != self.position:
            self.position = position
            self.activity()
        app = QApplication.instance()
        active = app.activeWindow()
        under_pointer = app.widgetAt(position)
        if not self.owns(active) or not self.owns(under_pointer):
            self.restore()
            self.last_activity = self.clock()
            return
        if not self.hidden and self.clock() - self.last_activity >= self.timeout:
            QApplication.setOverrideCursor(Qt.CursorShape.BlankCursor)
            self.hidden = True

    def eventFilter(self, watched, event):
        if self.owns(watched):
            if event.type() in (QEvent.Type.MouseMove, QEvent.Type.MouseButtonPress,
                                QEvent.Type.Wheel, QEvent.Type.KeyPress):
                self.activity()
            elif event.type() == QEvent.Type.WindowDeactivate:
                self.restore()
            elif watched is self.window and event.type() in (QEvent.Type.Hide,QEvent.Type.Close):
                self.restore()
        return False
