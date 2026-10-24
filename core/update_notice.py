"""In-session update notice, deferred until the assistant is idle."""
import os
from pathlib import Path

from PyQt6.QtCore import QObject, QTimer
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QDialog, QLabel, QPushButton, QVBoxLayout, QHBoxLayout

from core.distribution import atomic_json
from core.release_identity import VERSION
from core.update_watch import UpdateWatch


class UpdateNotice(QObject):
    def __init__(self, window):
        super().__init__(window)
        self.window=window
        self.pending=None
        self.dialog=None
        self.watch=UpdateWatch(VERSION)
        self.timer=QTimer(self)
        self.timer.timeout.connect(self.poll)
        if os.environ.get('DIEF_UPDATE_REQUEST') and os.environ.get('QT_QPA_PLATFORM')!='offscreen':
            self.timer.start(60000)

    def poll(self):
        release=self.watch.tick()
        if release:self.pending=release
        if not self.pending or self.dialog or not self.window.isVisible():return
        veil=getattr(self.window,'_opening_veil',None)
        hud=getattr(self.window,'hud',None)
        if veil and veil.isVisible():return
        if hud and (hud.speaking or hud.state in ('THINKING','PROCESSING','SPEAKING')):return
        self.show_notice(self.pending)

    def show_notice(self, release):
        self.pending=None
        dialog=QDialog(self.window)
        dialog.setFont(QFont('Segoe UI',10))
        self.dialog=dialog
        dialog.setWindowTitle('Atualizacao do DIEF JARVIS')
        dialog.setMinimumWidth(420)
        dialog.setStyleSheet('QDialog {background:#071621;color:#e5f8ff;} QLabel {color:#e5f8ff;} QPushButton {background:#12354a;color:#e5f8ff;border:1px solid #42caff;border-radius:7px;padding:10px;}')
        layout=QVBoxLayout(dialog)
        label=QLabel('Nova versao disponivel: '+release['version']+'\n\nReinicie para instalar a atualizacao. Seus dados e conexoes serao preservados.')
        label.setWordWrap(True);layout.addWidget(label)
        row=QHBoxLayout();layout.addLayout(row)
        later=QPushButton('Mais tarde');install=QPushButton('Reiniciar para atualizar')
        row.addWidget(later);row.addWidget(install)
        later.clicked.connect(dialog.close)
        def complete_restart():
            try:
                request=Path(os.environ['DIEF_UPDATE_REQUEST'])
                root=Path(os.environ['DIEF_MANAGED_ROOT']).resolve()
                if request.resolve().parent!=root/'sessions':raise ValueError('Destino de reinicializacao invalido')
                atomic_json(request,{'version':release['version']})
            except Exception:
                label.setText('Nao foi possivel preparar a reinicializacao. Feche e abra o Jarvis para atualizar.');return
            dialog.close();self.window.close()
        def restart():
            prepare=getattr(self.window,'on_prepare_update',None)
            try:future=prepare() if callable(prepare) else None
            except Exception as error:
                label.setText(str(error));return
            if future is None:complete_restart();return
            install.setEnabled(False);later.setEnabled(False)
            label.setText('Salvando o contexto da conversa antes de reiniciar...')
            def await_saved():
                if not dialog.isVisible():return
                if not future.done():QTimer.singleShot(100,await_saved);return
                try:future.result()
                except Exception as error:
                    label.setText('Reinicio adiado: '+str(error))
                    install.setEnabled(True);later.setEnabled(True);return
                complete_restart()
            QTimer.singleShot(100,await_saved)
        install.clicked.connect(restart)
        def finished(*_):
            self.dialog=None
            dialog.deleteLater()
        dialog.finished.connect(finished)
        dialog.show()
        announce=getattr(self.window,'on_update_available',None)
        if callable(announce):
            try:announce(release['version'])
            except Exception:pass
