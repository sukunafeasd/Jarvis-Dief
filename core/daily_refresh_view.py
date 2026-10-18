"""Small, non-interactive progress surface for actual daily source queries."""
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QFrame, QLabel, QProgressBar, QVBoxLayout
from core.hud_glass import HudGlassFrame
from core.auxiliary_theme import SURFACE_STYLE


class DailyRefreshView(HudGlassFrame):
    def __init__(self, parent):
        super().__init__(parent)
        self.transaction = None
        self.setObjectName('dailyRefresh')
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setStyleSheet(SURFACE_STYLE+'''
            QFrame#dailyRefresh { background: transparent; border:0; }
            QLabel { background: transparent; border: none; color: #e8f8ff; font-family: "Segoe UI"; }
        ''')
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(7)
        self.title = QLabel('Atualizando o dia', self)
        self.title.setStyleSheet('font-size: 14px; font-weight: 600;')
        self.detail = QLabel('Preparando consulta', self)
        self.detail.setWordWrap(True)
        self.detail.setStyleSheet('color: #9edce8; font-size: 12px;')
        self.bar = QProgressBar(self)
        self.bar.setFixedHeight(5)
        self.bar.setTextVisible(False)
        self.footer = QLabel('', self)
        self.footer.setStyleSheet('color: #91aab8; font-size: 11px;')
        for widget in (self.title, self.detail, self.bar, self.footer):
            layout.addWidget(widget)
        self.dismiss = QTimer(self)
        self.dismiss.setSingleShot(True)
        self.dismiss.timeout.connect(self.hide)
        self.hide()

    def update_model(self, model):
        self.dismiss.stop()
        self.transaction = model['id']
        total = max(0, int(model.get('total', 0)))
        completed = max(0, min(total, int(model.get('completed', 0))))
        items = model.get('items') or []
        working = [str(item.get('title', 'Fonte')) for item in items if item.get('status') == 'working']
        warnings = sum(item.get('status') == 'warning' for item in items)
        self.title.setText('Atualizando o dia')
        self.detail.setText(('Consultando: ' + ' / '.join(working[:2])) if working else
                            ('Consultas concluídas' if total else 'Preparando consulta'))
        self.bar.setRange(0, total)
        self.bar.setValue(completed)
        self.footer.setText(f'{completed} de {total} fontes verificadas' +
                            (f'  ·  {warnings} indisponíveis' if warnings else '') if total else 'Aguardando as fontes reais')
        self.reposition()
        self.show()
        self.raise_()

    def finish(self, transaction, failed=False):
        if transaction != self.transaction:
            return
        if failed:
            self.title.setText('Atualização interrompida')
            self.detail.setText('Não foi possível concluir. Você pode pedir para tentar novamente.')
            self.bar.setRange(0, 1)
            self.bar.setValue(0)
            self.dismiss.start(4000)
        else:
            self.hide()

    def reposition(self):
        stage = self.parentWidget()
        width = max(1, min(380, stage.width() - 32))
        height = min(126, max(1, stage.height() - 24))
        self.setGeometry((stage.width() - width) // 2, max(12, stage.height() - height - 115), width, height)
