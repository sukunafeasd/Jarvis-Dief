from core.windows_accessibility import run

PLUGIN = {
    "name": "desktop_accessibility",
    "description": "Controle dos aplicativos do Windows. Consulte windows e depois inspect, com control_query/offset opcionais. Use control_id observado (expira em 90 segundos) ou name/automation_id/type exatos. Ações: invoke/select/read/fill/expand/collapse/toggle/scroll/press. Prefira operações em segundo plano; allow_visible=true permite ativar a janela verificada quando necessário. Teclas exigem confirmação do foco. input_mode=keyboard permite eventos reais quando o preenchimento semântico não gera resultados. Examine novamente após cada ação; um clique não prova sucesso. Resultado incerto: nunca repita às cegas. Não preencha senhas. Nem todo aplicativo oferece controles acessíveis.",
    "parameters": {"type": "OBJECT", "properties": {
        "action": {"type": "STRING", "enum": ["windows","inspect","focus","invoke","select","fill","read","expand","collapse","toggle","scroll","press"]},
        "handle": {"type": "INTEGER"}, "name": {"type": "STRING"},
        "automation_id": {"type": "STRING"}, "type": {"type": "STRING"},
        "text": {"type": "STRING"}}, "required": ["action"]},
}

from actions.app_control import TOOL
for name in ('control_id','control_query','offset','allow_visible','input_mode','key','direction','amount','count'):
    PLUGIN['parameters']['properties'][name]=TOOL['parameters']['properties'][name].copy()
