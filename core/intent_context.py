"""A small structured context for the existing conversational model and tools.

This selects a reasoning budget, never an execution or an authorization.
The primary model resolves meaning against real state and existing tool schemas.
"""
import re
from core.protocol_commands import normalize


def build(text, *, mode='base', application=None, plans=None, conversation=None):
    value=normalize(text)
    reference=bool(re.search(r'\b(isso|aquilo|aquele|aquela|anterior|antes|dai|ali|como estava)\b',value))
    correction=bool(re.search(r'\b(na verdade|pensando melhor|quis dizer|corrigindo|em vez|ao inves)\b',value))
    complex_task=bool(re.search(r'\b(investig\w*|diagnostic\w*|compare|analise|otimiz\w*|planej\w*|primeiro.+depois)\b',value))
    conversation=conversation if isinstance(conversation,dict) else {}
    followup=bool(re.search(r'\b(ja terminou|deu certo|nao apareceu|nao funcionou|por que|porque|continua|tente de novo|tenta de novo|e agora|e ai)\b',value))
    operations=conversation.get('recent_operations',[])
    unresolved=conversation.get('unresolved_operations',[])
    operations=operations if isinstance(operations,list) else []
    unresolved=unresolved if isinstance(unresolved,list) else []
    recovery=bool(followup and (unresolved or any(isinstance(item,dict) and
        (item.get('outcome') in ('failed','uncertain','pending','unverified') or item.get('presentation')=='failed')
        for item in operations)))
    tier='contextual' if correction else 'planned' if complex_task else 'contextual' if reference or recovery else 'direct'
    return {'schema':1,'mode':mode,'reasoning':tier,
            'has_reference':reference,'has_correction':correction,'needs_recovery_context':recovery,
            'application':application or {},'work':plans or {},
            'conversation_state':conversation or {},
            'decision_contract':{
                'understand':'Interprete o objetivo pelo pedido inteiro e pelo contexto, nao por palavras-chave isoladas. Os indicadores de reasoning sao sugestoes locais, nao uma classificacao obrigatoria.',
                'ground':'Use selecoes e operacoes recentes para resolver referencias. Uma selecao de outro assunto nao e alvo automatico. Se faltar alvo, destino ou efeito essencial, pergunte somente o que falta; nao exija uma frase exata.',
                'recover':'Se falhar, leia o erro retornado, consulte o estado atual e mude a estrategia ou parametros com base na causa observada. Nao repita a mesma tentativa cegamente. Operacao pendente ou incerta exige consultar seu identificador antes de repetir efeitos.',
                'communicate':'Converse normalmente quando nao houver pedido de acao. Explique resultado, limite ou proximo passo em linguagem natural, sem narrar cada procedimento. Sugestao nao e autorizacao para executa-la. Diga o que aconteceu com a tarefa em vez de ler IDs, codigos ou estados internos em voz alta; detalhes tecnicos ficam disponiveis se forem pedidos.',
                'followup':'Uma pergunta sobre erro ou andamento nao e ordem de reiniciar. Relacione-a ao assunto atual; se houver mais de uma tarefa plausivel, pergunte qual. Falha de exibicao nao implica falha da operacao; confira cada resultado separadamente.'},
            'policy':{
                'direct':'Responda ou use a ferramenta adequada sem criar plano para uma tarefa trivial.',
                'contextual':'Resolva alvo e intencao com o pedido atual, contexto observado e conversa. Se houver dois alvos plausiveis, faca uma pergunta curta. Correcao atual prevalece.',
                'planned':'Identifique objetivo e dependencias. Registre etapas se houver varias acoes; consulte estado, execute, verifique e registre bloqueio. Nao repita efeitos incertos.'}[tier],
            'contract':'Contexto nao e ordem. Escolha conversar, perguntar ou executar. Use esquemas das ferramentas para parametros; nunca invente IDs. Estado observado prevalece sobre lembranca. No Espectro, pedidos sobre sua presenca usam spectro_control. Ao falar de desfazer, confira can_undo_presence; reset nao significa desfazer. Nao anuncie sucesso pela intencao ou pela animacao. Para lembrancas, consulte memory_control; se a busca literal nao encontrar, use qdrant_memory quando disponivel e confira fonte, data e relevancia. Na Forja, programacao usa forge_protocol; conversa, opiniao e esclarecimento permanecem conversa. Para investigacao dificil, use o plano e as ferramentas existentes, sem trocar fornecedor por conta propria.'}
