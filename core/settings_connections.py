"""Lista de conexoes com estados verificaveis e destinos explicitos."""
import time
from PyQt6.QtCore import Qt,QSize
from PyQt6.QtWidgets import (QWidget,QFrame,QLabel,QPushButton,QGridLayout,QHBoxLayout,QVBoxLayout,
    QFormLayout,QLineEdit,QScrollArea,QStyle,QTabBar,QStackedWidget)
from core.settings_style import settings_icon
from core.hud_glass import PinnedPreviewFrame
from core.connection_states import STATES,resolve
from core.locale_pt_br import tool_label
from core.resource_policy import EXTERNAL,LOCAL,local_status,external_status
from core.settings_components import TileLayout, StatusLabel
from core.ui_assets import service_badge, glyph


class ConnectionRow(PinnedPreviewFrame):
    def __init__(self,identifier,title,detail,icon,callback,configure=None,parent=None):
        super().__init__(parent);self.identifier=identifier;self.setObjectName('connectionRow');self.setProperty('connectionTile',True)
        self.set_accent('#65c6ff')
        self.grid=QGridLayout(self);self.grid.setContentsMargins(18,16,18,16);self.grid.setHorizontalSpacing(10);self.grid.setVerticalSpacing(5)
        self.icon=QLabel();self.icon.setPixmap(service_badge(identifier));self.icon.setFixedSize(54,54)
        self.title=QLabel(title);self.title.setObjectName('connectionTitle');self.title.setTextFormat(Qt.TextFormat.PlainText)
        self.title.setWordWrap(True)
        self.detail=QLabel(detail);self.detail.setObjectName('settingsMeta');self.detail.setTextFormat(Qt.TextFormat.PlainText);self.detail.setWordWrap(True)
        self.status=StatusLabel();self.status.setObjectName('connectionState');self.status.setWordWrap(True)
        self.action=QPushButton();self.action.setIconSize(QSize(14,14));self.action.clicked.connect(callback)
        self.action.setAccessibleName('Conectar ou testar '+title);self.action.setCursor(Qt.CursorShape.PointingHandCursor)
        self.actions=QWidget();actions=QHBoxLayout(self.actions);actions.setContentsMargins(0,0,0,0);actions.setSpacing(8);actions.addWidget(self.action)
        self.configure=None
        self.reauthorize=None
        if configure:
            self.configure=QPushButton();self.configure.setObjectName('rowConfigure');self.configure.setIcon(glyph('sliders-horizontal'))
            self.configure.setCursor(Qt.CursorShape.PointingHandCursor)
            self.configure.setFixedSize(30,30);self.configure.setToolTip('Configurar '+title);self.configure.setAccessibleName('Configurar '+title)
            self.configure.clicked.connect(configure);actions.addWidget(self.configure)
        self._compact=None;self.relayout(False);self.set_state('disconnected')

    def relayout(self,compact):
        if self._compact==compact:return
        self._compact=compact
        self.actions.layout().setDirection(QHBoxLayout.Direction.LeftToRight)
        for widget in (self.icon,self.title,self.detail,self.status,self.actions):self.grid.removeWidget(widget)
        self.grid.setColumnStretch(1,1)
        if compact:
            self.grid.addWidget(self.icon,0,0,3,1,Qt.AlignmentFlag.AlignTop)
            self.grid.addWidget(self.title,0,1);self.grid.addWidget(self.detail,1,1)
            self.grid.addWidget(self.status,2,1);self.grid.addWidget(self.actions,3,0,1,2,Qt.AlignmentFlag.AlignRight)
        else:
            self.grid.addWidget(self.icon,0,0,3,1,Qt.AlignmentFlag.AlignTop)
            self.grid.addWidget(self.title,0,1);self.grid.addWidget(self.detail,1,1)
            self.grid.addWidget(self.status,2,1);self.grid.addWidget(self.actions,0,2,3,1)
        self.updateGeometry()

    def resizeEvent(self,event):
        self.relayout(self.width()<650);super().resizeEvent(event)

    def set_state(self,state,detail=None,action=None):
        label,tone,default_action=STATES[state]
        key=(state,detail if detail is not None else self.detail.text(),action or default_action,self.title.text())
        if getattr(self,'_state_key',None)==key:return
        if self.status.text()!=label or self.status.property('tone')!=tone:
            self.status.setText(label);self.status.setProperty('tone',tone);self.status.style().unpolish(self.status);self.status.style().polish(self.status)
        text=action or default_action
        self.action.setText(text)
        pixmap=QStyle.StandardPixmap.SP_BrowserReload if state in ('connected','pending','error','available','awaiting') else QStyle.StandardPixmap.SP_ArrowForward
        self.action.setIcon(glyph('refresh-cw' if state in ('connected','pending','error','available','awaiting') else 'chevron-right'))
        self.action.setToolTip(text+' · '+self.title.text());self.action.setEnabled(state not in ('connecting','testing'))
        if self.configure:self.configure.setEnabled(state not in ('connecting','testing'))
        if self.reauthorize:
            self.reauthorize.setEnabled(state not in ('connecting','testing','broken','disabled'))
            self.reauthorize.setVisible(state in ('connected','pending','error','auth_required','awaiting'))
        if detail is not None and self.detail.text()!=detail:self.detail.setText(detail)
        self.setAccessibleName(self.title.text()+' · '+label)
        self._state_key=key

    def add_reauthorization(self,callback,label='Reconectar'):
        self._state_key=None
        self.reauthorize=QPushButton(label)
        self.reauthorize.setIcon(glyph('chevron-right'))
        self.reauthorize.setToolTip('Autorizar novamente ou escolher outra conta · '+self.title.text())
        self.reauthorize.setAccessibleName('Reconectar '+self.title.text())
        self.reauthorize.clicked.connect(callback)
        self.actions.layout().insertWidget(1,self.reauthorize)
        self.reauthorize.hide()


class ConnectionsPage(QWidget):
    def __init__(self,hub):
        super().__init__();self.hub=hub;self.rows={};self.local_gmail={};self._local_at=0;self._external_local={}
        outer=QVBoxLayout(self);outer.setContentsMargins(0,0,0,0);outer.setSpacing(12)
        hub.connections=QLabel('');hub.connections.setObjectName('settingsMeta');hub.connections.setWordWrap(True);outer.addWidget(hub.connections)
        toolbar=QHBoxLayout();toolbar.setSpacing(16)
        self.categories=QTabBar();self.categories.setExpanding(False);self.categories.setDrawBase(False)
        for title in ('Contas','Plugins nativos','Skills'):self.categories.addTab(title)
        self.categories.setAccessibleName('Categorias de conexões');toolbar.addWidget(self.categories)
        self.search=QLineEdit();self.search.setPlaceholderText('Buscar serviço, plugin ou skill');self.search.setAccessibleName('Buscar conexão, plugin ou skill');self.search.setMinimumWidth(150)
        self.search.addAction(glyph('search'),QLineEdit.ActionPosition.LeadingPosition)
        toolbar.addWidget(self.search,1);outer.addLayout(toolbar);self.toolbar=toolbar
        hub.connection_notice=QLabel();hub.connection_notice.setObjectName('connectionNotice');hub.connection_notice.setWordWrap(True);hub.connection_notice.setTextFormat(Qt.TextFormat.PlainText);outer.addWidget(hub.connection_notice)
        self.pages=QStackedWidget();outer.addWidget(self.pages,1);self.categories.currentChanged.connect(self.pages.setCurrentIndex)
        self.scrolls=[]
        for index in range(3):
            scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setFrameShape(QFrame.Shape.NoFrame)
            body=QWidget();scroll.setWidget(body)
            layout=TileLayout(body)
            self.scrolls.append((scroll,body,layout));self.pages.addWidget(scroll)
        self.account_scroll,self.body,self.layout=self.scrolls[0]
        self.native_scroll,self.native_body,self.native_layout=self.scrolls[1]
        self.skill_scroll,self.skills_body,self.skills_layout=self.scrolls[2]
        self.skill_rows={};self.search.textChanged.connect(self.filter_rows)
        hub.connection_buttons=[]
        self.section('Contas')
        from core.forge_settings import ForgeConnection
        self.forge_connection=ForgeConnection(hub);self.layout.addWidget(self.forge_connection)
        self.add('ai','IA Gemini','Conexão de voz e inteligência.',QStyle.StandardPixmap.SP_ComputerIcon,self.activate_ai,lambda:hub.open_page('ai'))
        self.add('gmail','Gmail','Autorização Google · somente leitura',QStyle.StandardPixmap.SP_FileDialogDetailedView,
                 lambda:self.activate('gmail'),lambda:self.show_gmail_editor())
        self.build_gmail_editor()
        self.add('whatsapp','WhatsApp Web','Sessão vinculada pelo código QR',QStyle.StandardPixmap.SP_MessageBoxInformation,
                 lambda:self.activate('whatsapp'),hub.connect_whatsapp)
        self.rows['gmail'].add_reauthorization(hub.connect_gmail)
        self.rows['whatsapp'].add_reauthorization(hub.connect_whatsapp)
        self.device_heading=self.section('Dispositivo')
        self.add('iphone','iPhone · Vincular ao Celular','Pareamento e permissões gerenciados no Windows.',QStyle.StandardPixmap.SP_DriveNetIcon,hub.connect_iphone).setProperty('connectionTile',False)
        self.section('Ferramentas e plugins')
        self.plugins_area=QWidget();self.plugins_layout=TileLayout(self.plugins_area);self.plugins_layout.setContentsMargins(0,0,0,0);self.layout.addWidget(self.plugins_area)
        links=QHBoxLayout();links.setContentsMargins(0,20,0,0)
        for text,callback in (('Gerenciar plugins',lambda:hub.open_overlay(hub.window._open_plugin_manager)),('Acesso remoto',lambda:hub.open_overlay(hub.window._open_remote))):
            button=QPushButton(text);button.clicked.connect(callback);links.addWidget(button)
        links.addStretch();self.layout.addLayout(links);self.layout.addStretch()
        self.native_layout.addStretch()
        self.build_skills()

    def ensureWidgetVisible(self,widget):
        self.categories.setCurrentIndex(0);self.account_scroll.ensureWidgetVisible(widget)

    def build_skills(self):
        from core.skill_library import entries
        translations={'brainstorming':'Explorar ideias','writing-plans':'Planejar etapas','systematic-debugging':'Investigar erros',
            'verification-before-completion':'Verificar resultados','requesting-code-review':'Revisar código','test-driven-development':'Desenvolver com testes',
            'frontend-design':'Design de interfaces','webapp-testing':'Testar interfaces web','mcp-builder':'Construir integrações MCP','skill-creator':'Criar skills',
            'notion-knowledge-capture':'Notion · registrar conhecimento','notion-meeting-intelligence':'Notion · reuniões',
            'notion-research-documentation':'Notion · pesquisa','notion-spec-to-implementation':'Notion · planejar implementação'}
        for item in entries():
            identifier=item['id'];title=translations.get(item['name'],item['name'])
            row=ConnectionRow(identifier,title,item.get('origin','Equipe Dief'),QStyle.StandardPixmap.SP_FileDialogContentsView,
                lambda checked=False,key=identifier:self.hub.open_skill(key))
            row.set_state('available' if item['available'] else 'error','Origem: '+item.get('origin','Equipe Dief'),'Consultar')
            row.status.setText('Ativa' if item['available'] else 'Integridade inválida');row.action.setEnabled(item['available'])
            self.skills_layout.addWidget(row);self.skill_rows[identifier]=row
        self.skills_layout.addStretch()

    def filter_rows(self):
        query=self.search.text().strip().casefold()
        for row in [*self.rows.values(),*self.skill_rows.values()]:
            row.setVisible(not query or query in (row.title.text()+' '+row.detail.text()).casefold())
        forge=self.forge_connection.row
        self.forge_connection.setVisible(not query or query in (forge.title.text()+' '+forge.detail.text()).casefold())
        for layout in (self.layout,self.native_layout,self.skills_layout,self.plugins_layout):layout.invalidate()

    def resizeEvent(self,event):
        self.toolbar.setDirection(QHBoxLayout.Direction.TopToBottom if self.width()<700 else QHBoxLayout.Direction.LeftToRight)
        super().resizeEvent(event)

    def section(self,text):
        title=QLabel(text);title.setObjectName('settingsGroup');self.layout.addWidget(title)
        return title

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
        account_keys={'ai','gmail','whatsapp'}|{'plugin:'+name for name in EXTERNAL}
        count=sum(state=='connected' and key in account_keys for key,state in self.states.items())
        available=sum(state in ('available','local','connected') and key not in account_keys for key,state in self.states.items())
        hub.connections.setText(f'{count} contas confirmadas · {available} plugins disponíveis · {len(self.skill_rows)} skills')
        busy=bool(hub._connection_checks.get('gmail').get('busy'))
        for field in (hub.gmail_email,hub.gmail_client,hub.gmail_secret):field.setEnabled(not busy)
        for button in hub.connection_buttons:
            if self.gmail_editor.isAncestorOf(button):button.setEnabled(not busy)

    def refresh_plugins(self,mapping):
        current={name for name in mapping if name not in ('gmail_control','whatsapp_web','skill_library')}
        for name in list(self.rows):
            if name.startswith('plugin:') and name[7:] not in current:
                row=self.rows.pop(name)
                layout=self.native_layout if row.parentWidget() is self.native_body else self.layout if row.parentWidget() is self.body else self.plugins_layout
                layout.removeWidget(row);row.deleteLater()
                self._external_local.pop(name[7:],None)
        settings=set()
        if any('plugin:'+name not in self.rows for name in current):
            sections=self.hub.window.get_plugin_settings() if self.hub.window.get_plugin_settings else []
            settings={value for section in sections for value in (section.get('plugin'),section.get('namespace')) if value}
        for name in sorted(current):
            external=name in EXTERNAL
            provider='desktop' if name=='desktop_accessibility' else 'plugin:'+name
            if external:provider=name
            identifier='plugin:'+name
            if identifier not in self.rows:
                row=ConnectionRow(identifier,tool_label(name),'Ferramenta instalada',QStyle.StandardPixmap.SP_ComputerIcon,
                    lambda checked=False,n=name:self.hub.activate_plugin(n),
                    (lambda checked=False,n=name:self.hub.open_plugin_settings(n)) if name in settings else None)
                if external:row.add_reauthorization(lambda checked=False,n=name:self.hub.reauthorize_plugin(n))
                self.rows[identifier]=row
                accounts={'spotify_control','google_calendar','google_drive','gmail_compose','notion_service','outlook_service','home_automation','fish_audio'}
                if name in accounts:
                    self.layout.insertWidget(2 if name=='spotify_control' else self.layout.indexOf(self.device_heading),row)
                elif external:self.plugins_layout.addWidget(row)
                else:self.native_layout.insertWidget(max(0,self.native_layout.count()-1),row)
                row.set_motion_reduced(self.hub._config().get('reduce_motion',False))
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
            from core.extension_suite import CATALOG
            if name in CATALOG and local.get('installed') is False:action='Instalar ferramenta'
            self.rows[identifier].set_state(state,detail,action)
            self.states[identifier]=state
        self.filter_rows()


