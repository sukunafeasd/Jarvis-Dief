"""Model tool adapter; user context is supplied exclusively by the host."""
import json

from core.ultron import Runtime


def ultron_protocol(parameters, player=None):
    context_provider = getattr(player, 'ultron_user_context', None)
    authorization_provider = getattr(player, 'ultron_authorization', None)
    present = getattr(player, 'present_ultron', None)
    runtime = getattr(player, 'ultron_runtime', None)
    if (not callable(context_provider) or not callable(authorization_provider)
            or not callable(present) or not isinstance(runtime, Runtime)):
        return json.dumps({'accepted': False, 'mode': 'rejected',
                           'speech': 'Integracao nativa ULTRON indisponivel.'})
    context = context_provider()
    context = dict(context) if isinstance(context, dict) else {}
    command = parameters.get('command') if isinstance(parameters, dict) else None
    result = runtime.command(command, user_text=context.get('text'), user_turn=context.get('serial'),
                             authorization=lambda: authorization_provider(context))
    snapshot = runtime.snapshot()
    from core.ultron_presentation import projection
    result['observations']=projection(snapshot)
    result['ok']=bool(result.get('accepted')) and result.get('mode')!='rejected'
    result['completed']=result.get('mode') not in ('activation','activation_question','scan_wait','question','operation')
    if result.get('mode')=='question':result['state']='awaiting_confirmation'
    present(snapshot, result)
    return json.dumps(result, ensure_ascii=False)


TOOL = {
    'name': 'ultron_protocol',
    'description': 'Protocolo ULTRON nativo. Use o comando literal do usuario atual. '
                   'Ativacao aceita variacoes claras como ativa o protocolo do ultron ou ligue o Ultron. '
                   'Mencao curta ambigua como vamos pro Ultron gera pergunta; somente o proximo sim real dentro do prazo ativa diagnostico. '
                   'Negacoes, hipoteses ou pedidos misturados nao autorizam ativacao. Confirmacao exige novo turno real. '
                   'Somente status ou diagnostico podem ser consultados sem pedido literal. '
                   'Use speech e observations na resposta; anuncie CPU, memoria, disco e observacoes por trechos. '
                   'Dados aparecem perto do planeta seguindo o audio real, sem botoes ou cards. '
                   'Cofre, monitorar, simular falha, limpeza segura, seguranca maxima, reparar windows: '
                   'use o pedido literal, preserve a pergunta de confirmacao e aguarde novo turno. '
                   'Nao invente sim, consentimento, sucesso, malware ou reparo concluido.',
    'parameters': {'type': 'OBJECT', 'properties': {'command': {'type': 'STRING'}},
                   'required': ['command']},
    'handler': ultron_protocol,
}
