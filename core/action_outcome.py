"""Shared interpretation of tool evidence, never inferred from animation."""
import json
import re


class DispatchBindingError(Exception):
    """The handler was not entered because its call contract could not bind."""


def dispatch_problem(code, *, started=False, exception=None):
    """Describe dispatch evidence without guessing whether side effects occurred."""
    messages = {
        'unavailable': 'A ferramenta solicitada nao esta disponivel.',
        'disabled': 'A ferramenta esta desativada nas configuracoes.',
        'invalid_arguments': 'Os parametros precisam ser um objeto com campos nomeados.',
        'invalid_handler_contract': 'A assinatura da ferramenta nao aceita a chamada preparada; requer correcao da integracao.',
        'missing_result': 'A ferramenta retornou sem um resultado verificavel.',
        'handler_exception': 'A execucao foi interrompida por um erro interno.',
    }
    result = {'ok': False, 'error_code': code, 'error': messages[code],
              'execution_started': started, 'uncertain': started,
              'recovery': ('Consulte o estado do destino antes de repetir; pode haver efeitos parciais.'
                           if started else
                           'Consulte a disponibilidade e os parametros da ferramenta; corrija a causa antes de tentar novamente.')}
    if exception is not None:
        # Exception messages may contain credentials or request payloads.
        result['exception_type'] = type(exception).__name__
    return json.dumps(result, ensure_ascii=False)


def normalize_dispatch_result(result):
    if result is None or (isinstance(result, str) and not result.strip()):
        return dispatch_problem('missing_result', started=True)
    return result


def diagnostic_facts(result):
    """Small allowlisted facts for follow-ups, not arbitrary tool output or causes."""
    if not isinstance(result, dict):
        return {}
    facts = {}
    for key in ('error_code', 'exception_type'):
        value = result.get(key)
        if isinstance(value, str) and re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,63}', value):
            facts[key] = value
    for key in ('execution_started', 'uncertain', 'completed'):
        if type(result.get(key)) is bool:
            facts[key] = result[key]
    for key in ('status_code', 'exit_code'):
        if type(result.get(key)) is int:
            facts[key] = result[key]
    # Job wrappers have a known result slot; never walk arbitrary documents.
    nested = result.get('result')
    if any(isinstance(result.get(key), str) for key in ('job_id', 'operation_id')) and isinstance(nested, dict):
        child = diagnostic_facts({key: value for key, value in nested.items() if key != 'result'})
        if child:
            facts['operation_result'] = child
    return facts


def assess(result):
    state='unverified'
    if isinstance(result,dict):
        verification=result.get('verification')
        verification=verification if isinstance(verification,dict) else {}
        status=result.get('state')
        if result.get('uncertain') or result.get('stage')=='uncertain' or status in ('uncertain','partial'):state='uncertain'
        elif result.get('ok') is False or result.get('accepted') is False or result.get('cancelled') is True or result.get('error') or status in ('failed','error','rejected','cancelled') or verification.get('postcondition_verified') is False:state='failed'
        elif result.get('completed') is False or status in ('awaiting_confirmation','running','queued','pending','in_progress') or verification.get('layout_animating'):state='pending'
        elif 'postcondition_verified' in verification and verification['postcondition_verified'] is None:state='unverified'
        elif result.get('ok') is True:state='tool_reported'
    guidance={
        'failed':'Explique a falha observada, sem inventar a causa. Consulte o estado e corrija o alvo antes de tentar outra vez.',
        'uncertain':'Consulte o resultado pelo identificador ou inspecione o destino. Nao repita uma alteracao cujo resultado esta incerto.',
        'pending':'Acompanhe a operacao existente ou aguarde a confirmacao especifica. Nao reinicie nem anuncie conclusao.',
        'unverified':'Falta evidencia do resultado. Consulte o estado antes de afirmar que concluiu.',
        'tool_reported':'Relate somente o resultado confirmado pela ferramenta e respeite seu escopo. Isso nao comprova outros objetivos nem pixels.',
    }
    if isinstance(result,dict) and result.get('state')=='partial':
        guidance[state]='Resultado parcial: explique o que foi confirmado e o que ficou pendente ou falhou. Nao anuncie sucesso total nem repita etapas ja executadas sem verificar.'
    assessment={'state':state,'guidance':guidance[state]}
    if isinstance(result,dict):
        presentation=result.get('presentation')
        if isinstance(presentation,dict):
            if presentation.get('ok') is False:
                assessment['presentation']='failed'
                assessment['guidance']+=' A apresentacao falhou separadamente. Nao afirme que o resultado apareceu na tela; repare a exibicao sem repetir uma operacao ja confirmada.'
            elif presentation.get('ok') is True:
                assessment['presentation']='requested'
                assessment['guidance']+=' A exibicao foi solicitada, mas isso nao comprova visibilidade. Consulte o estado visual antes de afirmar onde o conteudo esta.'
        more=result.get('next_offset') is not None or result.get('has_more') is True
        incomplete=result.get('extraction_incomplete') is True or result.get('truncated') is True
        partial=result.get('partial') is True or result.get('complete') is False or more or incomplete
        if partial:
            assessment['coverage']='partial'
            assessment['guidance']+=' O resultado nao cobre todo o conteudo; nao afirme que leu ou verificou tudo.'
            if more:
                assessment['guidance']+=' Continue pela paginacao retornada se o pedido exigir o restante, sem reiniciar a primeira pagina.'
            if incomplete:
                assessment['guidance']+=' Ha conteudo truncado ou nao extraido; explique essa limitacao e escolha outra consulta ou leitura quando necessario.'
    return assessment
