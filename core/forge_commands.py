"""Conversational controls; all remaining work stays in the current project."""
import re
from pathlib import Path
from core.protocol_commands import normalize


def command_for(text):
    value=normalize(text)
    value=re.sub(r'^(?:dief\s+)?jarvis\s+','',value)
    if value in ('o que esta fazendo','o que voce esta fazendo','qual o estado','como esta o projeto','status','o que esta fazendo agora',
                 'como esta indo','como esta ficando','como ta ficando','qual o progresso','em que etapa esta','quanto falta',
                 'como esta o processo','como ta o processo','deu certo','terminou','ja terminou','esta pronto','o que aconteceu','o que falta'):
        return {'action':'status'}
    # Conversation is not a work order, even when it mentions creation verbs.
    if re.match(r'^(?:nao\b|por que\b|porque\b|como\b|o que\b|voce\b|vc\b|sera que\b|se\b|e se\b|me explique\b|explique\b|me diga\b)',value):
        if value not in ('nao','nao faca','nao execute'):return None
    request=re.sub(r'^(?:por favor\s+)?(?:(?:pode|poderia|quero que voce|quero que vc|quero|gostaria de)\s+)?','',value)
    if value in ('nao','nao faca','nao execute'):
        return {'action':'approve','decision':False}
    # Conditions and multi-step requests need interpretation, not a single shortcut.
    if re.search(r'\b(?:se|caso|somente quando|so quando|apenas quando|depois que|apos confirmar)\b',request):
        return None
    if re.search(r'\b(?:e|depois|em seguida)\s+(?:crie|salve|exporte|cancele|desfaca|abra|feche|remova|envie)\b',request):
        return None
    # Let the conversational model resolve questions, corrections and host actions.
    # A creation verb does not necessarily refer to the open Forge project.
    if re.match(r'^(?:crie|criar|faca|fazer|de|dar|monte|gere)\s+(?:(?:um|uma|o|a)\s+)?(?:pergunta|comentario|piada|sugestao|conselho|opiniao|resumo|analise|backup|varredura|diagnostico)\b',request):
        return None
    if re.match(r'^(?:salve|salvar|guarde|guardar)\s+(?:(?:isso|isto)\s+)?(?:na memoria|nas lembrancas|essa preferencia|minha preferencia)\b',request):
        return None
    if re.search(r'\b(?:quer dizer|na verdade|pensando melhor|deixa pra la|deixe para la|nao faca|nao execute|nao crie|antes de (?:fazer|criar|executar)|o que (?:voce|vc) acha)\b',request):
        return None
    if re.match(r'^(?:crie|criar|faca|fazer|altere|alterar|mude|mudar|remova|remover|salve|salvar)\s+(?:isso|isto|aquilo)(?:\s+(?:por favor|pra mim|para mim))?$',request):
        return None
    if re.match(r'^(?:mude|troque|ajuste|aumente|diminua|use|altere)\s+(?:(?:a|o)\s+)?(?:sua voz|sua memoria|seu microfone|seu volume|volume|microfone|voz nativa)\b',request):
        return None
    if re.match(r'^(?:crie|criar|inicie|iniciar|comece)\s+(?:(?:um|uma)\s+)?(?:(?:outro|outra|novo|nova)\s+(?:projeto|criacao|simulador|cena)|(?:projeto|criacao|simulador|cena)\s+(?:novo|nova))\b',request):
        name=re.search(r'\b(?:chamado|chamada|com o nome|como)\s+(.+)',text,re.I)
        return {'action':'create','prompt':str(text).strip()[:8000],
                'name':name.group(1).strip(' .!?"')[:120] if name else 'Projeto FORJA'}
    if value in ('para','pare','parar'):return {'action':'stop_speech'}
    if re.match(r'(cancelar|cancele|cancela|pare|parar)\b.*\b(criacao|trabalho|execucao|projeto)\b',request):
        return {'action':'cancel'}
    if re.match(r'(desfaca|desfazer|volte|voltar)\b.*\b(versao|alteracao|anterior)\b',request):return {'action':'undo'}
    if value in ('refazer','refaca','proxima versao'):return {'action':'redo'}
    if re.match(r'(salve|salvar|guarde)\b.*\bbiblioteca\b',request):
        name=re.search(r'\bcomo\s+(.+)',text,re.I)
        return {'action':'save_library','name':name.group(1).strip(' .!?"')[:120] if name else ''}
    if re.match(r'(salve|salvar|exporte|exportar)\b',request):
        if 'area de trabalho' in value:
            return {'action':'export','destination':str(Path.home()/'Desktop')}
        path=re.search(r'([A-Za-z]:[\\/].+)',text)
        if path:return {'action':'export','destination':path.group(1).strip(' "')}
        return {'action':'save'}
    if value in ('continue','continuar','continue o projeto','continue o trabalho'):
        return {'action':'steer','prompt':'Continue o projeto atual a partir do estado real dos arquivos. Verifique a previa e os testes antes de concluir.'}
    if value in ('sim','confirmo','pode executar','pode fazer'):
        return {'action':'approve','decision':True}
    if re.match(r'^(?:crie|criar|faca|fazer|monte|montar|construa|construir|desenvolva|desenvolver|gere|gerar|implemente|implementar|programe|programar|desenhe|desenhar|ajuste|ajustar|altere|alterar|mude|mudar|troque|trocar|adicione|adicionar|inclua|incluir|remova|remover|retire|retirar|diminua|diminuir|aumente|aumentar|melhore|melhorar|corrija|corrigir|coloque|colocar|deixe|deixar|use|usar|aplique|aplicar|otimize|otimizar)\b',request):
        return {'action':'steer','prompt':str(text).strip()[:8000]}
    if re.match(r'^quero (?:um|uma)\s+(?:(?:novo|nova)\s+)?(?:site|app|aplicativo|jogo|simulador|planeta|cena|imagem|interface|painel|sistema|arquivo|programa|projeto|modelo|documento|video|animacao)\b',value):
        return {'action':'steer','prompt':str(text).strip()[:8000]}
    return None
