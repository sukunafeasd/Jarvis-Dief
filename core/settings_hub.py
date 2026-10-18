"""Settings surfaces backed by existing assistant callbacks and preferences."""
import json
import re
import threading
import os
import weakref
import queue
from core.bounded_work import BoundedWork
from PyQt6.QtCore import QTimer, pyqtSignal, Qt, QSize, QEvent
from PyQt6.QtGui import QFont, QColor
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QStackedWidget, QListWidget, QWidget,
    QFormLayout, QLineEdit, QTextEdit, QSpinBox, QPushButton, QLabel, QComboBox, QCheckBox, QScrollArea, QFrame, QFileDialog, QStyle, QListWidgetItem, QColorDialog)
from core.settings_style import SettingsSurface, settings_icon
from core.settings_components import SettingsSection, field_label, CorePreview, RailClock, LightSwitch
from core.ui_assets import glyph

CONNECTION_TIMEOUT=60
AUTHORIZATION_TIMEOUT=180
_CONNECTION_WORK=BoundedWork(workers=3,capacity=6,name='ConnectionSetup')

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
        rail = QFrame(); rail.setObjectName('settingsRail'); rail.setFixedWidth(190);self.rail=rail
        rail_layout = QVBoxLayout(rail); rail_layout.setContentsMargins(12,26,12,18)
        brand = QLabel('DIEF JARVIS'); brand.setObjectName('settingsBrand'); rail_layout.addWidget(brand)
        label = QLabel('CENTRAL DE CONTROLE'); label.setObjectName('sectionTitle'); rail_layout.addWidget(label)
        self.navigation=QListWidget(); self.navigation.setIconSize(QSize(20,20)); rail_layout.addWidget(self.navigation,1)
        self.navigation.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        rail_layout.addWidget(RailClock())
        layout.addWidget(rail)
        workspace = QVBoxLayout(); workspace.setContentsMargins(22,18,22,18); workspace.setSpacing(16);self.workspace_layout=workspace
        layout.addLayout(workspace,1)
        header = QHBoxLayout(); self.section_title=QLabel('Perfil'); self.section_title.setObjectName('settingsTitle'); header.addWidget(self.section_title); header.addStretch()
        close = QPushButton(); close.setObjectName('settingsClose'); close.setIcon(glyph('x')); close.setFixedSize(38,38)
        close.setAccessibleName('Voltar ao Jarvis'); close.setToolTip('Voltar ao Jarvis'); close.clicked.connect(self.close); header.addWidget(close)
        workspace.addLayout(header)
        self.tabs = QStackedWidget(); workspace.addWidget(self.tabs,1)
        self.navigation.currentRowChanged.connect(self.tabs.setCurrentIndex)
        self.navigation.currentRowChanged.connect(self.animate_entry)
        self.navigation.currentTextChanged.connect(self.section_title.setText)
        def add_page(page,title,icon,key):
            from core.system_knowledge import SETTINGS_PAGES
            title=SETTINGS_PAGES[key]['title']
            icons={'profile':'user-round','appearance':'monitor','connections':'link','ai':'brain','chat':'message-circle','activity':'activity'}
            item = QListWidgetItem(glyph(icons[key]), title)
            self.page_indices[key]=self.tabs.count()
            self.navigation.addItem(item);self.tabs.addWidget(page)
        cfg = self._config()
        profile = QWidget(); profile_layout=QVBoxLayout(profile);profile_layout.setContentsMargins(0,0,8,12);profile_layout.setSpacing(14)
        self.profile_top=QHBoxLayout();self.profile_top.setSpacing(12);profile_layout.addLayout(self.profile_top)
        identity=SettingsSection('IDENTIDADE E LOCALIZAÇÃO','Personalize como o JARVIS conversa com você.','user-round');self.profile_top.addWidget(identity,3)
        self.core_preview=CorePreview(self);self.profile_top.addWidget(self.core_preview,2)
        form=identity.form
        self.name = QLineEdit(cfg.get("user_name", "")); form.addRow(field_label('Como chamar você','Seu nome ou apelido.','message-circle'), self.name)
        self.assistant_name = QLineEdit(cfg.get('assistant_name','DIEF JARVIS')); form.addRow(field_label('Nome do assistente','A identidade do seu assistente.','bot'),self.assistant_name)
        self.city = QLineEdit(cfg.get("city", "")); form.addRow(field_label('Cidade do clima','Local das previsões.','map-pin'), self.city)
        self.visual = QComboBox(); self.visual.addItem("Rosto","face"); self.visual.addItem("Núcleo","core"); self.visual.setCurrentIndex(1 if window.hud.hud_style=="core" else 0); form.addRow(field_label('Visual do holograma','','box'),self.visual)
        self.panel_sounds_muted=LightSwitch();self.panel_sounds_muted.setAccessibleName('Silenciar sons do painel');self.panel_sounds_muted.setChecked(cfg.get('panel_sounds_muted') is True);form.addRow(field_label('Silenciar sons do painel','Sons de interação da interface.','volume-2'),self.panel_sounds_muted)
        self.panel_sounds_muted.toggled.connect(self._set_panel_sounds_muted)
        self._set_panel_sounds_muted(self.panel_sounds_muted.isChecked())
        routine=SettingsSection('NOTÍCIAS E ROTINA','Informações e preferências para o seu dia.','newspaper');profile_layout.addWidget(routine);form=routine.form
        self.interests = QTextEdit(); self.interests.setPlainText(cfg.get("news_interests", "")); self.interests.setFixedHeight(54); form.addRow(field_label('Preferências de notícias','Temas separados por vírgula.','newspaper'), self.interests)
        self.count = QSpinBox(); self.count.setRange(1,10); self.count.setValue(int(cfg.get("news_count",5)));self.count.setMaximumWidth(110); form.addRow(field_label('Quantidade de notícias','','hash'),self.count)
        self.brief=LightSwitch();self.brief.setAccessibleName('Atualização do dia ao iniciar ou retomar a conversa');self.brief.setChecked(bool(cfg.get('morning_brief_enabled',True)));form.addRow(field_label('Atualização do dia','Ao iniciar ou retomar a conversa.','sunrise'),self.brief)
        if os.name == 'nt':
            from core.windows_autostart import enabled
            self.autostart = LightSwitch();self.autostart.setAccessibleName('Abrir com o Windows como administrador')
            self.autostart_notice = QLabel(); self.autostart_notice.setWordWrap(True)
            try:
                self.autostart.setChecked(enabled())
            except Exception:
                self.autostart.setEnabled(False)
                self.autostart_notice.setText('Não consegui consultar a inicialização no Windows.')
            form.addRow(field_label('Abrir com o Windows como administrador','','shield-check'),self.autostart); form.addRow(self.autostart_notice)
            self.autostart_notice.setVisible(bool(self.autostart_notice.text()))
            self.autostart.toggled.connect(self._set_windows_autostart)
        from core.personality_view import PersonalityView
        personality_section=SettingsSection('PERSONALIDADE DO JARVIS','Perfil atual','brain')
        self.personality_view=PersonalityView();personality_section.outer.addWidget(self.personality_view)
        profile_layout.addWidget(personality_section)
        save = QPushButton("Salvar perfil");save.setFixedWidth(320);save.setIcon(glyph('save')); save.setObjectName('primaryAction'); save.clicked.connect(self.save);profile_layout.addWidget(save,0,Qt.AlignmentFlag.AlignHCenter)
        self.notice = QLabel(""); self.notice.setWordWrap(True); profile_layout.addWidget(self.notice);profile_layout.addStretch()
        profile_scroll=QScrollArea();profile_scroll.setWidgetResizable(True);profile_scroll.setFrameShape(QFrame.Shape.NoFrame);profile_scroll.setWidget(profile)
        add_page(profile_scroll,"Perfil",QStyle.StandardPixmap.SP_FileDialogInfoView,'profile')
        appearance_page = QWidget();appearance_layout=QVBoxLayout(appearance_page);appearance_layout.setContentsMargins(0,0,8,12);appearance_layout.setSpacing(14)
        projection=SettingsSection('HOLOGRAMA E PROJEÇÕES','Movimento, cor e permanência das informações.','box');appearance_layout.addWidget(projection);form=projection.form
        self.reduced=QCheckBox('Reduzir movimento das projeções');self.reduced.setChecked(bool(cfg.get('reduce_motion',False)));form.addRow(self.reduced)
        self.hold = QSpinBox(); self.hold.setRange(0,120); self.hold.setSuffix(" s"); self.hold.setSpecialValueText("Manter na tela"); self.hold.setValue(int(cfg.get("presentation_hold",15))); self.hold.setMaximumWidth(170); form.addRow("Recolher após a fala",self.hold)
        self.selected_color = cfg.get('ui_color') or '#00d4ff'
        self.color_button = QPushButton(); self.color_button.setAccessibleName('Cor do holograma'); self.color_button.setToolTip('Cor do holograma'); self.color_button.setFixedSize(60,38)
        self.color_button.clicked.connect(self.pick_color); self._update_swatch(); form.addRow('Cor do holograma',self.color_button)
        voice_section=SettingsSection('VOZ E ÁUDIO','Voz principal e dispositivos de áudio.','volume-2');appearance_layout.addWidget(voice_section);form=voice_section.form
        self.speech_provider=QComboBox();self.speech_provider.addItem('Fish Audio · voz DIEF JARVIS','fish_audio');self.speech_provider.addItem('Voz nativa da IA','gemini')
        self.speech_provider.setCurrentIndex(1 if cfg.get('speech_provider','fish_audio')=='gemini' else 0);self.speech_provider.setMaximumWidth(320);form.addRow('Voz principal',self.speech_provider)
        fish_settings=QPushButton('Configurar voz Fish Audio');fish_settings.clicked.connect(lambda:self.open_plugin_settings('fish_audio'));form.addRow(fish_settings)
        from memory.config_manager import AVAILABLE_VOICES, DEFAULT_VOICE
        self.voice = QComboBox(); self.voice.addItems(AVAILABLE_VOICES); self.voice.setCurrentText(cfg.get('voice_name') or DEFAULT_VOICE); self.voice.setMaximumWidth(320); form.addRow('Voz nativa da IA',self.voice)
        audio = QPushButton('Dispositivos de áudio'); audio.clicked.connect(lambda:self.open_overlay(window._open_audio_devices)); form.addRow(audio)
        save_appearance = QPushButton('Salvar aparência');save_appearance.setFixedWidth(320);save_appearance.setIcon(glyph('save')); save_appearance.setObjectName('primaryAction'); save_appearance.clicked.connect(self.save); appearance_layout.addWidget(save_appearance,0,Qt.AlignmentFlag.AlignHCenter)
        self.appearance_notice = QLabel(); self.appearance_notice.setWordWrap(True); appearance_layout.addWidget(self.appearance_notice);appearance_layout.addStretch()
        appearance_scroll=QScrollArea();appearance_scroll.setWidgetResizable(True);appearance_scroll.setWidget(appearance_page)
        add_page(appearance_scroll,'Aparência',QStyle.StandardPixmap.SP_ComputerIcon,'appearance')
        activity = QWidget(); al = QVBoxLayout(activity); al.setContentsMargins(0,0,0,0); self.activity = QTextEdit(); self.activity.setReadOnly(True); al.addWidget(self.activity); add_page(activity,"Atividade",QStyle.StandardPixmap.SP_FileDialogDetailedView,'activity')
        chat = QWidget(); cl = QVBoxLayout(chat); self.chat = QTextEdit(); self.chat.setReadOnly(True); cl.addWidget(self.chat)
        row = QHBoxLayout(); self.message = QLineEdit(); self.message.setPlaceholderText('Mensagem para o Jarvis'); row.addWidget(self.message); send = QPushButton("Enviar"); send.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowForward)); row.addWidget(send); cl.addLayout(row); send.clicked.connect(self.send); self.message.returnPressed.connect(self.send); add_page(chat,"Conversa",QStyle.StandardPixmap.SP_MessageBoxInformation,'chat')
        self.connection_done.connect(self._connection_finished)
        from core.settings_connections import ConnectionsPage
        self.connections_page=ConnectionsPage(self)
        add_page(self.connections_page,"Conexões",QStyle.StandardPixmap.SP_DriveNetIcon,'connections')
        ai = QWidget(); il = QVBoxLayout(ai);il.setContentsMargins(0,0,8,12);il.setSpacing(14)
        engine=SettingsSection('INTELIGÊNCIA PRINCIPAL','Conexão e estado do assistente.','brain');il.addWidget(engine)
        self.ai = QLabel(); self.ai.setWordWrap(True); engine.outer.addWidget(self.ai)
        key_form=engine.form
        self.ai_key=QLineEdit(); self.ai_key.setEchoMode(QLineEdit.EchoMode.Password); self.ai_key.setPlaceholderText('Credencial salva' if cfg.get('gemini_api_key') else 'Chave Gemini'); self.ai_key.setAccessibleName('Chave da IA Gemini'); key_form.addRow('Chave Gemini',self.ai_key)
        key_save=QPushButton('Salvar chave da IA');key_save.setIcon(glyph('save'));key_save.setMaximumWidth(230); key_save.clicked.connect(self.save_ai_key); engine.outer.addWidget(key_save)
        self.ai_notice=QLabel(); self.ai_notice.setWordWrap(True); engine.outer.addWidget(self.ai_notice)
        memory_section=SettingsSection('MEMÓRIA','Informações que o JARVIS guarda para as conversas.','book-open');il.addWidget(memory_section)
        for title, callback in (("Consultar memória",window._open_memory_panel),):
            button = QPushButton(title);button.setIcon(glyph('book-open'));button.setMaximumWidth(230); button.clicked.connect(lambda checked=False, cb=callback:self.open_overlay(cb)); memory_section.outer.addWidget(button)
        il.addStretch(); add_page(ai,"IA e memória",QStyle.StandardPixmap.SP_DriveHDIcon,'ai')
        order=['profile','appearance','connections','ai','chat','activity']
        pages={key:self.tabs.widget(index) for key,index in self.page_indices.items()}
        items={key:self.navigation.item(index).clone() for key,index in self.page_indices.items()}
        self.navigation.blockSignals(True);self.navigation.clear()
        for page in pages.values():self.tabs.removeWidget(page)
        for key in order:
            self.page_indices[key]=self.tabs.count();self.tabs.addWidget(pages[key]);self.navigation.addItem(items[key])
        self.navigation.blockSignals(False)
        for field, name in ((self.name,'Como chamar você'),(self.city,'Cidade do clima'),(self.interests,'Preferências de notícias'),(self.count,'Quantidade de notícias'),(self.message,'Mensagem para o Jarvis')):
            field.setAccessibleName(name)
        for button in self.findChildren(QPushButton):
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            if button not in (close,self.color_button):
                button.setMaximumWidth(600)
        from core.hud_glass import HudGlassFrame
        for frame in self.findChildren(HudGlassFrame):frame.set_motion_reduced(cfg.get('reduce_motion',False))
        self.navigation.currentRowChanged.connect(self._page_selected)
        self.navigation.setCurrentRow(0)
        self.timer = QTimer(self); self.timer.timeout.connect(self._refresh_tick); self.refresh()

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
            from ui import _FuiOverlay
            created=[w for w in self.window.centralWidget().findChildren(_FuiOverlay,options=Qt.FindChildOption.FindDirectChildrenOnly) if w.isVisible()]
        if not created:return
        self._mount_detail(created[-1])

    def _mount_detail(self,overlay,title=None):
        self._detail_transition=True
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
        self.section_title.setText(title or self.navigation.currentItem().text())
        self._detail_transition=False

    def _leave_detail(self):
        overlay=getattr(self,'_detail_overlay',None)
        if overlay:
            overlay.hide()
        self.tabs.setCurrentIndex(self._return_page)
        self.section_title.setText(self.navigation.item(self._return_page).text())

    def eventFilter(self,watched,event):
        if watched is getattr(self,'_detail_overlay',None) and event.type()==QEvent.Type.Hide and not getattr(self,'_detail_transition',False):
            def restore():
                if not self._closed and watched is getattr(self,'_detail_overlay',None) and not watched.isVisible() and self.tabs.currentWidget() is getattr(self,'_detail_page',None):self._leave_detail()
            QTimer.singleShot(0,restore)
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
        from memory.config_manager import save_api_keys
        try:
            save_api_keys(key,path=self.config_path)
        except (OSError,ValueError):
            self.ai_notice.setText('Não foi possível salvar a credencial. Confira o acesso à pasta do Jarvis.'); return
        self.ai_key.clear(); self.ai_key.setPlaceholderText('Credencial salva')
        self.ai_notice.setText('Credencial salva. Reconectando para verificar a IA.')
        if self.window.on_voice_change:
            if self._ai_check:
                self._connection_checks.invalidate('ai');self._ai_check=None
            self.check_ai(reset_session=True)

    def _connection_worker(self, callback,provider='gmail',connecting=False):
        generation=self._connection_checks.begin(provider,connecting)
        if generation is None:
            self.connection_notice.setText('Já existe uma verificação ou autorização em andamento para esta conexão.');return
        self.connection_notice.setText("Aguardando conexão/autorização…")
        self.refresh()
        reference=weakref.ref(self);checks=self._connection_checks
        def complete(state,message,ok=False):
            if not checks.finish(provider,generation,state,message):return
            target=reference()
            if target is not None and not target._closed:
                try:target.connection_done.emit({'provider':provider,'generation':generation,'ok':ok,'message':message})
                except RuntimeError:pass
        future=None
        def expired():
            if future is not None:future.cancel()
            complete('error','A conexão demorou demais. Confira a autorização ou a rede e tente novamente.')
        timeout=threading.Timer(AUTHORIZATION_TIMEOUT if connecting else CONNECTION_TIMEOUT,expired)
        timeout.daemon=True
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
                    from core.connection_errors import describe
                    ok,message=False,describe(error)
            timeout.cancel()
            complete(state,message,ok)
        try:future=_CONNECTION_WORK.submit(worker)
        except (queue.Full,RuntimeError):
            complete('error','Há conexões ocupadas. Aguarde as consultas atuais e tente novamente.')
            return
        timeout.start()
        if not checks.get(provider).get('busy'):timeout.cancel()

    def _connection_finished(self, result):
        if self._closed:return
        current=self._connection_checks.get(result['provider'])
        if current.get('generation')!=result.get('generation') or current.get('busy'):return
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
        if not gmail.LOCK.acquire(blocking=False):
            self.connection_notice.setText('A autorização anterior do Gmail ainda está encerrando. Aguarde antes de alterar a credencial.')
            return
        try:
            gmail.import_credentials(path)
            self.gmail_client.setText(gmail.credential_client_id()); self.gmail_secret.clear()
            self.gmail_secret.setPlaceholderText("Credencial salva")
            self.connection_notice.setText("Credencial importada. Autorização da conta pendente.")
            self._connection_checks.invalidate('gmail');self.connections_page._local_at=0;self.refresh()
        except Exception as error:
            self.connection_notice.setText(str(error) if isinstance(error,ValueError) else "Arquivo de credenciais inválido.")
        finally:gmail.LOCK.release()

    def save_gmail_credentials(self):
        from core import gmail_connection as gmail
        from core.local_data import LOCK,atomic_write
        from memory import config_manager
        if self._connection_checks.get('gmail').get('busy'):
            self.connection_notice.setText('Aguarde a verificação ou autorização atual do Gmail.');return False
        if not gmail.LOCK.acquire(blocking=False):
            self.connection_notice.setText('A autorização anterior do Gmail ainda está encerrando. Aguarde antes de alterar a credencial.')
            return False
        rollback_failed=False
        try:
            client = self.gmail_client.text().strip()
            secret = self.gmail_secret.text().strip()
            email = self.gmail_email.text().strip()
            if email and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
                raise ValueError("Informe um endereço de e-mail válido.")
            with LOCK:
                gmail.prepare_storage();config_manager.prepare_storage()
                paths=(gmail.CREDENTIALS,config_manager.CONFIG_FILE)
                previous={path:path.read_bytes() if path.exists() else None for path in paths}
                try:
                    if secret or client != gmail.credential_client_id() or not gmail.CREDENTIALS.exists():
                        gmail.configure_credentials(client, secret)
                    gmail.save_expected_account(email)
                except Exception:
                    # Restore both stores, including a file created by this attempt.
                    for path,data in previous.items():
                        try:
                            current=path.read_bytes() if path.exists() else None
                            if current==data:continue
                            if data is None:path.unlink(missing_ok=True)
                            else:atomic_write(path,data)
                        except Exception:rollback_failed=True
                    raise
            self.gmail_secret.clear(); self.gmail_secret.setPlaceholderText("Credencial salva")
            self.connection_notice.setText("Credencial e conta desejada salvas. A conexão depende da autorização do Google.")
            self._connection_checks.invalidate('gmail');self.connections_page._local_at=0
            self.refresh()
            return True
        except Exception as error:
            if rollback_failed:
                message='Falha ao salvar o Gmail e ao restaurar os arquivos anteriores. As credenciais podem ter sido alteradas; confira a configuracao antes de autorizar novamente.'
                self._connection_checks.invalidate('gmail')
                generation=self._connection_checks.begin('gmail')
                self._connection_checks.finish('gmail',generation,'error',message)
                self.connections_page._local_at=0
                self.refresh()
                self.connection_notice.setText(message)
            else:
                self.connection_notice.setText(str(error) if isinstance(error, ValueError) else "Não foi possível salvar a credencial Gmail.")
            return False
        finally:gmail.LOCK.release()

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

    def _set_windows_autostart(self, checked):
        from core.windows_autostart import set_enabled, enabled
        try:
            set_enabled(checked)
            actual = enabled()
            if actual != checked:
                raise RuntimeError('Estado nao confirmado pelo Windows.')
        except Exception:
            try:
                actual = enabled()
            except Exception:
                actual = not checked
            self.autostart_notice.setText('Não consegui confirmar a alteração. Abra o Jarvis como administrador e tente novamente.')
        else:
            self.autostart_notice.setText('Início com o Windows ativado.' if actual else 'Início com o Windows desativado.')
        self.autostart.blockSignals(True)
        self.autostart.setChecked(actual)
        self.autostart.blockSignals(False)
        self.window._update_autostart_btn(actual)
        self.autostart_notice.show()

    def _set_panel_sounds_muted(self,muted):
        sounds=getattr(self.window,'_ui_sounds',None)
        if sounds is not None:sounds.set_muted(muted)

    def save(self):
        from memory.config_manager import mutate_config,AVAILABLE_VOICES,DEFAULT_VOICE
        name=self.assistant_name.text().strip() or 'DIEF JARVIS'
        user_name=self.name.text().strip()[:100]
        color=self.selected_color.strip().lower()
        visual=self.visual.currentData()
        voice=self.voice.currentText().strip()
        try:
            def update(cfg):
                cfg.update(speech_provider=self.speech_provider.currentData(),assistant_name=name,user_name=user_name,ui_color=color,
                           hud_style=visual if visual in ('face','core') else 'face',voice_name=voice if voice in AVAILABLE_VOICES else DEFAULT_VOICE,city=self.city.text().strip()[:120],
                           news_interests=self.interests.toPlainText().strip()[:1000],news_count=self.count.value(),presentation_hold=self.hold.value(),morning_brief_enabled=self.brief.isChecked(),reduce_motion=self.reduced.isChecked(),panel_sounds_muted=self.panel_sounds_muted.isChecked())
            mutate_config(update,path=self.config_path)
        except (OSError,ValueError):
            message='Não foi possível salvar o perfil e a aparência. Confira o arquivo de preferências e o acesso à pasta do Jarvis.'
            self.notice.setText(message);self.appearance_notice.setText(message)
            return
        self._set_panel_sounds_muted(self.panel_sounds_muted.isChecked())
        self.window.hud.hud_style=visual if visual in ('face','core') else 'face'
        SettingsHub._apply_saved_identity(self,name,color)
        self.window._update_brief_btn(self.brief.isChecked())
        from core.hud_glass import HudGlassFrame
        for frame in self.window.findChildren(HudGlassFrame):
            frame.set_motion_reduced(self.reduced.isChecked())
        for key in ('_terminal','_execution'):
            panel=getattr(self.window,key,None)
            if panel: panel.surface.set_motion_reduced(self.reduced.isChecked())
        self.animate_entry()
        self.core_preview.sync_preview()
        if self.window.on_voice_change:
            self.window.on_voice_change()
        self.notice.setText("Perfil salvo. Clima e notícias usam essas preferências nas próximas consultas.")
        self.appearance_notice.setText('Aparência salva.')

    def _apply_saved_identity(self,name,color):
        # The window's identity callback also writes config; apply only its UI here.
        from ui import current_palette,apply_ui_accent,retheme_all_widgets
        window=self.window;display=name.upper()
        window._assistant_name=name;window.hud._assistant_name=display
        window.setWindowTitle('DIEF JARVIS')
        title=getattr(window,'_title_lbl',None)
        if title is not None:title.setText(display)
        subtitle=getattr(window,'_sub_lbl',None)
        if subtitle is not None:
            subtitle.setText('Assistente pessoal de inteligência artificial' if display in ('JARVIS','J.A.R.V.I.S') else 'Assistente pessoal de IA')
        log=getattr(window,'_log',None)
        if log is not None:
            log._ai_name_lc=name.lower()
            log.append_log('SYS: Identidade atualizada: '+display)
        if color:
            old=current_palette()
            if apply_ui_accent(color):retheme_all_widgets(old,current_palette())

    def send(self):
        text = self.message.text().strip()
        if text and self.window.on_text_command:
            self.window._log.append_log("Você: " + text)
            threading.Thread(target=self.window.on_text_command,args=(text,),daemon=True).start()
            self.message.clear()

    def _refresh_tick(self):
        if self.isVisible() and not self.isMinimized():self.refresh(active_only=True)

    def refresh(self,active_only=False):
        page=next((key for key,index in self.page_indices.items() if index==self.tabs.currentIndex()),None) if active_only else None
        if not active_only or page=='profile':self.personality_view.refresh()
        if not active_only or page in ('activity','chat'):
            log = self.window._log.toPlainText()[-40000:]
            if (not active_only or page=='activity') and self.activity.toPlainText()!=log:
                self.activity.setPlainText(log); self.activity.verticalScrollBar().setValue(self.activity.verticalScrollBar().maximum())
            if (not active_only or page=='chat') and getattr(self,'_chat_source_log',None)!=log:
                self._chat_source_log=log
                dialogue = "\n".join(line for line in log.splitlines() if any(name in line.lower() for name in ("você:","you:","jarvis:","dief jarvis:")))
                if self.chat.toPlainText()!=dialogue:
                    self.chat.setPlainText(dialogue); self.chat.verticalScrollBar().setValue(self.chat.verticalScrollBar().maximum())
        state = getattr(self.window,"_connection_status",{"connected":False,"model":"--"})
        self._complete_ai_check(state)
        if not active_only or page=='connections':
            plugins = self.window.get_plugins() if self.window.get_plugins else []
            self.connections_page.refresh(plugins,state)
            self.connection_notice.setVisible(bool(self.connection_notice.text()))
        if active_only and page!='ai':return
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
        if self._complete_ai_check(getattr(self.window,'_connection_status',{})):return
        self._ai_timeout.stop()
        self._connection_checks.finish('ai',self._ai_check[0],'error','Não houve confirmação de uma nova conexão da IA. Confira a chave e a internet.')
        self._ai_check=None;self.ai_notice.setText('O teste não confirmou a conexão. Confira a chave e a internet.');self.refresh()

    def _complete_ai_check(self,state):
        if not self._ai_check or not state.get('connected') or state.get('revision',0)<=self._ai_check[1]:return False
        self._connection_checks.finish('ai',self._ai_check[0],'connected','Sessão da IA reconectada e confirmada.')
        self._ai_check=None;self._ai_timeout.stop();self.ai_notice.setText('Conexão da IA confirmada.')
        return True

    def _page_selected(self,index):
        if self.isVisible():self.refresh(active_only=True)
        if index!=self.page_indices.get('connections') or not self.isVisible():return
        if os.environ.get('QT_QPA_PLATFORM')=='offscreen':return
        if hasattr(self.window,'_verify_saved_connections'):
            self.window._verify_saved_connections()

    def showEvent(self,event):
        self._closed=False;super().showEvent(event)
        if hasattr(self,'timer'):self.timer.start(1000)
        if hasattr(self,'connections_page'):self._page_selected(self.navigation.currentRow())

    def hideEvent(self,event):
        if hasattr(self,'timer'):self.timer.stop()
        super().hideEvent(event)

    def resizeEvent(self,event):
        super().resizeEvent(event)
        if hasattr(self,'rail'):
            self.rail.setFixedWidth(172 if self.width()<1100 else 190)
            margin=12 if self.width()<1000 else 22
            self.workspace_layout.setContentsMargins(margin,18,margin,18)
        if hasattr(self,'profile_top'):
            self.profile_top.setDirection(QHBoxLayout.Direction.TopToBottom if self.width()<1150 else QHBoxLayout.Direction.LeftToRight)
            self.core_preview.setVisible(self.width()>=1150)

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
        if name=='fish_audio':self.open_plugin_settings(name);return
        from core.extension_suite import CATALOG,status,verify
        if name in CATALOG:
            state=status(name)
            if not state['installed']:
                from core.extension_install import install
                self._connection_worker(lambda:install(name),'plugin:'+name if not state['account_required'] else name)
            elif not state['authorized']:self.open_plugin_settings(name)
            else:self._connection_worker(lambda:verify(name),'plugin:'+name if not state['account_required'] else name)
            return
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
        if name=='fish_audio':self.open_plugin_settings(name);return
        from core.extension_suite import CATALOG
        if name in CATALOG:self.open_plugin_settings(name);return
        plugins={p['name']:p for p in (self.window.get_plugins() if self.window.get_plugins else [])}
        record=plugins.get(name,{})
        if not record.get('valid'):self.open_overlay(self.window._open_plugin_manager);return
        if not record.get('enabled'):self.enable_plugin(name);return
        if self._connection_checks.get(name).get('busy'):
            self.connection_notice.setText('Aguarde a verificação atual antes de iniciar outra autorização.');return
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
        from ui import PluginSettingsOverlay
        panel=PluginSettingsOverlay(selected,self)
        panel._test_done.connect(lambda ns,ok,msg:self._plugin_authorization_finished(ns,ok,msg))
        self._mount_detail(panel,selected[0].get('title') or name)

    def open_skill(self,identifier):
        from core.skill_library import run
        value=run({'action':'read','id':identifier})
        panel=QWidget(self);layout=QVBoxLayout(panel);layout.setContentsMargins(0,8,0,12)
        source=QLabel('Fonte: '+value['source']);source.setWordWrap(True);source.setObjectName('settingsMeta');layout.addWidget(source)
        text=QTextEdit();text.setReadOnly(True);text.setPlainText(value['text']);layout.addWidget(text,1)
        self._mount_detail(panel,'Skill · '+identifier)

    def _plugin_authorization_finished(self,name,ok,message):
        from core.resource_policy import LOCAL
        provider=('desktop' if name=='desktop_accessibility' else 'plugin:'+name) if name in LOCAL else name
        self._connection_checks.invalidate(provider)
        self.connections_page._external_local.pop(name,None)
        generation=self._connection_checks.begin(provider)
        if generation is not None:
            state='connected' if ok else 'error'
            from core.resource_policy import external_status
            from core.resource_policy import LOCAL,local_status
            local=local_status(name) if name in LOCAL else external_status(name)
            if ok and name not in LOCAL and not local.get('connected'):state='pending'
            self._connection_checks.finish(provider,generation,state,message)
        self.connection_notice.setText(message)
        self.refresh()
