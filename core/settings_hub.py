"""Settings surfaces backed by existing assistant callbacks and preferences."""
import json
import re
import threading
import os
import weakref
from PyQt6.QtCore import QTimer, pyqtSignal, Qt, QSize, QEvent
from PyQt6.QtGui import QFont, QColor
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QStackedWidget, QListWidget, QWidget,
    QFormLayout, QLineEdit, QTextEdit, QSpinBox, QPushButton, QLabel, QComboBox, QCheckBox, QScrollArea, QFrame, QFileDialog, QStyle, QListWidgetItem, QColorDialog)
from core.settings_style import SettingsSurface, settings_icon

class SettingsHub(SettingsSurface):
    connection_done = pyqtSignal(object)

    def __init__(self, window, config_path, palette):
        super().__init__(window)
        self.window, self.config_path = window, config_path
        from core.connection_states import ConnectionChecks
        self._connection_checks=getattr(window,'_connection_checks',None) or ConnectionChecks();self._closed=False
        self._ai_check=None;self._ai_timeout=QTimer(self);self._ai_timeout.setSingleShot(True);self._ai_timeout.timeout.connect(self._ai_test_timeout)
        self.page_indices={}
        self.setWindowTitle("DIEF JARVIS · Configurações")
        from core.branding import app_icon
        self.setWindowIcon(app_icon())
        self.resize(1200, 800)
        self.setFont(QFont('Segoe UI',10))
        layout = QHBoxLayout(self); layout.setContentsMargins(0,0,0,0); layout.setSpacing(0)
        rail = QFrame(); rail.setObjectName('settingsRail'); rail.setFixedWidth(210);self.rail=rail
        rail_layout = QVBoxLayout(rail); rail_layout.setContentsMargins(20,28,20,24)
        brand = QLabel('DIEF JARVIS'); brand.setObjectName('settingsBrand'); rail_layout.addWidget(brand)
        label = QLabel('Configurações'); label.setObjectName('sectionTitle'); rail_layout.addWidget(label)
        self.navigation=QListWidget(); self.navigation.setIconSize(QSize(20,20)); rail_layout.addWidget(self.navigation,1)
        self.navigation.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        layout.addWidget(rail)
        workspace = QVBoxLayout(); workspace.setContentsMargins(30,24,30,28); workspace.setSpacing(20);self.workspace_layout=workspace
        layout.addLayout(workspace,1)
        header = QHBoxLayout(); self.section_title=QLabel('Perfil'); self.section_title.setObjectName('settingsTitle'); header.addWidget(self.section_title); header.addStretch()
        close = QPushButton(); close.setObjectName('settingsClose'); close.setIcon(settings_icon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogCloseButton))); close.setFixedSize(42,42)
        close.setAccessibleName('Voltar ao Jarvis'); close.setToolTip('Voltar ao Jarvis'); close.clicked.connect(self.close); header.addWidget(close)
        workspace.addLayout(header)
        self.tabs = QStackedWidget(); workspace.addWidget(self.tabs,1)
        self.navigation.currentRowChanged.connect(self.tabs.setCurrentIndex)
        self.navigation.currentRowChanged.connect(self.animate_entry)
        self.navigation.currentTextChanged.connect(self.section_title.setText)
        def add_page(page,title,icon,key):
            from core.system_knowledge import SETTINGS_PAGES
            title=SETTINGS_PAGES[key]['title']
            item = QListWidgetItem(settings_icon(self.style().standardIcon(icon)), title)
            self.page_indices[key]=self.tabs.count()
            self.navigation.addItem(item);self.tabs.addWidget(page)
        cfg = self._config()
        def group(form,title):
            label=QLabel(title);label.setObjectName('settingsGroup');form.addRow(label)
        profile = QWidget(); form = QFormLayout(profile); form.setSpacing(18); form.setContentsMargins(0,12,20,24)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        group(form,'Identidade e localização')
        self.name = QLineEdit(cfg.get("user_name", "")); form.addRow("Como chamar você", self.name)
        self.assistant_name = QLineEdit(cfg.get('assistant_name','DIEF JARVIS')); form.addRow('Nome do assistente',self.assistant_name)
        self.city = QLineEdit(cfg.get("city", "")); form.addRow("Cidade do clima", self.city)
        self.visual = QComboBox(); self.visual.addItem("Rosto","face"); self.visual.addItem("Núcleo","core"); self.visual.setCurrentIndex(1 if window.hud.hud_style=="core" else 0); self.visual.setMaximumWidth(320); form.addRow("Visual do holograma",self.visual)
        group(form,'Notícias e rotina')
        self.interests = QTextEdit(); self.interests.setPlainText(cfg.get("news_interests", "")); self.interests.setMaximumHeight(110); form.addRow("Preferências de notícias", self.interests)
        self.count = QSpinBox(); self.count.setRange(1,10); self.count.setValue(int(cfg.get("news_count",5)));self.count.setMaximumWidth(160); form.addRow("Quantidade de notícias",self.count)
        self.brief=QCheckBox('Atualização do dia ao iniciar ou retomar a conversa');self.brief.setChecked(bool(cfg.get('morning_brief_enabled',True)));form.addRow(self.brief)
        save = QPushButton("Salvar perfil"); save.setMaximumWidth(210);save.setIcon(settings_icon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton))); save.setObjectName('primaryAction'); save.clicked.connect(self.save); form.addRow(save)
        self.notice = QLabel(""); self.notice.setWordWrap(True); form.addRow(self.notice)
        profile_scroll=QScrollArea();profile_scroll.setWidgetResizable(True);profile_scroll.setFrameShape(QFrame.Shape.NoFrame);profile_scroll.setWidget(profile)
        add_page(profile_scroll,"Perfil",QStyle.StandardPixmap.SP_FileDialogInfoView,'profile')
        appearance_page = QWidget(); form = QFormLayout(appearance_page); form.setSpacing(18); form.setContentsMargins(0,12,20,24)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        group(form,'Holograma e projeções')
        self.reduced=QCheckBox('Reduzir movimento das projeções');self.reduced.setChecked(bool(cfg.get('reduce_motion',False)));form.addRow(self.reduced)
        self.hold = QSpinBox(); self.hold.setRange(0,120); self.hold.setSuffix(" s"); self.hold.setSpecialValueText("Manter na tela"); self.hold.setValue(int(cfg.get("presentation_hold",15))); self.hold.setMaximumWidth(170); form.addRow("Recolher após a fala",self.hold)
        self.selected_color = cfg.get('ui_color') or '#00d4ff'
        self.color_button = QPushButton(); self.color_button.setAccessibleName('Cor do holograma'); self.color_button.setToolTip('Cor do holograma'); self.color_button.setFixedSize(60,38)
        self.color_button.clicked.connect(self.pick_color); self._update_swatch(); form.addRow('Cor do holograma',self.color_button)
        group(form,'Voz e áudio')
        from memory.config_manager import AVAILABLE_VOICES, DEFAULT_VOICE
        self.voice = QComboBox(); self.voice.addItems(AVAILABLE_VOICES); self.voice.setCurrentText(cfg.get('voice_name') or DEFAULT_VOICE); self.voice.setMaximumWidth(320); form.addRow('Voz em português',self.voice)
        audio = QPushButton('Dispositivos de áudio'); audio.clicked.connect(lambda:self.open_overlay(window._open_audio_devices)); form.addRow(audio)
        save_appearance = QPushButton('Salvar aparência');save_appearance.setMaximumWidth(230);save_appearance.setIcon(settings_icon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton))); save_appearance.setObjectName('primaryAction'); save_appearance.clicked.connect(self.save); form.addRow(save_appearance)
        self.appearance_notice = QLabel(); self.appearance_notice.setWordWrap(True); form.addRow(self.appearance_notice)
        appearance_scroll=QScrollArea();appearance_scroll.setWidgetResizable(True);appearance_scroll.setWidget(appearance_page)
        add_page(appearance_scroll,'Aparência',QStyle.StandardPixmap.SP_ComputerIcon,'appearance')
        activity = QWidget(); al = QVBoxLayout(activity); al.setContentsMargins(0,0,0,0); self.activity = QTextEdit(); self.activity.setReadOnly(True); al.addWidget(self.activity); add_page(activity,"Atividade",QStyle.StandardPixmap.SP_FileDialogDetailedView,'activity')
        chat = QWidget(); cl = QVBoxLayout(chat); self.chat = QTextEdit(); self.chat.setReadOnly(True); cl.addWidget(self.chat)
        row = QHBoxLayout(); self.message = QLineEdit(); self.message.setPlaceholderText('Mensagem para o Jarvis'); row.addWidget(self.message); send = QPushButton("Enviar"); send.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowForward)); row.addWidget(send); cl.addLayout(row); send.clicked.connect(self.send); self.message.returnPressed.connect(self.send); add_page(chat,"Conversa",QStyle.StandardPixmap.SP_MessageBoxInformation,'chat')
        self.connection_done.connect(self._connection_finished)
        from core.settings_connections import ConnectionsPage
        self.connections_page=ConnectionsPage(self)
        add_page(self.connections_page,"Conexões",QStyle.StandardPixmap.SP_DriveNetIcon,'connections')
        ai = QWidget(); il = QVBoxLayout(ai); self.ai = QLabel(); self.ai.setWordWrap(True); il.addWidget(self.ai)
        key_form=QFormLayout(); il.addLayout(key_form)
        self.ai_key=QLineEdit(); self.ai_key.setEchoMode(QLineEdit.EchoMode.Password); self.ai_key.setPlaceholderText('Credencial salva' if cfg.get('gemini_api_key') else 'Chave Gemini'); self.ai_key.setAccessibleName('Chave da IA Gemini'); key_form.addRow('Chave Gemini',self.ai_key)
        key_save=QPushButton('Salvar chave da IA'); key_save.clicked.connect(self.save_ai_key); il.addWidget(key_save)
        self.ai_notice=QLabel(); self.ai_notice.setWordWrap(True); il.addWidget(self.ai_notice)
        for title, callback in (("Consultar memória",window._open_memory_panel),):
            button = QPushButton(title); button.clicked.connect(lambda checked=False, cb=callback:self.open_overlay(cb)); il.addWidget(button)
        il.addStretch(); add_page(ai,"IA e memória",QStyle.StandardPixmap.SP_DriveHDIcon,'ai')
        for field, name in ((self.name,'Como chamar você'),(self.city,'Cidade do clima'),(self.interests,'Preferências de notícias'),(self.count,'Quantidade de notícias'),(self.message,'Mensagem para o Jarvis')):
            field.setAccessibleName(name)
        for button in self.findChildren(QPushButton):
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            if button not in (close,self.color_button):
                button.setMaximumWidth(600)
        for page in (profile,appearance_page,self.connections_page.body,ai):
            page.setMaximumWidth(1080)
        self.navigation.currentRowChanged.connect(self._page_selected)
        self.navigation.setCurrentRow(0)
        self.timer = QTimer(self); self.timer.timeout.connect(self.refresh); self.timer.start(1000); self.refresh()

    def _config(self):
        try:
            return json.loads(self.config_path.read_text(encoding="utf-8"))
        except (OSError,ValueError):
            return {}

    def open_overlay(self,callback):
        before = set(self.window.centralWidget().findChildren(QWidget, options=Qt.FindChildOption.FindDirectChildrenOnly))
        callback()
        created = [w for w in self.window.centralWidget().findChildren(QWidget, options=Qt.FindChildOption.FindDirectChildrenOnly) if w not in before and w.isVisible()]
        if not created:
            return
        overlay = created[-1]
        self._return_page = self.navigation.currentRow()
        if getattr(self,'_detail_page',None):
            self.tabs.removeWidget(self._detail_page); self._detail_page.deleteLater()
        page=QWidget(); page_layout=QVBoxLayout(page); page_layout.setContentsMargins(0,0,0,0)
        back=QPushButton('Voltar'); back.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowBack)); back.setMaximumWidth(140)
        back.clicked.connect(self._leave_detail); page_layout.addWidget(back)
        scroll=QScrollArea(); scroll.setWidgetResizable(True); page_layout.addWidget(scroll,1)
        overlay.hide(); overlay.setParent(scroll); overlay.setMinimumSize(0,0); overlay.setMaximumSize(1080,16777215)
        for widget in [overlay,*overlay.findChildren(QWidget)]:
            widget.setStyleSheet('')
            widget.setFont(QFont('Segoe UI',10))
            if isinstance(widget,(QLineEdit,QComboBox,QPushButton)):
                widget.setMinimumHeight(40); widget.setMaximumHeight(16777215)
        scroll.setWidget(overlay); overlay.installEventFilter(self)
        self._detail_page=page; self._detail_overlay=overlay
        self.tabs.addWidget(page); self.tabs.setCurrentWidget(page); overlay.show()
        self.section_title.setText(back.text()+' · '+self.navigation.currentItem().text())

    def _leave_detail(self):
        overlay=getattr(self,'_detail_overlay',None)
        if overlay:
            overlay.hide()
        self.tabs.setCurrentIndex(self._return_page)
        self.section_title.setText(self.navigation.item(self._return_page).text())

    def eventFilter(self,watched,event):
        if watched is getattr(self,'_detail_overlay',None) and event.type()==QEvent.Type.Hide:
            QTimer.singleShot(0,lambda:self.tabs.setCurrentIndex(self.navigation.currentRow()))
            self.section_title.setText(self.navigation.currentItem().text())
        return super().eventFilter(watched,event)

    def _update_swatch(self):
        self.color_button.setStyleSheet(f'background:{self.selected_color}; border:2px solid #4bb7c9; border-radius:4px;')

    def pick_color(self):
        color=QColorDialog.getColor(QColor(self.selected_color),self,'Cor do holograma')
        if color.isValid():
            self.selected_color=color.name(); self._update_swatch()

    def save_ai_key(self):
        key=self.ai_key.text().strip()
        if not key:
            self.ai_notice.setText('Informe a chave para substituir a credencial salva.'); return
        cfg=self._config(); cfg['gemini_api_key']=key
        try:
            self.config_path.write_text(json.dumps(cfg,indent=4,ensure_ascii=False),encoding='utf-8')
        except OSError:
            self.ai_notice.setText('Não foi possível salvar a credencial. Confira o acesso à pasta do Jarvis.'); return
        self.ai_key.clear(); self.ai_key.setPlaceholderText('Credencial salva')
        self.ai_notice.setText('Credencial salva. Reconectando para verificar a IA.')
        if self.window.on_voice_change:
            if self._ai_check:
                self._connection_checks.invalidate('ai');self._ai_check=None
            self.check_ai(reset_session=True)

    def _connection_worker(self, callback,provider='gmail',connecting=False):
        generation=self._connection_checks.begin(provider,connecting)
        if generation is None:return
        self.connection_notice.setText("Aguardando conexão/autorização…")
        self.refresh()
        reference=weakref.ref(self);checks=self._connection_checks
        def worker():
            try:
                value=callback()
                if isinstance(value,dict):
                    ok=bool(value.get('ok'));message=value.get('message','');state=value.get('state','connected' if ok else 'error')
                else:
                    ok,message=value;state='connected' if ok else 'auth_required'
            except Exception as error:
                if provider=='spotify_control':
                    from core.spotify_service import error_details
                    details=error_details(error);state=details['state'];ok=False;message=details['message']
                elif provider in ('google_drive','google_calendar','gmail_compose'):
                    from core.google_services import error_details
                    details=error_details(error);state=details['state'];ok=False;message=details['message']
                else:
                    code=getattr(getattr(error,'resp',None),'status',None)
                    state='auth_required' if code==401 else 'error'
                    ok,message=False,f"Não foi possível verificar ({type(error).__name__}). Confira a autorização ou a conexão."
            if not checks.finish(provider,generation,state,message):return
            target=reference()
            if target is not None and not target._closed:
                try:target.connection_done.emit({'provider':provider,'generation':generation,'ok':ok,'message':message})
                except RuntimeError:pass
        threading.Thread(target=worker,daemon=True,name="ConnectionSetup").start()

    def _connection_finished(self, result):
        if self._closed:return
        self.connection_notice.setText(result['message'])
        self.connections_page._local_at=0
        self.connections_page._external_local.clear()
        busy=bool(self._connection_checks.get('gmail').get('busy'))
        for button in self.connection_buttons:
            if self.connections_page.gmail_editor.isAncestorOf(button):button.setEnabled(not busy)
        self.refresh()

    def connect_whatsapp(self):
        from core.whatsapp_web import transport
        def connect():
            result=transport.call('connect')
            return {'ok':bool(result.get('connected')),'state':'connected' if result.get('connected') else 'awaiting' if result.get('ok') else 'error',
                'message':result.get('status') or result.get('error') or 'Autorize o WhatsApp pelo código QR.'}
        self._connection_worker(connect,'whatsapp',connecting=True)

    def check_whatsapp(self):
        from core.whatsapp_web import transport
        def check():
            result=transport.call("status")
            connected=bool(result.get('connected'))
            return {'ok':connected,'state':'connected' if connected else 'disconnected' if result.get('needs_link') else 'error',
                'message':result.get('status') if connected else result.get('error','Não confirmei a conexão do WhatsApp Web.')}
        self._connection_worker(check,'whatsapp')

    def import_gmail_credentials(self):
        from core import gmail_connection as gmail
        path,_=QFileDialog.getOpenFileName(self,"Selecionar JSON OAuth do Google para computador","","Credenciais Google (*.json)")
        if not path:
            return
        try:
            gmail.import_credentials(path)
            self.gmail_client.setText(gmail.credential_client_id()); self.gmail_secret.clear()
            self.gmail_secret.setPlaceholderText("Credencial salva")
            self.connection_notice.setText("Credencial importada. Autorização da conta pendente.")
            self._connection_checks.invalidate('gmail');self.connections_page._local_at=0;self.refresh()
        except Exception as error:
            self.connection_notice.setText(str(error) if isinstance(error,ValueError) else "Arquivo de credenciais inválido.")

    def save_gmail_credentials(self):
        from core import gmail_connection as gmail
        if self._connection_checks.get('gmail').get('busy'):
            self.connection_notice.setText('Aguarde a verificação ou autorização atual do Gmail.');return False
        try:
            client = self.gmail_client.text().strip()
            secret = self.gmail_secret.text().strip()
            email = self.gmail_email.text().strip()
            if email and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
                raise ValueError("Informe um endereço de e-mail válido.")
            if secret or client != gmail.credential_client_id() or not gmail.CREDENTIALS.exists():
                gmail.configure_credentials(client, secret)
            gmail.save_expected_account(email)
            self.gmail_secret.clear(); self.gmail_secret.setPlaceholderText("Credencial salva")
            self.connection_notice.setText("Credencial e conta desejada salvas. A conexão depende da autorização do Google.")
            self._connection_checks.invalidate('gmail');self.connections_page._local_at=0
            self.refresh()
            return True
        except Exception as error:
            self.connection_notice.setText(str(error) if isinstance(error, ValueError) else "Não foi possível salvar a credencial Gmail.")
            return False

    def connect_gmail(self):
        from core import gmail_connection as gmail
        if not self.save_gmail_credentials():
            return
        email = self.gmail_email.text().strip()
        self._connection_worker(lambda: gmail.connect(email),'gmail',connecting=True)

    def check_gmail(self):
        from core import gmail_connection as gmail
        email = self.gmail_email.text().strip()
        self._connection_worker(lambda: gmail.verify(email),'gmail')

    def connect_iphone(self):
        import os
        try:
            os.startfile("shell:AppsFolder\\Microsoft.YourPhone_8wekyb3d8bbwe!App")
            self.connection_notice.setText("No Vincular ao Celular, escolha iPhone e siga o pareamento Bluetooth. Mensagens, chamadas e notificações dependem das permissões do iPhone; isso não libera controle de todos os aplicativos.")
        except OSError:
            self.connection_notice.setText("Não consegui abrir Vincular ao Celular. Confira a instalação do aplicativo da Microsoft.")

    def save(self):
        cfg = self._config()
        cfg.update(user_name=self.name.text().strip()[:100],city=self.city.text().strip()[:120],
                   news_interests=self.interests.toPlainText().strip()[:1000],news_count=self.count.value(),presentation_hold=self.hold.value(),morning_brief_enabled=self.brief.isChecked(),reduce_motion=self.reduced.isChecked())
        self.config_path.write_text(json.dumps(cfg,indent=4,ensure_ascii=False),encoding="utf-8")
        from memory.config_manager import save_hud_style
        save_hud_style(self.visual.currentData()); self.window.hud.hud_style=self.visual.currentData()
        self.window._apply_name_update(self.assistant_name.text(),self.name.text(),self.selected_color,'')
        from memory.config_manager import save_voice
        save_voice(self.voice.currentText())
        self.window._update_brief_btn(self.brief.isChecked())
        from core.hud_glass import HudGlassFrame
        for frame in self.window.findChildren(HudGlassFrame):
            frame.set_motion_reduced(self.reduced.isChecked())
        for key in ('_terminal','_execution'):
            panel=getattr(self.window,key,None)
            if panel: panel.surface.set_motion_reduced(self.reduced.isChecked())
        self.animate_entry()
        if self.window.on_voice_change:
            self.window.on_voice_change()
        self.notice.setText("Perfil salvo. Clima e notícias usam essas preferências nas próximas consultas.")
        self.appearance_notice.setText('Aparência salva.')

    def send(self):
        text = self.message.text().strip()
        if text and self.window.on_text_command:
            self.window._log.append_log("Você: " + text)
            threading.Thread(target=self.window.on_text_command,args=(text,),daemon=True).start()
            self.message.clear()

    def refresh(self):
        log = self.window._log.toPlainText()[-40000:]
        if self.activity.toPlainText()!=log:
            self.activity.setPlainText(log); self.activity.verticalScrollBar().setValue(self.activity.verticalScrollBar().maximum())
        dialogue = "\n".join(line for line in log.splitlines() if any(name in line.lower() for name in ("você:","you:","jarvis:","dief jarvis:")))
        if self.chat.toPlainText()!=dialogue:
            self.chat.setPlainText(dialogue); self.chat.verticalScrollBar().setValue(self.chat.verticalScrollBar().maximum())
        plugins = self.window.get_plugins() if self.window.get_plugins else []
        state = getattr(self.window,"_connection_status",{"connected":False,"model":"--"})
        if self._ai_check and state.get('connected') and state.get('revision',0)>self._ai_check[1]:
            self._connection_checks.finish('ai',self._ai_check[0],'connected','Sessão da IA reconectada e confirmada.')
            self._ai_check=None;self._ai_timeout.stop();self.ai_notice.setText('Conexão da IA confirmada.')
        self.connections_page.refresh(plugins,state)
        self.connection_notice.setVisible(bool(self.connection_notice.text()))
        from core.locale_pt_br import state_label, VISUALS
        self.ai.setText(f"Conexão: {'conectada' if state['connected'] else 'desconectada'}\nModelo: {state.get('model','--')}\nEstado: {state_label(self.window.hud.state)}\nMicrofone: {'silenciado' if self.window._muted else 'ativo'}\nVisual: {VISUALS.get(self.window.hud.hud_style,'Indisponível')}")

    def closeEvent(self,event):
        self._closed=True
        if self._ai_check:
            self._connection_checks.invalidate('ai');self._ai_check=None
        self._ai_timeout.stop()
        self.timer.stop(); super().closeEvent(event)

    def open_page(self,key):
        if key not in self.page_indices:raise ValueError('Seção de configurações desconhecida.')
        self.navigation.setCurrentRow(self.page_indices[key]);self.tabs.setCurrentIndex(self.page_indices[key])

    def check_ai(self,reset_session=False):
        self.open_page('ai')
        callback=(None if reset_session else getattr(self.window,'on_connection_test',None)) or self.window.on_voice_change
        if callback is None:
            self.ai_notice.setText('Inicie o assistente para verificar a sessão da IA.');return
        generation=self._connection_checks.begin('ai')
        if generation is None:return
        self._ai_check=(generation,getattr(self.window,'_connection_status',{}).get('revision',0))
        self.ai_notice.setText('Reconectando para verificar a sessão da IA…');self.refresh();self._ai_timeout.start(45000)
        try:callback()
        except Exception:
            self._ai_test_timeout()

    def _ai_test_timeout(self):
        if not self._ai_check:return
        self._ai_timeout.stop()
        self._connection_checks.finish('ai',self._ai_check[0],'error','Não houve confirmação de uma nova conexão da IA. Confira a chave e a internet.')
        self._ai_check=None;self.ai_notice.setText('O teste não confirmou a conexão. Confira a chave e a internet.');self.refresh()

    def _page_selected(self,index):
        if index!=self.page_indices.get('connections') or not self.isVisible():return
        if os.environ.get('QT_QPA_PLATFORM')=='offscreen':return
        if hasattr(self.window,'_verify_saved_connections'):
            self.window._verify_saved_connections()

    def showEvent(self,event):
        self._closed=False;super().showEvent(event)
        if hasattr(self,'timer'):self.timer.start(1000)
        if hasattr(self,'connections_page'):self._page_selected(self.navigation.currentRow())

    def resizeEvent(self,event):
        super().resizeEvent(event)
        if hasattr(self,'rail'):
            self.rail.setFixedWidth(210)
            margin=18 if self.width()<1000 else 30
            self.workspace_layout.setContentsMargins(margin,24,margin,24)

    def enable_plugin(self,name):
        from memory.config_manager import save_plugin_enabled
        save_plugin_enabled(name,True)
        if self.window.on_voice_change:self.window.on_voice_change()
        self.refresh()

    def activate_plugin(self,name):
        plugins={p['name']:p for p in (self.window.get_plugins() if self.window.get_plugins else [])}
        record=plugins.get(name,{})
        if not record.get('valid'):self.open_overlay(self.window._open_plugin_manager);return
        if not record.get('enabled'):self.enable_plugin(name);return
        from core.resource_policy import LOCAL,local_status
        if name in LOCAL:
            def check_local():
                value=local_status(name)
                return {'ok':value['local_available'],'state':value['state'],'message':value['message']}
            self._connection_worker(check_local,'desktop' if name=='desktop_accessibility' else 'plugin:'+name);return
        if name=='notion_service':
            from core import notion_service as service
            if service.status()['connected']:self._connection_worker(service.verify,name)
            else:self.open_plugin_settings(name)
            return
        if name in ('outlook_service','mcp_bridge'):
            from importlib import import_module
            service=import_module('core.'+name);local=service.status()
            if self._connection_checks.get(name).get('state')=='auth_required':
                self.reauthorize_plugin(name)
            elif local.get('connected') or name=='mcp_bridge' and local.get('configured'):
                self._connection_worker(service.verify,name)
            elif name=='outlook_service' and local.get('configured'):
                self.reauthorize_plugin(name)
            else:self.open_plugin_settings(name)
            return
        if name in ('google_calendar','google_drive','spotify_control','gmail_compose','home_automation'):
            if name=='home_automation':
                from core import home_automation as service
                local=service.status();check=service.verify
                # Token entry belongs to the settings action, not to a model call.
                if local.get('connected'):
                    self._connection_worker(check,name)
                else:self.open_plugin_settings(name)
                return
            elif name=='spotify_control':
                from core import spotify_service as service
                local=service.status();check=service.verify;connect=service.connect
            else:
                from core import google_services as service
                local=service.status(name);check=lambda:service.verify(name);connect=lambda:service.connect(name)
            checked=self._connection_checks.get(name)
            if checked.get('state')=='auth_required':
                self.reauthorize_plugin(name)
            elif local.get('connected') or local.get('authorization_pending') or checked.get('state') in ('connected','error','pending'):
                self._connection_worker(check,name)
            elif local.get('configured'):
                self._connection_worker(connect,name,connecting=True)
            else:self.open_plugin_settings(name)
            return
        self.open_plugin_settings(name)

    def reauthorize_plugin(self,name):
        from core.resource_policy import EXTERNAL,external_status
        if name not in EXTERNAL:raise ValueError('Esta ferramenta nao exige autorizacao de conta.')
        plugins={p['name']:p for p in (self.window.get_plugins() if self.window.get_plugins else [])}
        record=plugins.get(name,{})
        if not record.get('valid'):self.open_overlay(self.window._open_plugin_manager);return
        if not record.get('enabled'):self.enable_plugin(name);return
        if self._connection_checks.get(name).get('busy'):return
        local=external_status(name)
        if name in ('home_automation','mcp_bridge','notion_service') or not local.get('configured'):
            self.open_plugin_settings(name);return
        if name in ('google_calendar','google_drive','gmail_compose'):
            from core.google_services import connect
            self._connection_worker(lambda:connect(name),name,connecting=True)
        else:
            from importlib import import_module
            service=import_module('core.spotify_service' if name=='spotify_control' else 'core.'+name)
            self._connection_worker(service.connect,name,connecting=True)

    def open_plugin_settings(self,name):
        sections=self.window.get_plugin_settings() if self.window.get_plugin_settings else []
        selected=[section for section in sections if section.get('plugin')==name or section.get('namespace')==name]
        if not selected:self.open_overlay(self.window._open_plugin_manager);return
        def show():
            from ui import PluginSettingsOverlay
            panel=PluginSettingsOverlay(selected,self.window.centralWidget());panel.show()
            panel._test_done.connect(lambda ns,ok,msg:self._plugin_authorization_finished(ns,ok,msg))
            self.window._plugin_settings_overlay=panel
        self.open_overlay(show)

    def _plugin_authorization_finished(self,name,ok,message):
        self._connection_checks.invalidate(name)
        self.connections_page._external_local.pop(name,None)
        generation=self._connection_checks.begin(name)
        if generation is not None:
            state='connected' if ok else 'error'
            from core.resource_policy import external_status
            local=external_status(name)
            if ok and not local.get('connected'):state='pending'
            self._connection_checks.finish(name,generation,state,message)
        self.connection_notice.setText(message)
        self.refresh()
