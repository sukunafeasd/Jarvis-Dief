"""Semantic commands for the assistant's own window, marshalled onto Qt."""
import json


def interface_control(parameters, player=None):
    if player is None:
        return json.dumps({"ok": False, "error": "Interface indisponível."})
    result=player.control_interface(parameters.get("action", "inspect"),
                                               parameters.get("value", ""),
                                               parameters.get("setting", ""))
    from core.interface_verification import verify_result
    result=verify_result(parameters.get('action','inspect'),parameters.get('value',''),result,parameters.get('setting',''))
    if parameters.get('action')=='environment' and isinstance(result,dict) and result.get('ok'):
        environment=result.get('screen',{}).get('environment',{})
        result={**result,'environment_result':{'requested_mode':environment.get('requested_mode'),
                  'resolved_mode':environment.get('resolved_mode'),'renderer':environment.get('renderer'),
                  'planet':environment.get('planet')},
                'note':'Confirme o modo resolvido. O pedido explicito de modo permanece durante leitura; configuracoes abertas ainda priorizam foco. Se o renderizador estiver carregando ou em fallback, nao prometa uma transicao 3D concluida.'}
    return json.dumps(result,ensure_ascii=False)


TOOL = {
    "name": "interface_control",
    "description": "Controle da SUA cena, nao do navegador. Use inspect antes de referir IDs e posicoes. Clima consultado e holograma sem card; pin cria previa com vidro azul e icone compacto. Ate SEIS previas simultaneas de qualquer assunto consultado: weather/tasks/calendar/news/gmail/whatsapp/system/memory/files/search/data ou fotos via pin_image. Nomes em portugues tambem funcionam. value vazio fixa o conteudo atual. Nao invente dados: consulte a ferramenta real primeiro. move_pin reposiciona em QUALQUER ponto e pode alterar o tamanho: value e a chave real do inspect, setting e JSON com x,y entre 0 e 1 (canto superior esquerdo da previa relativo a tela), width,height opcionais em proporcao. Exemplo setting={\"x\":0.04,\"y\":0.32,\"width\":0.22,\"height\":0.20}. Tambem aceita row/column para organizar todas as previas em fila/coluna, ou bottom_left/bottom_right/upper_left/upper_right/middle_left/middle_right. Nao restringir a quatro cantos. Leia bounds no inspect para confirmar o enquadramento real: a composicao evita colisoes e protege leitura. Posicoes e tamanhos persistem entre sessoes. clear preserva TODAS as previas e fotos; remova apenas com unpin e pedido explicito. Noticias permanecem no nucleo. Abra settings/profile/audio/memory/plugins/connections/remote/commands/activity/chat/ai; visual troca face/core, color muda destaque, focus seleciona item, move reposiciona holograma, return restaura contexto, fullscreen alterna tela cheia. Para objetos livres use visual_composer. ok=true sozinho nao prova o efeito visual: confira verification.postcondition_verified, layout_animating e preserved. null significa nao verificado; false significa falha; nao afirme ter visto pixels com base no estado da aplicacao.",
    "parameters": {"type": "OBJECT", "properties": {
        "action": {"type": "STRING", "enum": ["inspect", "catalog", "environment", "resume", "open", "close", "clear", "visual", "color", "focus", "pin", "unpin", "move_pin", "return", "fullscreen", "setting", "move", "settle", "rest", "request_image", "pin_image", "close_terminal"]},
        "setting": {"type": "STRING", "description": "Para move_pin: JSON {x,y,width,height} normalizado, row/column ou canto nomeado; use a chave real do inspect em value. Para setting: assistant_name/user_name/voice/microphone/briefing. resume retoma apenas com pedido explicito. rest usa value on/off. close preserva pins. catalog descreve renderizadores seguros, nao codigo arbitrario."},
        "value": {"type": "STRING", "description": "environment controla o observatorio: normal/auto restaura, foco simplifica o fundo, analise/execucao/exploracao muda o ambiente. sol/mercurio/venus/terra/marte/jupiter/saturno/urano/netuno/lua destaca um corpo 3D. Orbitas artisticas, nao simulacao astronomica; nao invente batidas ou etapas executadas. Leitura de noticias/mensagens tem prioridade visual e preserva o modo solicitado para depois. Abra terminal/chat/commands para conversa e anexos; execution mostra etapas reais. Configurações: settings/profile/audio/memory/plugins/connections/remote/activity. Visual face/core; rest on/off entra ou sai do repouso. request_image aguarda foto escolhida; pin_image usa ID real de anexo. close_terminal fecha o terminal. Cor #RRGGBB; focus usa número de item; move left/right/center/auto."}
    }, "required": ["action"]},
    "handler": interface_control,
}

TOOL['parameters']['properties']['action']['enum'].append('spectro')
TOOL['description']+=' Modo Espectro: prefira a ferramenta spectro_control para controles estruturados. action=spectro tambem aceita enter/exit/scale/opacity/position/reset/minimal/clear/privacy/context/highlight/note/quiet. setting JSON usa factor/size para scale, value/delta para opacity, anchor para position. Leia completed e spectro.ready/bounds. Observacao depende de autorizacao real por aplicativo.'
