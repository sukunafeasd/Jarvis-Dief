"""On-demand conversation and execution surfaces with restrained perspective."""
import time
from core.hud_glass import HudGlassFrame
from pathlib import Path
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QIcon, QTransform, QTextCursor, QImageReader
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
    QLineEdit, QPushButton, QStyle, QFileDialog, QGraphicsView, QGraphicsScene)

from core.auxiliary_theme import SURFACE_STYLE
STYLE=SURFACE_STYLE+'''
QWidget#Surface { background:transparent; border:0; }
QTextEdit { background:transparent; border:0; border-top:1px solid #3c8eb560; padding:8px 0; }
QPushButton { padding:4px; }
'''


def panel_icon(style,kind):
    pixmap=style.standardIcon(kind).pixmap(22,22)
    painter=QPainter(pixmap)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    painter.fillRect(pixmap.rect(),QColor('#cbe8ed'));painter.end()
    return QIcon(pixmap)


def image_preview(path):
    """Bound decoding before allocating a full-resolution user image."""
    from PyQt6.QtCore import QSize
    reader = QImageReader(str(path))
    reader.setAutoTransform(True)
    size = reader.size()
    if not size.isValid() or size.width()*size.height() > 80000000:
        raise ValueError('Imagem invalida ou maior que 80 megapixels.')
    reader.setScaledSize(size.scaled(QSize(1600,1200), Qt.AspectRatioMode.KeepAspectRatio))
    image = reader.read()
    if image.isNull():
        raise ValueError('Nao foi possivel ler esta imagem.')
    return image


class WorkspacePanel(QGraphicsView):
    submitted = pyqtSignal(str)
    attached = pyqtSignal(str)
    pin_requested = pyqtSignal(str)
    closed = pyqtSignal()

    def __init__(self, parent, mode='terminal'):
        super().__init__(parent)
        self.mode = mode
        self.attachment_id = ''
        self.setFrameShape(QGraphicsView.Shape.NoFrame)
        self.setStyleSheet('background:transparent;border:0;')
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.viewport().setAutoFillBackground(False)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scene_model = QGraphicsScene(self)
        self.setScene(self.scene_model)
        self.surface = HudGlassFrame(); self.surface.setObjectName('Surface'); self.surface.setStyleSheet(STYLE)
        self.surface.set_motion_reduced(True)
        self.surface.setProperty('panelMode',mode)
        self.surface.style().unpolish(self.surface);self.surface.style().polish(self.surface)
        layout = QVBoxLayout(self.surface); layout.setContentsMargins(18,16,18,16); layout.setSpacing(12)
        header = QHBoxLayout()
        self.title = QLabel('TERMINAL' if mode=='terminal' else 'EXECUÇÃO')
        self.title.setText('DIEF JARVIS · '+('Terminal' if mode=='terminal' else 'Execução'))
        self.title.setWordWrap(True)
        self.title.setStyleSheet('color:#c6e7ff;font:600 14px "Segoe UI";')
        header.addWidget(self.title); header.addStretch()
        layout.addLayout(header)
        self.status = QLabel('Conversa com o DIEF JARVIS' if mode=='terminal' else 'Aguardando uma operação')
        self.status.setWordWrap(True); self.status.setStyleSheet('color:#97aab5;font:11px "Segoe UI";')
        layout.addWidget(self.status)
        self.transcript = QTextEdit(); self.transcript.setReadOnly(True)
        self.transcript.setAcceptRichText(False); self.transcript.document().setMaximumBlockCount(160)
        self.transcript.setAccessibleName('Conversa' if mode=='terminal' else 'Etapas de execução')
        layout.addWidget(self.transcript,1)
        self.file_label = QLabel(''); self.file_label.setWordWrap(True); layout.addWidget(self.file_label)
        self.image = QLabel();self.image.setAlignment(Qt.AlignmentFlag.AlignCenter);self.image.setMaximumHeight(140);self.image.hide();layout.addWidget(self.image)
        self.input = QLineEdit(); self.input.setPlaceholderText('Mensagem para o DIEF JARVIS')
        self.input.setAccessibleName('Mensagem para o Jarvis'); self.input.setMaxLength(12000)
        if mode=='terminal':
            layout.addWidget(self.input)
            row = QHBoxLayout()
            attach = self.button(QStyle.StandardPixmap.SP_DialogOpenButton,'Anexar foto ou arquivo')
            attach.clicked.connect(self.choose_file); row.addWidget(attach)
            self.pin_button = self.button(QStyle.StandardPixmap.SP_DialogSaveButton,'Fixar foto selecionada')
            self.pin_button.setEnabled(False); self.pin_button.clicked.connect(lambda:self.pin_requested.emit(self.attachment_id))
            row.addWidget(self.pin_button); row.addStretch()
            send = self.button(QStyle.StandardPixmap.SP_ArrowForward,'Enviar mensagem')
            send.clicked.connect(self.send); row.addWidget(send); layout.addLayout(row)
            self.input.returnPressed.connect(self.send)
        else:
            self.input.hide(); self.file_label.hide()
        self.proxy = self.scene_model.addWidget(self.surface)
        self.setAcceptDrops(mode=='terminal')
        self._history = []
        self._reveal = QTimer(self); self._reveal.setInterval(16); self._reveal.timeout.connect(self._step)
        self._progress = 1.0
        self.hide()

    def button(self, icon, label):
        button = QPushButton(); button.setIcon(panel_icon(self.style(),icon))
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setToolTip(label); button.setAccessibleName(label); button.setFixedSize(34,32)
        return button

    def show_panel(self, reduced=False):
        already_visible = self.isVisible()
        if reduced:
            self._reveal.stop()
            self._progress = 1.0
        elif not already_visible:
            self._progress = 0.0
        self.proxy.setOpacity(self._progress)
        self.show(); self.raise_(); self._fit()
        self.surface.set_motion_reduced(reduced)
        if not reduced and self._progress < 1.0: self._reveal.start()

    def close_panel(self):
        self._reveal.stop(); self.hide(); self.closed.emit()

    def _step(self):
        self._progress = min(1.0,self._progress+.065)
        self.proxy.setOpacity(self._progress)
        self._fit()
        if self._progress>=1: self._reveal.stop()

    def _fit(self):
        width=max(180,self.width()-32); height=max(200,self.height()-30)
        self.surface.resize(width,height)
        # Genuine perspective on the interactive proxy; text remains nearly frontal.
        sign=1 if self.mode=='terminal' else -1
        tilt=0.014*sign*(.35+.65*self._progress)
        self.proxy.setTransform(QTransform(1,tilt,0.00007*sign,0,1,0,0,0,1))
        self.scene_model.setSceneRect(self.proxy.sceneBoundingRect().adjusted(-8,-8,8,8))
        self.resetTransform()
        self.fitInView(self.scene_model.sceneRect(),Qt.AspectRatioMode.KeepAspectRatio)

    def resizeEvent(self,event):
        super().resizeEvent(event)
        if hasattr(self,'proxy'): self._fit()

    def hideEvent(self,event):
        self.surface.suspend_motion()
        self._reveal.stop(); super().hideEvent(event)

    def send(self):
        text=self.input.text().strip()
        if text:
            self.input.clear(); self.submitted.emit(text)

    def choose_file(self):
        path,_=QFileDialog.getOpenFileName(self,'Anexar ao terminal','','Fotos e arquivos (*)')
        if path: self.attached.emit(path)

    def dragEnterEvent(self,event):
        urls=event.mimeData().urls()
        if self.mode=='terminal' and len(urls)==1 and urls[0].isLocalFile(): event.acceptProposedAction()

    def dropEvent(self,event):
        urls=event.mimeData().urls()
        if self.mode=='terminal' and len(urls)==1 and urls[0].isLocalFile():
            self.attached.emit(urls[0].toLocalFile()); event.acceptProposedAction()

    def add_line(self,text):
        cursor=self.transcript.textCursor();cursor.movePosition(QTextCursor.MoveOperation.End)
        if not self.transcript.document().isEmpty(): cursor.insertText('\n')
        cursor.insertText(str(text)[:12000]); self.transcript.setTextCursor(cursor);self.transcript.ensureCursorVisible()

    def attachment(self,identifier,path,is_image):
        self.attachment_id=identifier; self.file_label.setText(Path(path).name)
        self.pin_button.setEnabled(is_image)
        self.image.hide()

    def show_image(self,pixmap):
        from PyQt6.QtCore import QSize
        self.image.setPixmap(pixmap.scaled(QSize(max(180,self.surface.width()-40),130),Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))
        self.image.show()

    def record(self,name,state):
        name,_,action=name.partition(':')
        labels={'running':'EM ANDAMENTO','finished':'ETAPA ENCERRADA','failed':'FALHOU','uncertain':'SEM CONFIRMAÇÃO','cancelled':'CANCELADA','pending':'AGUARDANDO CONFIRMAÇÃO',
                'success':'CONCLUÍDA','completed':'CONCLUÍDA','done':'CONCLUÍDA'}
        tool={'app_control':'Aplicativo','powershell_control':'PowerShell','desktop_accessibility':'Controles do aplicativo','gmail_control':'Gmail',
              'whatsapp_web':'WhatsApp','send_message':'Enviar mensagem','weather_report':'Clima',
              'organizer':'Agenda e tarefas','web_search':'Pesquisa','interface_control':'Interface',
              'file_processor':'Processar arquivo','system_status':'Sistema'}.get(name,'Ferramenta')
        actions={'search':'Pesquisar','inspect':'Examinar controles','read':'Ler conteúdo','read_chat':'Ler conversa',
            'fill':'Preencher campo','invoke':'Acionar controle','select':'Selecionar item','open':'Abrir',
            'list':'Listar','scroll':'Rolar conteúdo','press':'Acionar tecla','send':'Enviar',
            'read_thread':'Ler conversa','describe':'Analisar imagem','summarize':'Resumir arquivo'}
        if action in actions:tool+=' · '+actions[action]
        accent='#e7b882' if state in ('failed','uncertain','pending') else '#a7dce2' if state=='running' else '#97aab5'
        self.status.setStyleSheet('color:'+accent+';font:11px "Segoe UI";')
        self.status.setText(tool+' · '+labels.get(state,'ETAPA ENCERRADA'))
        self.add_line(time.strftime('%H:%M:%S')+'  '+self.status.text())
        self._history=(self._history+[{'tool':tool,'state':state}])[-40:]

