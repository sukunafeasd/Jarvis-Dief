"""Rotulos de apresentacao; os identificadores das ferramentas nao mudam."""
STATES={'idle':'Em repouso','sleeping':'Em repouso','resting':'Em repouso','listening':'Escutando',
    'thinking':'Analisando','processing':'Processando','speaking':'Falando','booting':'Iniciando',
    'executing':'Executando','active':'Ativo','muted':'Microfone silenciado','error':'Erro',
    'connecting':'Conectando','disconnected':'Desconectado','connected':'Conectado'}
VISUALS={'face':'Rosto','core':'Núcleo'}
TOOLS={'desktop_accessibility':'Controle de aplicativos','gmail_control':'Gmail',
    'google_calendar':'Google Agenda','google_drive':'Google Drive','spotify_control':'Spotify',
    'document_reader':'Documentos e anexos','personal_routines':'Rotinas pessoais','structured_browser':'Navegação estruturada',
    'whatsapp_web':'WhatsApp Web','app_control':'Aplicativos','send_message':'Enviar mensagem',
    'weather_report':'Clima','organizer':'Agenda e tarefas','web_search':'Pesquisa',
    'interface_control':'Painel do Jarvis','memory_control':'Memória','system_status':'Sistema',
    'local_resources':'Contatos, notas e projetos','file_library':'Arquivos e conhecimento',
    'task_execution':'Planejamento e resultados','office_resources':'Documentos e planilhas',
    'resource_backups':'Backup dos dados locais','gmail_compose':'Gmail · rascunhos e envio',
    'home_automation':'Casa inteligente','desktop_resources':'Utilidades do computador',
    'resource_diagnostics':'Diagnostico e reparacao','outlook_service':'Microsoft Outlook',
    'mcp_bridge':'Servidor MCP','resource_monitor':'Monitoramento de arquivos',
    'resource_updates':'Atualizacoes do Jarvis','calendar_planning':'Planejamento de agenda','notion_service':'Notion'}


def state_label(value):
    return STATES.get(str(value).lower(),'Estado indisponível')


def tool_label(value):
    return TOOLS.get(value,value)
