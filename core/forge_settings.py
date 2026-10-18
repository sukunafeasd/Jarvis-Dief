"""Connection editor for the independent FORJA engine; no secrets enter WebEngine."""
import threading
import webbrowser
from PyQt6.QtCore import pyqtSignal,QTimer,Qt
from PyQt6.QtWidgets import QWidget,QVBoxLayout,QFormLayout,QComboBox,QLineEdit,QPushButton,QLabel,QStyle,QFileDialog


class ForgeConnection(QWidget):
    completed=pyqtSignal(object)

    def __init__(self,hub):
        super().__init__();self.hub=hub;self.busy=False;self.setProperty('connectionTile',True)
        from core.settings_connections import ConnectionRow
        layout=QVBoxLayout(self);layout.setContentsMargins(0,0,0,0)
        self.row=ConnectionRow('forge','Codex / Modo Forja','Motor de criacao separado da voz e da IA principal.',QStyle.StandardPixmap.SP_ComputerIcon,self.test,self.toggle)
        layout.addWidget(self.row)
        self.editor=QWidget();form=QFormLayout(self.editor);form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        self.auth=QComboBox();self.auth.addItem('Conectar conta ChatGPT','chatgpt');self.auth.addItem('Chave OpenAI API','apiKey')
        form.addRow('Autenticacao',self.auth)
        self.key=QLineEdit();self.key.setEchoMode(QLineEdit.EchoMode.Password);self.key.setPlaceholderText('Chave protegida neste computador')
        self.key.setAccessibleName('Chave OpenAI exclusiva da Forja');form.addRow('Chave OpenAI',self.key)
        self.model=QComboBox();self.model.setEditable(False);self.model.addItem('Modelo padrao da conta','')
        form.addRow('Modelo de criacao',self.model)
        self.connect=QPushButton('Conectar');self.connect.clicked.connect(self.authorize);form.addRow(self.connect)
        self.notice=QLabel('Login ChatGPT e chave API possuem limites e formas de cobranca diferentes. A chave da Forja nao substitui a chave Gemini nem a voz Fish.')
        self.notice.setWordWrap(True);self.notice.setTextFormat(Qt.TextFormat.PlainText);form.addRow(self.notice)
        self.editor.hide();layout.addWidget(self.editor)
        self.completed.connect(self._done)
        self._auth_edited=False;self._model_edited=False;self._account_type=''
        self.auth.activated.connect(self._edit_auth);self.model.activated.connect(self._edit_model)
        self.auth.currentIndexChanged.connect(lambda:self.key.setEnabled(self.auth.currentData()=='apiKey'))
        self.key.setEnabled(False);self.row.set_state('disconnected',action='Conectar')
        self.timer=QTimer(self);self.timer.setInterval(2500);self.timer.timeout.connect(self.refresh)

    def _edit_auth(self,*_):self._auth_edited=True
    def _edit_model(self,*_):self._model_edited=True

    def showEvent(self,event):
        super().showEvent(event);self.timer.start();self.refresh()

    def hideEvent(self,event):
        self.timer.stop();super().hideEvent(event)

    def runtime(self):
        from core.forge_host import runtime_for
        return runtime_for(self.hub.window)

    def toggle(self):self.editor.setVisible(not self.editor.isVisible())

    def refresh(self):
        if self.busy or not self.isVisible():return
        runtime=getattr(self.hub.window,'_forge_runtime',None)
        if runtime:self._done(runtime.status())

    def test(self):
        if self.row.status.text() not in ('Conectado','Verificado'):
            self.editor.show()
        self._start(lambda:self.runtime().connect())

    def authorize(self):
        mode=self.auth.currentData();key=self.key.text().strip();model=self.model.currentData() or ''
        reuse_account=mode==self._account_type and not key
        if mode=='apiKey' and not key and not reuse_account:
            self.notice.setText('Informe a chave OpenAI para conectar por API.');return
        self.key.clear();self._auth_edited=False;self._model_edited=False
        self._start(lambda:self.runtime().connect(auth_mode=None if reuse_account else mode,key=key,model=model))

    def _start(self,callback):
        if self.busy:return
        self.busy=True;self.row.set_state('testing');self.connect.setEnabled(False)
        def work():
            try:result=callback()
            except Exception as error:result={'ok':False,'error':'Conexao da Forja indisponivel ('+type(error).__name__+').'}
            try:self.completed.emit(result)
            except RuntimeError:pass
        threading.Thread(target=work,name='ForgeConnection',daemon=True).start()

    def _done(self,result):
        if getattr(self.hub,'_closed',False):return
        self.busy=False;self.connect.setEnabled(True)
        if not isinstance(result,dict):result={'error':'Resposta de conexao invalida.'}
        url=result.get('auth_url') or result.get('authUrl')
        if url:
            from urllib.parse import urlparse
            parsed=urlparse(url)
            if parsed.scheme=='https' and parsed.hostname in ('auth.openai.com','chatgpt.com'):
                webbrowser.open(url)
        connected=bool(result.get('connected') or result.get('authenticated') and result.get('transport')=='ready')
        account=result.get('account') or {}
        if not isinstance(account,dict):account={}
        account_type=account.get('type','')
        if account_type in ('apiKey','chatgpt'):
            self._account_type=account_type
            if not self._auth_edited:self.auth.setCurrentIndex(self.auth.findData(account_type))
        elif 'account' in result:self._account_type=''
        identity=account.get('email') or account.get('type') or ''
        self.row.title.setText('Codex / Modo Forja')
        self.row.set_state('connected' if connected else 'auth_required' if url else 'error' if result.get('error') else 'disconnected',
                           result.get('message') or result.get('error') or (str(identity)+' · Motor pronto para a Forja.' if connected and identity else 'Motor pronto para a Forja.' if connected else 'Conecte uma conta ou chave OpenAI para criar.'),
                           'Testar conexao' if connected else 'Conectar')
        self.notice.setText(result.get('message') or result.get('error') or ('Conexao verificada.' if connected else 'Conclua a autorizacao no navegador e teste novamente.'))
        models=result.get('models') or []
        if models:
            current=self.model.currentData() if self._model_edited else result.get('model',self.model.currentData())
            self.model.clear();self.model.addItem('Modelo padrao da conta','')
            for model in models:
                identifier=model.get('id') or model.get('model') if isinstance(model,dict) else str(model)
                if identifier:self.model.addItem(str(identifier),str(identifier))
            if current and self.model.findData(current)<0:self.model.addItem(str(current),str(current))
            index=self.model.findData(current)
            if index>=0:self.model.setCurrentIndex(index)
