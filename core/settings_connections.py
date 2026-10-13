"""Lista de conexoes com estados verificaveis e destinos explicitos."""
import time
from PyQt6.QtCore import Qt,QSize
from PyQt6.QtWidgets import (QWidget,QFrame,QLabel,QPushButton,QGridLayout,QHBoxLayout,QVBoxLayout,
    QFormLayout,QLineEdit,QScrollArea,QStyle)
from core.settings_style import settings_icon
from core.hud_glass import HudGlassFrame
from core.connection_states import STATES,resolve
from core.locale_pt_br import tool_label
from core.resource_policy import EXTERNAL,LOCAL,local_status,external_status


class ConnectionRow(HudGlassFrame):
    def __init__(self,identifier,title,detail,icon,callback,configure=None,parent=None):
        super().__init__(parent);self.identifier=identifier;self.setObjectName('connectionRow')
        self.grid=QGridLayout(self);self.grid.setContentsMargins(14,18,14,18);self.grid.setHorizontalSpacing(16);self.grid.setVerticalSpacing(7)
        self.icon=QLabel();self.icon.setPixmap(settings_icon(self.style().standardIcon(icon)).pixmap(28,28));self.icon.setFixedSize(36,36)
        self.title=QLabel(title);self.title.setObjectName('connectionTitle');self.title.setTextFormat(Qt.TextFormat.PlainText)
        self.title.setWordWrap(True)
        self.detail=QLabel(detail);self.detail.setObjectName('settingsMeta');self.detail.setTextFormat(Qt.TextFormat.PlainText);self.detail.setWordWrap(True)
        self.status=QLabel();self.status.setObjectName('connectionState');self.status.setWordWrap(True);self.status.setMinimumWidth(108)
        self.action=QPushButton();self.action.setIconSize(QSize(16,16));self.action.setMinimumWidth(170);self.action.clicked.connect(callback)
        self.action.setAccessibleName('Conectar ou testar '+title);self.action.setCursor(Qt.CursorShape.PointingHandCursor)
        self.actions=QWidget();actions=QHBoxLayout(self.actions);actions.setContentsMargins(0,0,0,0);actions.setSpacing(8);actions.addWidget(self.action)
        self.configure=None
        self.reauthorize=None
        if configure:
            self.configure=QPushButton();self.configure.setObjectName('rowConfigure');self.configure.setIcon(settings_icon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView)))
            self.configure.setCursor(Qt.CursorShape.PointingHandCursor)
            self.configure.setFixedSize(36,40);self.configure.setToolTip('Configurar '+title);self.configure.setAccessibleName('Configurar '+title)
            self.configure.clicked.connect(configure);actions.addWidget(self.configure)
        self._compact=None;self.relayout(False);self.set_state('disconnected')

    def relayout(self,compact):
        if self._compact==compact:return
        self._compact=compact
        self.actions.layout().setDirection(QHBoxLayout.Direction.TopToBottom if compact else QHBoxLayout.Direction.LeftToRight)
        for widget in (self.icon,self.title,self.detail,self.status,self.actions):self.grid.removeWidget(widget)
        self.grid.setColumnStretch(1,1)
        if compact:
            self.grid.addWidget(self.icon,0,0,2,1,Qt.AlignmentFlag.AlignTop)
            self.grid.addWidget(self.title,0,1);self.grid.addWidget(self.status,0,2)
            self.grid.addWidget(self.detail,1,1,1,2);self.grid.addWidget(self.actions,2,1,1,2,Qt.AlignmentFlag.AlignLeft)
        else:
            self.grid.addWidget(self.icon,0,0,2,1,Qt.AlignmentFlag.AlignTop)
            self.grid.addWidget(self.title,0,1);self.grid.addWidget(self.detail,1,1)
            self.grid.addWidget(self.status,0,2,2,1);self.grid.addWidget(self.actions,0,3,2,1)

    def resizeEvent(self,event):
        self.relayout(self.width()<720);super().resizeEvent(event)

    def set_state(self,state,detail=None,action=None):
        label,tone,default_action=STATES[state]
        if self.status.text()!=label:
            self.status.setText(label);self.status.setProperty('tone',tone);self.status.style().unpolish(self.status);self.status.style().polish(self.status)
        text=action or default_action
        self.action.setText(text)
        pixmap=QStyle.StandardPixmap.SP_BrowserReload if state in ('connected','pending','error','available','awaiting') else QStyle.StandardPixmap.SP_ArrowForward
        self.action.setIcon(settings_icon(self.style().standardIcon(pixmap)))
        self.action.setToolTip(text+' · '+self.title.text());self.action.setEnabled(state not in ('connecting','testing'))
        if self.configure:self.configure.setEnabled(state not in ('connecting','testing'))
        if self.reauthorize:
            self.reauthorize.setEnabled(state not in ('connecting','testing','broken','disabled'))
            self.reauthorize.setVisible(state in ('connected','pending','error','auth_required','awaiting'))
        if detail is not None and self.detail.text()!=detail:self.detail.setText(detail)
        self.setAccessibleName(self.title.text()+' · '+label)

    def add_reauthorization(self,callback,label='Reconectar'):
        self.reauthorize=QPushButton(label)
        self.reauthorize.setIcon(settings_icon(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowForward)))
        self.reauthorize.setToolTip('Autorizar novamente ou escolher outra conta · '+self.title.text())
        self.reauthorize.setAccessibleName('Reconectar '+self.title.text())
        self.reauthorize.clicked.connect(callback)
        self.actions.layout().insertWidget(1,self.reauthorize)
        self.reauthorize.hide()


class ConnectionsPage(QScrollArea):
    def __init__(self,hub):
        super().__init__();self.hub=hub;self.rows={};self.local_gmail={};self._local_at=0;self._probed=False;self._external_local={}
        self.setWidgetResizable(True);self.setFrameShape(QFrame.Shape.NoFrame)
        self.body=QWidget();self.setWidget(self.body);self.body.setMaximumWidth(1080)
        self.layout=QVBoxLayout(self.body);self.layout.setContentsMargins(0,0,12,24);self.layout.setSpacing(0)
        hub.connections=QLabel('');hub.connections.setObjectName('settingsMeta');hub.connections.setWordWrap(True);self.layout.addWidget(hub.connections)
        hub.connection_notice=QLabel();hub.connection_notice.setObjectName('connectionNotice');hub.connection_notice.setWordWrap(True);hub.connection_notice.setTextFormat(Qt.TextFormat.PlainText);self.layout.addWidget(hub.connection_notice)
        hub.connection_buttons=[]
        self.section('Contas')
        self.add('ai','IA Gemini','Conexão de voz e inteligência.',QStyle.StandardPixmap.SP_ComputerIcon,self.activate_ai,lambda:hub.open_page('ai'))
        self.add('gmail','Gmail','Autorização Google · somente leitura',QStyle.StandardPixmap.SP_FileDialogDetailedView,
                 lambda:self.activate('gmail'),lambda:self.show_gmail_editor())
        self.build_gmail_editor()
        self.add('whatsapp','WhatsApp Web','Sessão vinculada pelo código QR',QStyle.StandardPixmap.SP_MessageBoxInformation,
                 lambda:self.activate('whatsapp'),hub.connect_whatsapp)
        self.rows['gmail'].add_reauthorization(hub.connect_gmail)
        self.rows['whatsapp'].add_reauthorization(hub.connect_whatsapp)
        self.section('Dispositivo')
        self.add('iphone','iPhone · Vincular ao Celular','Pareamento e permissões gerenciados no Windows.',QStyle.StandardPixmap.SP_DriveNetIcon,hub.connect_iphone)
        self.section('Ferramentas e plugins')
        self.plugins_area=QWidget();self.plugins_layout=QVBoxLayout(self.plugins_area);self.plugins_layout.setContentsMargins(0,0,0,0);self.plugins_layout.setSpacing(0);self.layout.addWidget(self.plugins_area)
        links=QHBoxLayout();links.setContentsMargins(0,20,0,0)
        for text,callback in (('Gerenciar plugins',lambda:hub.open_overlay(hub.window._open_plugin_manager)),('Acesso remoto',lambda:hub.open_overlay(hub.window._open_remote))):
            button=QPushButton(text);button.clicked.connect(callback);links.addWidget(button)
        links.addStretch();self.layout.addLayout(links);self.layout.addStretch()

    def section(self,text):
        title=QLabel(text);title.setObjectName('settingsGroup');self.layout.addWidget(title)

    def activate_ai(self):
        if self.states.get('ai') in ('connected','error'):self.hub.check_ai()
        else:self.hub.open_page('ai')

    def add(self,identifier,title,detail,icon,callback,configure=None):
        row=ConnectionRow(identifier,title,detail,icon,callback,configure);self.rows[identifier]=row;self.layout.addWidget(row)
        row.set_motion_reduced(self.hub._config().get('reduce_motion',False))
        self.hub.connection_buttons.append(row.action)
        if row.configure:self.hub.connection_buttons.append(row.configure)
        return row

    def build_gmail_editor(self):
        from core import gmail_connection as gmail
        hub=self.hub;self.gmail_editor=QWidget();self.gmail_editor.setObjectName('credentialsEditor')
        outer=QVBoxLayout(self.gmail_editor);outer.setContentsMargins(48,12,16,20)
        heading=QLabel('Credenciais do Gmail');heading.setObjectName('settingsGroup');outer.addWidget(heading)
        form=QFormLayout();form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows);form.setSpacing(12);outer.addLayout(form)
        hub.gmail_email=QLineEdit(gmail.expected_account() or gmail.status().get('account_email',''));hub.gmail_email.setPlaceholderText('Conta que deseja conectar')
        hub.gmail_email.setAccessibleName('E-mail da conta Gmail');form.addRow('E-mail da conta',hub.gmail_email)
        hub.gmail_client=QLineEdit(gmail.credential_client_id());hub.gmail_client.setPlaceholderText('Identificador do cliente OAuth do Google');form.addRow('Identificador do cliente',hub.gmail_client)
        hub.gmail_secret=QLineEdit();hub.gmail_secret.setEchoMode(QLineEdit.EchoMode.Password)
        hub.gmail_secret.setPlaceholderText('Credencial salva' if gmail.CREDENTIALS.exists() else 'Segredo do cliente OAuth do Google');form.addRow('Segredo do cliente',hub.gmail_secret)
        hub.gmail_secret.setAccessibleName('Segredo do cliente Gmail');hub.gmail_secret.setToolTip('Não é a senha do Gmail nem a chave da IA. A credencial salva não é exibida.')
        hub.gmail_account=QLabel();hub.gmail_account.setWordWrap(True);hub.gmail_account.setObjectName('settingsMeta');outer.addWidget(hub.gmail_account)
        buttons=QVBoxLayout()
        buttons.setSpacing(8)
        for text,callback in (('Importar JSON OAuth',hub.import_gmail_credentials),('Salvar credencial',hub.save_gmail_credentials),('Autorizar conta',hub.connect_gmail)):
            button=QPushButton(text);button.clicked.connect(callback);buttons.addWidget(button);hub.connection_buttons.append(button)
        outer.addLayout(buttons);self.layout.addWidget(self.gmail_editor);self.gmail_editor.hide()

    def show_gmail_editor(self):
        self.gmail_editor.setVisible(not self.gmail_editor.isVisible())
        if self.gmail_editor.isVisible():self.ensureWidgetVisible(self.gmail_editor)

    def activate(self,provider):
        row=self.rows[provider];state=self.states.get(provider,'disconnected')
        if state=='disabled':
            self.hub.enable_plugin('gmail_control' if provider=='gmail' else 'whatsapp_web');return
        if state=='broken':
            self.hub.open_overlay(self.hub.window._open_plugin_manager);return
        if state in ('connected','pending','error','awaiting'):
            (self.hub.check_gmail if provider=='gmail' else self.hub.check_whatsapp)();return
        if provider=='gmail':
            from core import gmail_connection as gmail
            if not gmail.CREDENTIALS.exists():
                self.gmail_editor.show();self.ensureWidgetVisible(self.gmail_editor)
                self.hub.connection_notice.setText('Importe a credencial OAuth do Google ou preencha os campos para autorizar a conta.');return
            self.hub.connect_gmail()
        else:self.hub.connect_whatsapp()

    def refresh(self,plugins,ai):
        from core import gmail_connection as gmail
        from core.whatsapp_web import PROFILE
        now=time.monotonic()
        if not self.local_gmail or now-self._local_at>5:
            self.local_gmail=gmail.status();self._local_at=now
        hub=self.hub;mapping={p['name']:p for p in plugins};self.states={}
        for provider,plugin_name,local in (('gmail','gmail_control',self.local_gmail),('whatsapp','whatsapp_web',{'saved_session':PROFILE.exists()}),('ai','',ai),('iphone','',{})):
            checked=hub._connection_checks.get(provider)
            plugin=mapping.get(plugin_name)
            state=resolve(provider,local,checked,plugin);self.states[provider]=state
            if provider=='gmail':
                account=local.get('account_email','') or 'Conta não identificada'
                detail=account+' · somente leitura' if local.get('connected') else 'Autorização Google · somente leitura'
                hub.gmail_account.setText('Conta autorizada: '+(local.get('account_email') or 'não conectada'))
            elif provider=='whatsapp':detail='Sessão própria do Jarvis · WhatsApp Web'
            elif provider=='ai':detail='Modelo: '+str(ai.get('model','--'))
            else:detail='O Windows confirma o pareamento. Não há teste remoto de conexão do iPhone neste projeto.'
            if checked.get('message'):detail=checked['message']
            if checked.get('checked'):detail+=' · '+checked['checked']
            action='Configurar IA' if provider=='ai' and state=='disconnected' else None
            self.rows[provider].set_state(state,detail,action)
        self.refresh_plugins(mapping)
        count=sum(state=='connected' for state in self.states.values())
        available=sum(state=='available' for state in self.states.values())
        hub.connections.setText(f'{count} conexões confirmadas · {available} ferramentas locais disponíveis')
        busy=bool(hub._connection_checks.get('gmail').get('busy'))
        for field in (hub.gmail_email,hub.gmail_client,hub.gmail_secret):field.setEnabled(not busy)
        for button in hub.connection_buttons:
            if self.gmail_editor.isAncestorOf(button):button.setEnabled(not busy)

    def refresh_plugins(self,mapping):
        current={name for name in mapping if name not in ('gmail_control','whatsapp_web')}
        for name in list(self.rows):
            if name.startswith('plugin:') and name[7:] not in current:
                row=self.rows.pop(name);self.plugins_layout.removeWidget(row);row.deleteLater()
        for name in sorted(current):
            external=name in EXTERNAL
            provider='desktop' if name=='desktop_accessibility' else 'plugin:'+name
            if external:provider=name
            identifier='plugin:'+name
            if identifier not in self.rows:
                row=ConnectionRow(identifier,tool_label(name),'Ferramenta instalada',QStyle.StandardPixmap.SP_ComputerIcon,
                    lambda checked=False,n=name:self.hub.activate_plugin(n),
                    (lambda checked=False,n=name:self.hub.open_plugin_settings(n)) if self.has_settings(name) else None)
                if external:row.add_reauthorization(lambda checked=False,n=name:self.hub.reauthorize_plugin(n))
                self.rows[identifier]=row;self.plugins_layout.addWidget(row)
            checked=self.hub._connection_checks.get(provider);plugin=mapping[name]
            local={}
            if external:
                cached=self._external_local.get(name,{})
                if time.monotonic()-cached.get('at',0)>5:
                    local=external_status(name)
                    self._external_local[name]={'at':time.monotonic(),'value':local}
                else:local=cached.get('value',{})
            elif name in LOCAL:
                cached=self._external_local.get(name,{})
                if time.monotonic()-cached.get('at',0)>5:
                    local=local_status(name);self._external_local[name]={'at':time.monotonic(),'value':local}
                else:local=cached.get('value',{})
            state=resolve(provider,local,checked,plugin)
            detail=checked.get('message') or local.get('detail') or 'Plugin instalado; consulte suas configuracoes.'
            if external:detail=checked.get('message') or local.get('account') or ('Verificando a conta salva em segundo plano.' if state in ('pending','testing') else 'Autorização da conta necessária; configure e conecte este serviço.')
            action='Testar ferramenta' if name in LOCAL and state in ('local','available') else 'Configurar e conectar' if external and state=='disconnected' and not local.get('configured') else None
            self.rows[identifier].set_state(state,detail,action)
            self.states[identifier]=state

    def has_settings(self,name):
        sections=self.hub.window.get_plugin_settings() if self.hub.window.get_plugin_settings else []
        return any(section.get('plugin')==name or section.get('namespace')==name for section in sections)
