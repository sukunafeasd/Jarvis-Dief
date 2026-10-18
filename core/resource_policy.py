"""Disponibilidade local nao equivale a autorizacao de uma conta externa."""
import importlib.util
import os

EXTERNAL={'google_calendar','google_drive','spotify_control','gmail_compose','home_automation','outlook_service','mcp_bridge','notion_service','github_mcp','context7','deep_research'}
EXTERNAL.add('fish_audio')
LOCAL={
 'planet_knowledge': ((), 'Fatos NASA e comparacoes; escala artistica separada das medidas reais.'),
 'playwright_mcp': (('mcp',), 'Navegador estruturado MCP; verifica runtime separado.'),
 'windows_mcp': (('mcp',), 'Controles Windows MCP; runtime separado Python 3.13.'),
 'markitdown': (('markitdown',), 'Extracao de documentos em texto, sem macros.'),
 'qdrant_memory': (('qdrant_client','fastembed'), 'Busca semantica local; modelo carregado ao usar.'),
 'local_transcription': (('faster_whisper',), 'Transcricao de arquivos em portugues; modelo carregado ao usar.'),
 'skill_library': ((), 'Skills disponiveis por padrao; consulta sob demanda sem executar scripts.'),
 'structured_browser':(('playwright',),'Navegador proprio do Jarvis; logins em sites sao separados.'),
 'document_reader':(('pdfplumber','docx','openpyxl','pptx','pytesseract'),'Leitura local e anexos; OCR usa Tesseract quando instalado.'),
 'personal_routines':(('sqlite3',),'Rotinas locais; executam enquanto o Jarvis esta aberto.'),
 'local_resources':(('sqlite3',),'Contatos, notas, projetos e transcricoes locais.'),
 'file_library':(('sqlite3','pdfplumber','docx'),'Busca e indexacao em pasta ou arquivo escolhido.'),
 'office_resources':(('docx','openpyxl','PIL'),'Documentos, planilhas e conversao local de imagens.'),
 'task_execution':((),'Planejamento e consulta de resultados reais das ferramentas.'),
 'resource_backups':(('sqlite3',),'Backup local sem incluir arquivos de autorizacao das contas.'),
 'desktop_resources':(('pyperclip','sounddevice'),'Clipboard, notas Markdown, volume e consulta Git.'),
 'resource_diagnostics':(('pip',),'Diagnostico e reparacao das dependencias declaradas.'),
 'resource_monitor':(('sqlite3',),'Monitoramento dos arquivos escolhidos pelo usuario.'),
 'resource_updates':(('requests',),'Consulta publicacoes oficiais; instalacao automatica ainda pendente.'),
 'calendar_planning':((),'Conflitos e horarios da fonte consultada; Google exige autorizacao propria.'),
 'desktop_accessibility':(('pywinauto','pythoncom'),'Controle de aplicativos acessiveis do Windows.'),
}


def local_status(name):
    from core.extension_suite import CATALOG,status
    if name in CATALOG:
        value=status(name)
        return {**value,'local_available':value['installed'],'account_required':False,'detail':value['message']}
    modules,detail=LOCAL[name]
    missing=[module for module in modules if importlib.util.find_spec(module) is None]
    available=not missing
    if name=='desktop_accessibility':
        from core.elevation import is_admin
        available=available and os.name=='nt' and is_admin()
        if not available:detail+=' Requer Windows, dependencias e administrador.'
    if name=='document_reader' and available:
        from core.document_reader import ocr_engine
        detail+=' OCR disponivel.' if ocr_engine() else ' OCR requer Tesseract.'
    return {'local_available':available,'account_required':False,'missing_dependencies':missing,'detail':detail,
        'state':'available' if available else 'error','message':detail if available else 'Ferramenta local requer reparacao. '+detail}


def external_status(name):
    if name not in EXTERNAL:raise ValueError('Servico externo desconhecido.')
    if name=='fish_audio':
        from core.fish_audio import status
        return status()
    from core.extension_suite import CATALOG,status
    if name in CATALOG:return status(name)
    if name in ('google_calendar','google_drive','gmail_compose'):
        from core.google_services import status
        return status(name)
    if name=='spotify_control':
        from core.spotify_service import status
        return status()
    from importlib import import_module
    return import_module('core.'+name).status()
