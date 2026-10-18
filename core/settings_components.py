"""Responsive native controls for the observatory settings workspace."""
from PyQt6.QtCore import Qt, QRect, QRectF, QSize, QEvent, QDateTime, QTimer, QPropertyAnimation, QEasingCurve, pyqtProperty
from PyQt6.QtWidgets import (QWidget, QLabel, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLayout, QWidgetItem, QSizePolicy, QCheckBox)
from core.hud_glass import PinnedPreviewFrame
from core.ui_assets import symbol_pixmap


class StatusLabel(QLabel):
    def __init__(self,parent=None):
        super().__init__(parent);self.setContentsMargins(12,0,0,0)
    def paintEvent(self,event):
        super().paintEvent(event)
        from PyQt6.QtGui import QPainter,QColor
        colors={'ok':'#29e8a1','notice':'#ffcb6d','error':'#ff667b','muted':'#5487a6'}
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing);p.setPen(Qt.PenStyle.NoPen)
        color=QColor(colors.get(self.property('tone'),'#5487a6'))
        color.setAlpha(30);p.setBrush(color);p.drawEllipse(QRectF(0,self.height()/2-5,10,10))
        color.setAlpha(255);p.setBrush(color);p.drawEllipse(QRectF(2,self.height()/2-3,6,6));p.end()


class LightSwitch(QCheckBox):
    def __init__(self, parent=None):
        super().__init__(parent);self._position=0.0;self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(48,28);self.animation=QPropertyAnimation(self,b'position',self)
        self.animation.setDuration(140);self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.toggled.connect(self._toggle)

    @pyqtProperty(float)
    def position(self):return self._position
    @position.setter
    def position(self,value):self._position=value;self.update()
    def _toggle(self,checked):
        self.animation.stop()
        owner=self.window()
        reduced=hasattr(owner,'_config') and owner._config().get('reduce_motion',False)
        if not self.isVisible() or reduced:self.position=float(checked);return
        self.animation.setStartValue(self.position);self.animation.setEndValue(float(checked));self.animation.start()
    def hitButton(self,point):return self.rect().contains(point)
    def setChecked(self,checked):
        super().setChecked(checked)
        # Programmatic rollback may block signals; the thumb must match the state.
        if self.signalsBlocked():
            self.animation.stop();self.position=float(self.isChecked())
    def paintEvent(self,event):
        from PyQt6.QtGui import QPainter,QColor,QPen,QLinearGradient
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setOpacity(1 if self.isEnabled() else .45)
        track=QLinearGradient(0,3,0,25)
        track.setColorAt(0,QColor('#056895' if self.isChecked() else '#081929'))
        track.setColorAt(1,QColor('#02b8f2' if self.isChecked() else '#12293c'))
        p.setPen(QPen(QColor('#6ae4ff' if self.isChecked() else '#326285'),1));p.setBrush(track);p.drawRoundedRect(QRectF(2,4,44,20),10,10)
        x=5+24*self.position
        p.setPen(Qt.PenStyle.NoPen);p.setBrush(QColor(70,211,255,55));p.drawEllipse(QRectF(x-3,3,22,22))
        p.setBrush(QColor('#e3f8ff' if self.isChecked() else '#91bbda'));p.drawEllipse(QRectF(x,6,16,16))
        if self.hasFocus():
            p.setBrush(Qt.BrushStyle.NoBrush);p.setPen(QPen(QColor('#e3f8ff'),1,Qt.PenStyle.DotLine));p.drawRoundedRect(QRectF(0,1,47,26),12,12)
        p.end()


class TileLayout(QLayout):
    """Two balanced columns with full-width headings/editors and no filter holes."""
    def __init__(self, parent=None):
        super().__init__(parent); self.items=[]; self.setSpacing(12); self.setContentsMargins(4,4,8,16)

    def addItem(self, item): self.items.append(item); self.invalidate()
    def count(self): return len(self.items)
    def itemAt(self, index): return self.items[index] if 0 <= index < len(self.items) else None
    def takeAt(self, index):
        item = self.items.pop(index) if 0 <= index < len(self.items) else None
        self.invalidate(); return item
    def addLayout(self, layout): self.addChildLayout(layout); self.addItem(layout)
    def addStretch(self, stretch=0): pass
    def insertWidget(self, index, widget):
        self.addChildWidget(widget); self.items.insert(index, QWidgetItem(widget)); self.invalidate()
    def expandingDirections(self): return Qt.Orientation.Horizontal
    def hasHeightForWidth(self): return True
    def heightForWidth(self, width): return self._arrange(QRect(0,0,width,0), False)
    def minimumSize(self): return QSize(280,0)
    def sizeHint(self): return QSize(900,self.heightForWidth(900))
    def setGeometry(self, rect): super().setGeometry(rect); self._arrange(rect, True)

    def _arrange(self, rect, apply):
        margins=self.contentsMargins(); width=max(1,rect.width()-margins.left()-margins.right())
        x=rect.x()+margins.left(); y=rect.y()+margins.top(); gap=self.spacing()
        columns=2 if width>=880 else 1
        tile_width=(width-gap*(columns-1))//columns
        pending=[]
        def height(item,w):
            return max(item.minimumSize().height(), item.heightForWidth(w) if item.hasHeightForWidth() else item.sizeHint().height())
        def flush():
            nonlocal y,pending
            if not pending:return
            h=max(height(item,tile_width) for item in pending)
            for column,item in enumerate(pending):
                if apply:item.setGeometry(QRect(x+column*(tile_width+gap),y,tile_width,h))
            y+=h+gap; pending=[]
        for item in self.items:
            widget=item.widget()
            if widget and widget.isHidden():continue
            if widget and widget.property('connectionTile'):
                pending.append(item)
                if len(pending)==columns:flush()
            else:
                flush(); h=height(item,width)
                if apply:item.setGeometry(QRect(x,y,width,h))
                y+=h+gap
        flush()
        return y-rect.y()+margins.bottom()


class SettingsSection(PinnedPreviewFrame):
    def __init__(self, title, subtitle='', icon='settings-2', parent=None):
        super().__init__(parent); self.setObjectName('settingsSection')
        self.outer=QVBoxLayout(self); self.outer.setContentsMargins(20,16,20,18); self.outer.setSpacing(12)
        heading=QHBoxLayout(); heading.setSpacing(12)
        mark=QLabel(); mark.setPixmap(symbol_pixmap(icon,size=26));mark.setFixedSize(30,34);heading.addWidget(mark)
        labels=QVBoxLayout();labels.setSpacing(2)
        name=QLabel(title);name.setObjectName('sectionHeading'); labels.addWidget(name)
        if subtitle:
            hint=QLabel(subtitle);hint.setObjectName('settingsMeta');hint.setWordWrap(True);labels.addWidget(hint)
        heading.addLayout(labels,1);heading.setAlignment(Qt.AlignmentFlag.AlignTop);self.outer.addLayout(heading)
        self.form=QFormLayout();self.form.setContentsMargins(0,6,0,0);self.form.setHorizontalSpacing(22);self.form.setVerticalSpacing(12)
        self.form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows);self.outer.addLayout(self.form)
        self.outer.setAlignment(Qt.AlignmentFlag.AlignTop)


def field_label(title, description='', icon='settings-2'):
    widget=QWidget(); row=QHBoxLayout(widget);row.setContentsMargins(0,0,0,0);row.setSpacing(10)
    mark=QLabel();mark.setPixmap(symbol_pixmap(icon,size=21));mark.setFixedSize(28,30);row.addWidget(mark)
    labels=QVBoxLayout();labels.setSpacing(2)
    text=QLabel(title);text.setWordWrap(True);text.setObjectName('fieldTitle');labels.addWidget(text)
    if description:
        detail=QLabel(description);detail.setWordWrap(True);detail.setObjectName('settingsMeta');labels.addWidget(detail)
    row.addLayout(labels);widget.setMinimumWidth(200);widget.setMaximumWidth(350)
    return widget


class CorePreview(PinnedPreviewFrame):
    """Reuse the real core; rendering is suspended outside the profile page."""
    def __init__(self, hub):
        super().__init__();self.hub=hub;self.view=None;self._creating_view=False;self.setObjectName('corePreview')
        self.setMinimumSize(250,270);self.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Expanding)
        self.layout_box=QVBoxLayout(self);self.layout_box.setContentsMargins(12,12,12,12)
        label=QLabel('JARVIS');label.setObjectName('sectionHeading');label.setAlignment(Qt.AlignmentFlag.AlignCenter);self.layout_box.addWidget(label)
        self.placeholder=QLabel();self.placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        from PyQt6.QtGui import QPixmap
        from pathlib import Path
        picture=QPixmap(str(Path(__file__).resolve().parents[1]/'config/dief-jarvis.png'))
        self.placeholder.setPixmap(picture.scaled(230,230,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))
        self.layout_box.addWidget(self.placeholder,1)
        self.caption=QLabel('Núcleo holográfico');self.caption.setObjectName('settingsMeta');self.caption.setAlignment(Qt.AlignmentFlag.AlignCenter);self.layout_box.addWidget(self.caption)

    def showEvent(self,event):
        super().showEvent(event)
        import os
        if self.view is None and not self._creating_view and os.environ.get('QT_QPA_PLATFORM')!='offscreen':
            from core.spatial_view import SpatialCoreView
            # Creating WebEngine may process a nested show event before returning.
            self._creating_view=True
            try:
                self.view=SpatialCoreView(self);self.view.setMinimumSize(180,190);self.view.setMaximumHeight(300)
                self.view.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Ignored)
                self.layout_box.insertWidget(1,self.view,1);self.placeholder.hide()
                self.view.sync_environment({'staging':False})
                self.view.unavailable.connect(self.placeholder.show)
            finally:self._creating_view=False
        self.sync_preview()

    def sync_preview(self):
        if not self.view:return
        visible=self.isVisible() and not self.hub.isMinimized()
        self.view.sync({'phase':'idle','color':getattr(self.hub,'selected_color','#ff303b'),
            'visible':visible,'motion':'reduced' if self.hub._config().get('reduce_motion') else 'full'})
        if visible and not self.view.failed:
            if not self.view._health.isActive():
                import time
                self.view._created=time.monotonic()
                self.view._health.start(1000)
        else:self.view._health.stop()

    def hideEvent(self,event):
        if self.view:
            self.view.sync({**self.view._payload,'visible':False})
            self.view._health.stop()
        super().hideEvent(event)

    def closeEvent(self,event):
        if self.view:self.view.close()
        super().closeEvent(event)

    def eventFilter(self,watched,event):
        result=super().eventFilter(watched,event)
        if watched is self._motion_window and event.type()==QEvent.Type.WindowStateChange:self.sync_preview()
        return result


class RailClock(QLabel):
    def __init__(self,parent=None):
        super().__init__(parent);self.setObjectName('railClock');self.timer=QTimer(self)
        self.timer.setInterval(30000);self.timer.timeout.connect(self.refresh);self.refresh()
    def refresh(self):self.setText(QDateTime.currentDateTime().toString('HH:mm\ndd.MM.yyyy'))
    def showEvent(self,event):super().showEvent(event);self.refresh();self.timer.start()
    def hideEvent(self,event):self.timer.stop();super().hideEvent(event)
