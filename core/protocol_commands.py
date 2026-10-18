"""Host routing of explicit protocol requests, never instructions from tool data."""
import re
import unicodedata


def normalize(text):
    value=''.join(c for c in unicodedata.normalize('NFD',str(text)) if not unicodedata.combining(c))
    value=re.sub(r'^\s*(?:dief\s+)?jarvis\b[\s,:!]*','',value.casefold())
    return ' '.join(value.strip().rstrip('.!?').split())


def protocol_request(text):
    value=normalize(text)
    prefix=r'(?:(?:por favor|por gentileza)[, ]+)?(?:(?:pode|poderia|quero que voce|quero que vc|quero|gostaria de)\s+)?'
    suffix=r'(?:[, ]+(?:por favor|por gentileza|senhor|agora|pra mim|para mim))?'
    for protocol in ('forja','ultron'):
        target=protocol if protocol=='forja' else r'(?:ultron|ulktron)'
        noun=r'(?:(?:o|a|no|na|do|da|esse|este|aquele)\s+)?(?:(?:modo|protocolo)\s+(?:(?:do|da|de)\s+)?)?'
        if re.fullmatch(prefix+r'(?:ativar|ative|ativa|iniciar|inicie|inicia|entrar|entre|entra|abra|abrir|abre|ligar|ligue|liga|acionar|acione|aciona)\s+'+noun+target+suffix,value):
            return protocol,'enter'
        if re.fullmatch(prefix+r'(?:desativar|desative|desativa|sair|saia|sai|fechar|feche|fecha|desligar|desligue|desliga|encerrar|encerre|encerra)\s+'+noun+target+suffix,value):
            return protocol,'exit'
    if value in ('voltar ao jarvis','volte ao jarvis','voltar para o jarvis'):
        return 'forja','exit'
    return None


YES = frozenset({'sim','sim senhor','sim, senhor','sim jarvis','confirmo','pode ativar','pode ligar','pode entrar','pode fazer'})


def protocol_clarification(text):
    """Only a bounded first-person desire/short reference may invite a question."""
    value=normalize(text)
    if protocol_request(text):return None
    for name in ('ultron','forja'):
        target=r'(?:ultron|ulktron)' if name=='ultron' else name
        if re.fullmatch(r'(?:(?:vamos|vamos para|vamos pro|vamos pra|quero|quero usar|quero entrar|gostaria de usar)\s+)?(?:(?:o|a|no|na|pro|pra)\s+)?(?:(?:modo|protocolo)\s+(?:(?:do|da|de)\s+)?)?'+target,value):
            return name,'enter'
    return None
