"""Read-only personality telemetry, in the approved observatory material."""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget,QLabel,QProgressBar,QVBoxLayout,QHBoxLayout,QGridLayout,QLayout
from core.personality import BASE,LABELS,snapshot


class PersonalityView(QWidget):
    def __init__(self,parent=None):
        super().__init__(parent)
        self._revision=None;self._columns=0;self.meters={};self.sources={};self.cells=[]
        self.setStyleSheet('''
            QLabel { background:transparent; color:#d9f1ff; font-size:12px; }
            QLabel[muted="true"] { color:#8fb8d0; font-size:10px; }
            QProgressBar { background:#031321; border:1px solid #245b7c; border-radius:4px; color:#effaff; font-size:10px; text-align:center; }
            QProgressBar::chunk { background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #0967a4,stop:.75 #1da8e3,stop:1 #8ddfff); border-radius:3px; }
        ''')
        self.outer=QVBoxLayout(self);self.outer.setContentsMargins(0,0,0,0);self.outer.setSpacing(10)
        self.outer.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        self.grid=QGridLayout();self.grid.setHorizontalSpacing(28);self.grid.setVerticalSpacing(12);self.outer.addLayout(self.grid)
        edges={'familiarity':('Formal','Próximo'),'humor':('Discreto','Irônico'),
            'initiative':('Reativo','Propositivo'),'detail':('Objetivo','Explicativo')}
        for key in BASE:
            cell=QWidget();layout=QVBoxLayout(cell);layout.setContentsMargins(0,0,0,0);layout.setSpacing(4)
            row=QHBoxLayout();name=QLabel(LABELS[key]);row.addWidget(name);row.addStretch()
            source=QLabel();source.setProperty('muted',True);row.addWidget(source);self.sources[key]=source;layout.addLayout(row)
            meter=QProgressBar();meter.setRange(0,100);meter.setFormat('%v%');meter.setFixedHeight(16)
            meter.setFocusPolicy(Qt.FocusPolicy.NoFocus);meter.setAccessibleName(LABELS[key]+' atual, somente leitura')
            self.meters[key]=meter;layout.addWidget(meter)
            scale=QHBoxLayout()
            for index,text in enumerate(edges[key]):
                if index:scale.addStretch()
                label=QLabel(text);label.setProperty('muted',True);scale.addWidget(label)
            layout.addLayout(scale);self.cells.append(cell)
        self.status=QLabel();self.status.setWordWrap(True);self.status.setProperty('muted',True)
        self.status.setTextFormat(Qt.TextFormat.PlainText);self.outer.addWidget(self.status)
        self._arrange(2);self.refresh()

    def _arrange(self,columns):
        if columns==self._columns:return
        self._columns=columns
        while self.grid.count():self.grid.takeAt(0)
        for index,cell in enumerate(self.cells):self.grid.addWidget(cell,index//columns,index%columns)
        self.grid.setColumnStretch(0,1);self.grid.setColumnStretch(1,1 if columns==2 else 0)

    def resizeEvent(self,event):
        super().resizeEvent(event);self._arrange(1 if self.width()<520 else 2)

    def refresh(self):
        state=snapshot();key=(state['available'],state['revision'])
        if key==self._revision:return
        self._revision=key
        for dimension,meter in self.meters.items():
            meter.setVisible(state['available'])
            item=state['dimensions'][dimension]
            meter.setValue(item['value'])
            self.sources[dimension].setText({'baseline':'Inicial','inferred':'Aprendido','explicit':'Preferência explícita'}[item['source']] if state['available'] else 'Indisponível')
        if not state['available']:
            self.status.setText('Não foi possível ler o perfil. Os dados anteriores foram preservados.');return
        if state['events']:
            event=state['events'][-1]
            dimension=LABELS.get(event.get('dimension'),'Tratamento')
            origin='preferência explícita' if event.get('source')=='explicit' else 'ajuste gradual'
            self.status.setText('Último ajuste: '+dimension.lower()+' · '+origin+'.')
        else:self.status.setText('Personalidade inicial · JARVIS')
        if state.get('address'):self.status.setText(self.status.text()+' Tratamento: '+state['address']+'.')
