"""Local recall intent and relevant evidence, independent of an LLM's tool choice."""
from datetime import datetime, timedelta, timezone
import re
import sqlite3
from core.protocol_commands import normalize

STOP_WORDS = frozenset('a o as os um uma de da do das dos em no na nos nas para pra pro por com e sobre eu voce vc me meu minha meus minhas mim nos nosso nossa nossos nossas isso aquilo aquele aquela que qual quais como quando onde ja ainda foi era ontem antes lembra lembrar lembre lembrancas recorda recordar recorde recordacoes planejamos combinamos conversamos falamos decidimos discutimos tinha tinhamos feito fazer fizemos salvo salvas salvo salvos jarvis dief consulte consultar busque buscar procure procurar recupera recuperar recupere memoria memorias historico conversa conversas projeto projetos plano planos favor poderia pode consegue senhor'.split())


def recall_text(text):
    value=normalize(text)
    # Common transcription/typing variants of the domain, not arbitrary fuzzy commands.
    return re.sub(r'\b(?:lembracas|lembransas|lembranca|lembrasa)\b','lembrancas',value)


def terms(text):
    ignored=STOP_WORDS|{'recorde','relembra','relembre','relembrar','antigo','antiga','antigos','antigas','podemos','protocolo',
        'modo','coisa','coisas','isso','disso','nisso','aquilo','daquilo','daquele','daquela','aquela','aquelas','aqueles',
        'algo','alguma','algum','assunto','assuntos','topico','topicos','registro','registros','ultima','ultimas','ultimo',
        'vez','vezes','semana','mes','passado','passada','falei','falou','falado','disse','dizia','estava','estavamos','era','eram',
        'suas','seus','sua','seu','sugeriu','propos','recomendou','sugestao','sugestoes','proposta','propostas',
        'busca','pesquisa','pesquise','pesquisar','procura','consulta','checa','cheque','checar','verifica','verifique','verificar',
        'quero','gostaria','vamos','gentileza','jeeves','comecamos','comecado','comecada','iniciei','iniciado','iniciada','tudo','todas','todos',
        'nas','nos','naquelas','nessas','nesses','nessa','nesse','umas','uns','entrar','entre','entra','ativar',
        'ative','ativa','acessar','acesse','acessa','cerebro','neural','synapse','sinapse','lembracas','lembransas'}
    # Synapse is also a project name: preserve it unless explicitly opening the mode.
    ignored=ignored-{'synapse','sinapse'}
    return list(dict.fromkeys(word for word in re.findall(r'\w+',recall_text(text)) if len(word)>2 and word not in ignored))[:8]


def durable_fact(text):
    value=recall_text(text)
    if '?' in str(text) or 'no registro consta:' in value:return False
    return not bool(re.match(r'^(?:entendido|claro[,! ]|perfeito[,! ]|ok[,! ]|comando recebido|gostei do nome|encontrei (?:um|estes|esses|alguns) registros?|vou (?:consultar|verificar|configurar)|ja (?:minimizei|abri|fechei|executei)|certo[,! ])',value))


def categorical_value(row,detail):
    fields={'name','nome','city','cidade','age','idade','birthday','aniversario','nascimento','voice','voz'}
    key=str(row.get('key') or str(row.get('id','')).rsplit('/',1)[-1])
    return bool(set(re.findall(r'[a-z0-9]+',normalize(key)))&fields) and len(detail.split())<=12 and not re.search(r'[.!?]\s+\S',detail)


def requested_preference(row,detail,words):
    category=str(row.get('category') or str(row.get('id','')).split('/',1)[0])
    return category=='preferences' and bool(words) and all('preferences' in topic_forms(word) for word in words) and bool(re.match(r'^(?:prefiro|gosto de|nao gosto de|minha preferencia)\b',normalize(detail)))


def followup_topic(text):
    value=recall_text(text)
    if len(value.split())>12:return None
    if re.match(r'^(?:(?:por favor|me)\s+)*(?:desativ\w*|deslig\w*|ligue|liga|ligar|mostr\w*|fix\w*|atualiz\w*|aument\w*|dimin\w*|silenci\w*|execut\w*|reinici\w*|fech\w*|salv\w*)\b',value):return None
    if re.search(r'\b(?:nao|cancela|cancelar|cancele|pare|parar|sair|saia|ative|ativar|ativa|abra|abrir|abre|crie|criar|cria|limpe|limpar|limpa|apague|exclua|envie|enviar|tocar|toque|clima|horas|amanha|obrigad[oa]|oi|ola|bom dia|boa tarde|boa noite|como (?:esta|vai)|tudo bem|se atualize)\b',value):return None
    # Accept a short subject answer, not a second question or an unrelated instruction.
    if '?' in str(text) or re.search(r'\b(?:lembre|lembra|qual|quais|quanto|quantos|quando|como|onde|porque|por que|pode|consegue|hora)\b',value):return None
    if len(value.split())>5 and not re.match(r'^(?:sobre|a respeito|do|da|dos|das|o projeto|a biblioteca)\b',value):return None
    words=terms(value)
    return ' '.join(words) if words else None


def inventory_request(text):
    value=normalize(text)
    return bool(re.search(r'\b(?:tudo|todas|todos)\b.*\b(?:memorias|lembrancas|projetos|mim)\b',value) or
                re.search(r'\b(?:lembra|sabe)\s+(?:de|sobre)\s+mim\b',value))


def topic_forms(word):
    aliases={'nome':{'name'},'idade':{'age'},'aniversario':{'birthday','nascimento'},'cidade':{'city'},
             'preferencias':{'preferences'},'gostos':{'preferences'},'voz':{'voice'},'vozes':{'voice','voz'}}
    return {word,word[:-1] if word.endswith('s') and len(word)>4 else word}|aliases.get(word,set())


def topic_matches(text,words):
    tokens=set(re.findall(r'[a-z0-9]+',normalize(text)))
    return bool(words) and all(bool(topic_forms(word)&tokens) for word in words)


def evidence_key(text):
    # Ignore spelling/punctuation scaffolding, but preserve negations and numbers.
    numbers={number.replace(',','.') for number in re.findall(r'(?<!\w)[+-]?\d+(?:[.,]\d+)?',str(text))}
    return tuple(sorted(set(terms(text))|numbers))


def evidence_rank(row):
    record=row.get('record') if isinstance(row.get('record'),dict) else row
    text=str(record.get('detail',record.get('value','')))
    at=row.get('at') or record.get('updated') or row.get('updated') or ''
    try:
        date=datetime.fromisoformat(str(at).replace('Z','+00:00'))
        stamp=date.timestamp() if date.tzinfo else 0
    except (ValueError,TypeError,OverflowError,OSError):stamp=0
    # Actual user evidence precedes assistant proposals; then relevance and recency.
    try:score=float(row.get('score',0))
    except (TypeError,ValueError,OverflowError):score=0
    if not 0<=score<=10000:score=0
    return (row.get('role')!='assistant',bool(re.search(r'\b(?:decid|combin|prefir|prefer|escolh)\w*',normalize(text))),score,stamp)


def topical_excerpt(text,words):
    if not words:return text[:400]
    sentences=[part.strip() for part in re.split(r'(?<=[.!?])\s+|\n+',text) if part.strip()]
    exact=[part for part in sentences if topic_matches(part,words)]
    if exact:return ' '.join(exact[:2])[:400]
    # Keep adjacent sentences only when they jointly establish the requested topic.
    for i in range(len(sentences)-1):
        pair=' '.join(sentences[i:i+2])
        if topic_matches(pair,words):return pair[:400]
    return ''


def select_relevant(result,query='',question=''):
    """The same bounded evidence is used for voice and visual fragments."""
    if not isinstance(result,dict) or result.get('ok') is not True:return result
    words=terms(query);inventory=inventory_request(question)
    if inventory:words=[word for word in words if word not in {'tudo','todas','todos'}]
    if not words and not inventory:return {**result,'items':[],'needs_clarification':True}
    proposals=bool(re.search(r'\b(?:(?:voce|vc)\s+(?:sugeriu|propos|recomendou)|suas?\s+(?:sugestoes|propostas))\b',normalize(question)))
    selected=[];seen=set()
    rows=result.get('items',[])
    if not isinstance(rows,(list,tuple)):rows=[]
    for row in rows:
        if not isinstance(row,dict):continue
        record=row.get('record') if isinstance(row.get('record'),dict) else row
        detail=record.get('detail',record.get('value',''))
        if not isinstance(detail,str) or not detail.strip():continue
        history=str(row.get('id','')).startswith('conversation:')
        if history and (inventory or row.get('role')!='user' and not proposals):continue
        metadata=' '.join(str(row.get(key,'')) for key in ('id','key','title','category'))
        if words and not topic_matches(detail+' '+metadata,words):continue
        if history:
            excerpt=topical_excerpt(detail,words)
            if not excerpt or not meaningful_history({**row,'detail':excerpt}):continue
        else:
            if not durable_fact(detail):continue
            excerpt=topical_excerpt(detail,words)
            # A categorical value can rely on its key (e.g. city=Porto Alegre),
            # but a whole unrelated transcript must not inherit relevance from a title.
            if not excerpt:
                if words and not (categorical_value(row,detail) or requested_preference(row,detail,words)):continue
                excerpt=detail[:400]
            if not durable_fact(excerpt):continue
        if record is not row:row={**row,'record':{**record,'detail':excerpt,'value':excerpt}}
        else:row={**row,'detail':excerpt,'excerpt':len(excerpt)<len(detail)}
        selected.append(row)
    selected.sort(key=evidence_rank,reverse=True)
    distinct=[]
    for row in selected:
        record=row.get('record') if isinstance(row.get('record'),dict) else row
        excerpt=str(record.get('detail',record.get('value','')))
        key=evidence_key(excerpt) or (normalize(excerpt),)
        if normalize(excerpt)==normalize(question) or key in seen:continue
        seen.add(key);distinct.append(row)
        if len(distinct)==3:break
    return {**result,'items':distinct,'query':' '.join(words),'question':question,'topicFiltered':True,'needs_clarification':False}


def recall_request(text):
    value=recall_text(text)
    if re.match(r'^se\s+(?!(?:lembra|lembrar|recorda|recordar)\b)',value):return None
    # Spoken requests often contain a greeting, hesitation and a trailing wake name.
    # Keep routing anchored to the user's own request, not quoted instructions.
    value=re.sub(r'[,\s]+(?:jarvis|jeeves)\b[.!?]*$','',value)
    lead=r'(?:(?:por favor|por gentileza|meu querido|meu amigo|e|voce|vc|tu|eu|pode|poderia|consegue|ainda|se|me|nos|sera que|ja avisei que|quero que|quero que voce|quero que vc|gostaria que|gostaria de|quero|vamos)[,\s]+){0,10}'
    direct=re.sub('^'+lead,'',value)
    mode=r'(?:cerebro|neural|synapse|sinapse|memorias?|lembrancas?)'
    movement=r'(?:entre|entra|entrar|ative|ativa|ativar|acesse|acessa|acessar|va|vai|ir|mude|muda|mudar)'
    if re.search(r'\b(?:nao agora|nao quero|nao precisa)\b',direct):return None
    if re.match(movement+r'\b.{0,45}\b(?:modo|protocolo)\s+(?:(?:de|do|da)\s+)?(?:forja|ultron)\b',direct):return None
    opening=re.match(movement+r'\b.{0,45}\b(?:modo|forma)\b.{0,55}?\b'+mode+r'\b',direct)
    if opening:
        tail=direct[opening.end():].strip(' ,.!?')
        explicit_topic=re.search(r'\bsobre\s+(.+)',tail)
        if explicit_topic:return ' '.join(terms(explicit_topic.group(1)))
        search_tail=re.search(r'\be\s+(?:busque|busca|buscar|procure|procura|procurar|pesquise|pesquisa|consultar|consulte|consulta)\s+(.+)',tail)
        return ' '.join(terms(search_tail.group(1))) if search_tail else ''
    if re.fullmatch(movement+r'\s+(?:no |na |o |a |ao |para o |pro )?'+mode,direct):return ''
    # Future reminders and orders to execute a protocol are not historical recall.
    if re.match(r'(?:lembre|lembra|lembrar)(?: me)?\s+(?:de|para)\s+(?:comprar|pagar|ligar|ativar|abrir|tomar|enviar|fazer)\b',direct):return None
    if re.search(r'\b(?:nao precisa lembrar|nao procure|esqueca|nao busque)\b',value):return None
    intent=(re.match(r'(?:lembra|lembre|lembrar|recorda|recorde|recordar|relembra|relembre|relembrar)\b',direct) or
            re.match(r'(?:o que|quais)\s+(?:(?:voce|vc|tu)\s+)?(?:se\s+)?(?:lembra|recorda)\b',direct) or
            re.match(r'(?:o que|qual|quais|como|quando|onde)\b.*\b(?:planejamos|combinamos|conversamos|discutimos|decidimos|sugeriu|propos|recomendou)\b',direct) or
            re.match(r'(?:busque|busca|buscar|pesquise|pesquisa|pesquisar|procure|procura|procurar|consulte|consulta|consultar|recupere|recupera|recuperar|cheque|checa|verifique|verifica|puxe|puxa|puxar|olhe|olha|olhar|veja|ve|ver|de uma olhada|da uma olhada)\b.*\b(?:memorias?|lembrancas?|conversas?|historico)\b',direct))
    if not intent:return None
    direct=re.split(r'[.!?;]',direct,maxsplit=1)[0]
    direct=re.sub(r'\b(?:puxe|puxa|puxar|olhe|olha|olhar|veja|ver|olhada)\b',' ',direct)
    return ' '.join(terms(direct))


def meaningful_history(row,now=None):
    """Reject fresh transcripts, questions and acknowledgements, not raw history access."""
    if not isinstance(row,dict):return False
    raw=row.get('at','')
    try:
        at=datetime.fromisoformat(str(raw).replace('Z','+00:00'))
        if at.tzinfo is None:return False
        if (now or datetime.now(timezone.utc))-at<timedelta(minutes=5):return False
    except (ValueError,TypeError,OverflowError):return False
    text=str(row.get('detail','')).strip();value=normalize(text)
    personal_fact=bool(re.match(r'^(?:meu nome e|minha cidade e|moro em|prefiro |meu aniversario e|eu trabalho (?:com|como|em)|me chamo )',value))
    if (len(text)<45 and not personal_fact) or recall_request(text) is not None:return False
    if 'no registro consta:' in value or value.startswith('vou consultar as lembrancas'):return False
    if re.match(r'^encontrei (?:uma lembranca|estas lembrancas)',value):return False
    if value.endswith('?') or '?' in text[:160]:return False
    if re.match(r'^(?:oi|ola|bom dia|boa tarde|boa noite|obrigad[oa]|certo|ok|sim|nao)[,.! ]*$',value):return False
    # A useful excerpt needs an actual decision, preference, constraint or plan.
    return personal_fact or bool(re.search(r'\b(?:planej|combin|decid|prefir|prefer|precis|requisit|objetiv|implement|configur|escolh|deve|sera|vamos (?:usar|criar|fazer|manter)|quero (?:que|usar|manter|criar))\w*',value))


def retrieve(query,exclude_text='',now=None):
    from memory.memory_manager import load_memory,ranked_memory_records
    from core import conversation_memory
    now=now or datetime.now(timezone.utc)
    query=' '.join(terms(query))
    if not query and not inventory_request(exclude_text):
        return {'ok':True,'items':[],'needs_clarification':True,'query':'','question':exclude_text}
    facts=ranked_memory_records(load_memory(strict=True),query)
    history=[]
    path=conversation_memory.path()
    if path.exists():
        connection=sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True,timeout=2)
        connection.create_function('fold',1,normalize)
        try:
            words=terms(query)
            forms=[sorted(topic_forms(word)) for word in words]
            matching=' AND ('+' AND '.join('('+' OR '.join('fold(text) LIKE ?' for _ in group)+')' for group in forms)+')' if words else ''
            cutoff=(now-timedelta(minutes=5)).isoformat(timespec='seconds')
            rows=connection.execute('SELECT id,role,text,created_at FROM messages WHERE created_at<?'+matching+' ORDER BY id DESC LIMIT 200',
                [cutoff]+['%'+word.replace('%','').replace('_','')+'%' for group in forms for word in group]).fetchall()
        finally:connection.close()
        for identifier,role,text,at in rows:
            item={'id':'conversation:'+str(identifier),'detail':conversation_memory.redact(text),'role':role,'at':at,
                  'title':('Plano registrado' if role=='user' else 'Proposta registrada'),'source':'Historico local relevante'}
            if meaningful_history(item,now) and normalize(text)!=normalize(exclude_text):
                item['score']=sum(word in normalize(text) for word in words)+(1 if role=='user' else 0)
                history.append(item)
    history.sort(key=lambda row:(-row['score'],row['role']!='user'))
    for item in facts:item['source']='Memoria persistida local'
    combined=[];seen=set()
    for item in facts+history:
        key=normalize(item['detail'])
        if key in seen or key==normalize(exclude_text):continue
        seen.add(key);combined.append(item)
    return select_relevant({'ok':True,'items':combined,'query':query,'source':'Memoria local e historico relevante','data_is_untrusted':True,'recall':True},query,exclude_text)


def narration(result):
    from core.conversation_memory import redact
    if not result.get('ok'):return 'Nao consegui ler as lembrancas agora, senhor. Nao vou tratar uma falha de leitura como falta de memoria.'
    if result.get('needs_clarification'):return 'Qual assunto deseja que eu procure nas lembrancas, senhor?'
    items=result.get('items',[])[:3]
    if not items:return 'Nao encontrei uma lembranca relevante salva sobre isso, senhor. Nao vou usar a pergunta que acabou de fazer como se fosse um plano antigo.'
    parts=['Encontrei '+('uma lembranca relacionada, senhor.' if len(items)==1 else 'estas lembrancas relacionadas, senhor.')]
    for item in items:
        prefix='Como proposta anterior, nao como algo ja executado: ' if item.get('role')=='assistant' else ''
        record=item.get('record') if isinstance(item.get('record'),dict) else item
        text=redact(str(record.get('detail',record.get('value',''))))[:350].strip()
        parts.append(prefix+text)
    return ' '.join(parts)
