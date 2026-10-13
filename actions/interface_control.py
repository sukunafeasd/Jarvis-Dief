"""Semantic commands for the assistant's own window, marshalled onto Qt."""
import json


def interface_control(parameters, player=None):
    if player is None:
        return json.dumps({"ok": False, "error": "Interface indisponível."})
    result=player.control_interface(parameters.get("action", "inspect"),
                                               parameters.get("value", ""),
                                               parameters.get("setting", ""))
    if parameters.get('action')=='environment' and isinstance(result,dict) and result.get('ok'):
        environment=result.get('screen',{}).get('environment',{})
        result={**result,'environment_result':{'requested_mode':environment.get('requested_mode'),
                  'resolved_mode':environment.get('resolved_mode'),'renderer':environment.get('renderer'),
                  'planet':environment.get('planet')},
                'note':'Confirme o modo resolvido. O pedido explicito de modo permanece durante leitura; configuracoes abertas ainda priorizam foco. Se o renderizador estiver carregando ou em fallback, nao prometa uma transicao 3D concluida.'}
    return json.dumps(result,ensure_ascii=False)


TOOL = {
    "name": "interface_control",
    "description": "Controle da SUA cena do Jarvis, não do navegador. Use inspect antes de referir a posições e seleções. Notícias ficam no holograma principal; Gmail e WhatsApp aparecem acima. Abra settings/profile/audio/memory/plugins/connections/remote/commands/activity/chat/ai ou dados já consultados. pin fixa QUALQUER assunto consultado: weather, tasks, calendar, news, gmail, whatsapp, system, memory, files, search, data; value vazio fixa o conteudo atual, inclusive resposta textual. Nomes em português como agenda, tarefas, noticias e arquivos também funcionam. Cada prévia tem ícone compacto próprio e persiste entre sessões. Para foto use pin_image. Até quatro prévias simultâneas; não substitua outra sem pedido. Não diga que só clima pode ser fixado. Consulte o assunto antes de pin se ainda não há dados. clear preserva TODAS as prévias, fotos e composições fixadas. Remova somente com unpin e pedido explícito. visual troca face/core; color muda destaque; focus seleciona posição; move reposiciona; settle recolhe; return restaura contexto; fullscreen alterna tela cheia. Dados reais vêm das ferramentas existentes. Para composições livres use visual_composer; inspect inclui IDs reais. Não fabrique valores nem contas conectadas. Exija ok=true para confirmar qualquer mudança.",
    "parameters": {"type": "OBJECT", "properties": {
        "action": {"type": "STRING", "enum": ["inspect", "catalog", "environment", "resume", "open", "close", "clear", "visual", "color", "focus", "pin", "unpin", "move_pin", "return", "fullscreen", "setting", "move", "settle", "rest", "request_image", "pin_image", "close_terminal"]},
        "setting": {"type": "STRING", "enum": ["assistant_name", "user_name", "voice", "microphone", "briefing","bottom_left","bottom_right","upper_left","upper_right"], "description": "resume retoma uma apresentacao pausada quando o usuario pedir para continuar; confira presentation.paused no inspect. Nunca retome um assunto antigo por causa de fala nova de outro tema. For setting: names/voice/microphone/briefing. For move_pin: choose a corner; value is the pinned object's actual key from inspect. Rest uses value on/off. close uses current domain/terminal/execution and preserves pins. catalog describes approved icon/renderer/tool bindings, NOT arbitrary source-code execution."},
        "value": {"type": "STRING", "description": "environment controla o observatorio: normal/auto restaura, foco simplifica o fundo, analise/execucao/exploracao muda o ambiente. sol/mercurio/venus/terra/marte/jupiter/saturno/urano/netuno/lua destaca um corpo 3D. Orbitas artisticas, nao simulacao astronomica; nao invente batidas ou etapas executadas. Leitura de noticias/mensagens tem prioridade visual e preserva o modo solicitado para depois. Abra terminal/chat/commands para conversa e anexos; execution mostra etapas reais. Configurações: settings/profile/audio/memory/plugins/connections/remote/activity. Visual face/core; rest on/off entra ou sai do repouso. request_image aguarda foto escolhida; pin_image usa ID real de anexo. close_terminal fecha o terminal. Cor #RRGGBB; focus usa número de item; move left/right/center/auto."}
    }, "required": ["action"]},
    "handler": interface_control,
}
