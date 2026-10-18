"""Shared interpretation of tool evidence, never inferred from animation."""


def assess(result):
    state='unverified'
    if isinstance(result,dict):
        verification=result.get('verification')
        verification=verification if isinstance(verification,dict) else {}
        status=result.get('state')
        if result.get('uncertain') or result.get('stage')=='uncertain' or status in ('uncertain','partial'):state='uncertain'
        elif result.get('ok') is False or result.get('accepted') is False or result.get('error') or status in ('failed','error','rejected','cancelled') or verification.get('postcondition_verified') is False:state='failed'
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
    return {'state':state,'guidance':guidance[state]}
