"""Biblioteca semantica de receitas visuais locais, nunca codigo gerado pela IA."""
import copy
import math
import re
import unicodedata

# Cada conceito tem identidade propria; variantes reutilizam primitivas confiaveis.
GROUPS={
 'pensamento':('network','Ideia|Pergunta|Dúvida|Hipótese|Insight|Reflexão|Decisão|Alternativa'),
 'conhecimento':('slabs','Conhecimento|Conceito|Explicação|Evidência|Fonte|Aprendizado|Descoberta|Pesquisa'),
 'estudo':('columns','Estudo|Matemática|Ciência|História|Idioma|Leitura|Exercício|Revisão'),
 'tempo':('clock','Tempo|Agora|Passado|Futuro|Prazo|Duração|Pausa|Continuidade'),
 'planejamento':('route','Plano|Objetivo|Etapa|Prioridade|Progresso|Marco|Agenda|Tarefa'),
 'relacoes':('network','Relação|Conexão|Causa|Efeito|Dependência|Grupo|Contexto|Comunidade'),
 'comunicacao':('message','Mensagem|Conversa|E-mail|Contato|Resposta|Escuta|Voz|Notificação'),
 'clima':('weather','Atmosfera|Sol|Nuvem|Chuva|Vento|Neve|Tempestade|Temperatura'),
 'natureza':('orbit','Natureza|Terra|Lua|Estrela|Espaço|Horizonte|Energia|Equilíbrio'),
 'criatividade':('spark','Criatividade|Inspiração|Imaginação|Expressão|Arte|Design|Música|Narrativa'),
 'dados':('columns','Dados|Comparação|Diferença|Tendência|Distribuição|Ranking|Quantidade|Escala'),
 'sistema':('circuit','Sistema|Processador|Memória RAM|Rede|Disco|Aplicativo|Serviço|Diagnóstico'),
 'arquivos':('slabs','Arquivo|Documento|Imagem|Vídeo|Áudio|Pasta|Código|Anexo'),
 'seguranca':('shield','Segurança|Privacidade|Permissão|Identidade|Verificação|Proteção|Atenção|Limite'),
 'estado':('ring','Em espera|Em análise|Em execução|Concluído|Indisponível|Parcial|Atualizado|Desatualizado'),
 'bem-estar':('orbit','Bem-estar|Descanso|Foco|Ritmo|Movimento|Respiração|Rotina|Presença'),
 'organizacao':('grid','Organização|Categoria|Coleção|Filtro|Seleção|Resumo|Detalhe|Estrutura'),
 'localizacao':('route','Lugar|Destino|Origem|Rota|Distância|Direção|Mapa|Chegada'),
 'dialogo':('message','Olá|Obrigado|Confirmação|Convite|Sugestão|Esclarecimento|Discordância|Consideração'),
 'abstracao':('spark','Possibilidade|Incerteza|Complexidade|Simplicidade|Perspectiva|Intenção|Significado|Transformação'),
}
VARIANTS={'contorno':'Contorno','solido':'Sólido','orbital':'Orbital','camadas':'Camadas',
          'conectado':'Conectado','particulas':'Partículas','segmentado':'Segmentado','sinal':'Sinal'}
PALETTES={'neutro':('#c9d4e5','#8aa6bd'),'menta':('#77dfb9','#b9d8ec'),
 'violeta':('#c0a7ed','#75dfd4'),'dourado':('#efd28f','#a7cbe5'),
 'coral':('#edaa9d','#b8b1e7'),'gelo':('#96cfe8','#ded3a9'),'rosa':('#e8b1d7','#a3dad2'),'alerta':('#f1c078','#e7aaa2')}
ANIMATIONS=('montar','condensar','desenhar','conectar','expandir','revelar','orbitar','pulsar',
 'fluxo','chuva','neve','onda','varrer','segmentar','aproximar','dissolver',
 'recolher','sinalizar','alternar','respirar','estabilizar','acender','projetar','silencio')
LAYOUTS=('livre','radial','duas-colunas','comparacao','linha-do-tempo','sequencia','constelacao',
 'hierarquia','arco','campo','pilha','triade','resumo','pergunta','causa-efeito','ranking',
 'foco-contexto','quadrantes','vertical','horizontal')
ROLES=('titulo','frase','legenda','valor','pergunta')
PRIMITIVES=('orb','ring','arc','node','connection','plane','column','marker','grid','beam','trail','points')
SLOTS=('centro','acima','abaixo','esquerda','direita','orbita')
ANCHORS={f'{row}-{col}':{'x':(.1,.3,.5,.7,.9)[col],'y':(.16,.32,.5,.68,.86)[row]} for row in range(5) for col in range(5)}
ANCHORS.update({'alto-esquerda':{'x':.18,'y':.2},'alto-direita':{'x':.82,'y':.2},
 'baixo-esquerda':{'x':.18,'y':.8},'baixo-direita':{'x':.82,'y':.8},'centro':{'x':.5,'y':.5}})
PHRASES={
 'pergunta':('O que realmente importa aqui?','Vamos olhar por outro ângulo.','Qual dessas possibilidades faz mais sentido?',
    'Não existe uma única resposta.','Podemos explorar essa ideia.','O que muda entre essas opções?','Qual é a próxima pergunta?',
    'O contexto faz diferença.','Há espaço para outra interpretação.','Que resultado você procura?'),
 'reflexao':('Uma hipótese para considerar.','Uma perspectiva possível.','Primeiro, o significado.','O detalhe muda a leitura.',
    'Podemos separar as partes.','A conexão está aqui.','Essa ideia merece atenção.','Vale considerar o contraponto.',
    'Vamos distinguir fato e interpretação.','O importante é manter o contexto.'),
 'estrutura':('Ideia central','Ponto de partida','Próxima etapa','Em perspectiva','Para comparar','Uma alternativa',
    'Pergunta em aberto','Contexto relevante','Detalhe importante','Síntese'),
 'conversa':('Estou ouvindo.','Vamos pensar juntos.','Entendi a pergunta.','Podemos ir por partes.','Conte um pouco mais.',
    'Vou organizar a explicação.','Vamos retomar esse ponto.','Você pode escolher o caminho.','Isso depende do contexto.',
    'Podemos continuar daqui.'),
 'cuidado':('Uma ilustração, não uma medição.','Há incerteza neste ponto.','Ainda falta confirmação.','Não confunda estimativa com fato.',
    'O conteúdo precisa de uma fonte.','Sem dados suficientes para concluir.','Esse exemplo é hipotético.',
    'Uma possibilidade, não uma garantia.','O resultado precisa ser verificado.','Vamos preservar a legibilidade.'),
 'ritmo':('Um passo de cada vez.','Agora, o ponto principal.','Depois, os detalhes.','Um momento para observar.',
    'Vamos conectar as partes.','O foco está na relação.','Menos ruído, mais significado.','Podemos simplificar.',
    'Voltando à ideia central.','A explicação continua.'),
 'comparacao':('Primeira perspectiva','Segunda perspectiva','Pontos em comum','O que muda','O que permanece',
    'Diferença principal','Mesma pergunta, outra leitura','Critério de comparação','Escolhas possíveis','Conclusão provisória'),
 'criacao':('Uma ideia começa aqui.','Podemos combinar esses conceitos.','Forma a serviço do significado.',
    'Uma proposta visual.','Uma interpretação criativa.','O símbolo organiza a ideia.','Do conceito à composição.',
    'Uma nova combinação.','O texto conduz a leitura.','Espaço para imaginar.'),
}


def key(text):
    value=''.join(c for c in unicodedata.normalize('NFKD',text.lower()) if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]+','-',value).strip('-')


ICONS={}
for category,(family,words) in GROUPS.items():
    for index,label in enumerate(words.split('|')):
        for variant in VARIANTS:
            identifier=key(category)+'/'+key(label)+'/'+variant
            ICONS[identifier]={'id':identifier,'label':label,'category':category,'family':family,
                'variant':variant,'seed':index,'meaning':'Símbolo ilustrativo: '+label.lower()}
PHRASE_BANK={f'{category}/{index+1}':{'id':f'{category}/{index+1}','text':text,'category':category}
             for category,texts in PHRASES.items() for index,text in enumerate(texts)}


def overview():
    return {'icons':len(ICONS),'semantic_concepts':sum(len(words.split('|')) for _,words in GROUPS.values()),
        'variants':VARIANTS,'categories':list(GROUPS),'animations':list(ANIMATIONS),'layouts':list(LAYOUTS),
        'phrases':len(PHRASE_BANK),'anchors':list(ANCHORS),'palettes':list(PALETTES),'primitives':list(PRIMITIVES),
        'roles':list(ROLES),'limits':{'elements':12,'parts_per_symbol':6,'text_per_element':300,'total_text':1800},
        'recipe_note':'1280 receitas: 160 conceitos com 8 variantes locais. Não são 1280 modelos pesados distintos.'}


def search(kind='icons',query='',category='',offset=0,limit=16):
    if kind not in ('icons','phrases'):raise ValueError('Consulte icons ou phrases.')
    source=ICONS if kind=='icons' else PHRASE_BANK
    needle=key(query);records=[]
    for item in source.values():
        if category and item['category']!=category:continue
        if needle and needle not in key(' '.join(str(value) for value in item.values())):continue
        records.append(item)
    if isinstance(offset,bool) or not isinstance(offset,int) or offset<0:raise ValueError('Página inválida.')
    if isinstance(limit,bool) or not isinstance(limit,int) or not 1<=limit<=30:raise ValueError('Use entre 1 e 30 resultados.')
    end=min(len(records),offset+limit)
    return {'ok':True,'items':copy.deepcopy(records[offset:end]),'total':len(records),
        'next_offset':end if end<len(records) else None,'complete':end>=len(records)}


def number(value,minimum,maximum):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):raise ValueError('Coordenada ou escala inválida.')
    if not minimum<=value<=maximum:raise ValueError('Valor fora dos limites visuais.')
    return float(value)


def validate_element(item):
    if not isinstance(item,dict):raise ValueError('Cada elemento deve ser um objeto.')
    allowed={'id','icon','text','phrase','anchor','x','y','role','palette','animation','cue','scale','parts','pinned'}
    if set(item)-allowed:raise ValueError('Campo visual desconhecido. Código, URLs, CSS e shaders não são aceitos.')
    identifier=item.get('id','')
    if not isinstance(identifier,str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,48}',identifier):raise ValueError('Use um ID estável de até 48 caracteres.')
    result={'id':identifier,'text':item.get('text',''),'cue':item.get('cue',''),
        'role':item.get('role','frase'),'palette':item.get('palette','gelo'),
        'animation':item.get('animation','montar'),'anchor':item.get('anchor','alto-direita'),
        'scale':number(item.get('scale',1),.65,1.35),'pinned':item.get('pinned',False)}
    if not isinstance(result['pinned'],bool):raise ValueError('A fixação deve ser verdadeira ou falsa.')
    if result['role'] not in ROLES or result['palette'] not in PALETTES or result['animation'] not in ANIMATIONS:raise ValueError('Recurso visual fora da biblioteca.')
    if result['anchor'] not in ANCHORS:raise ValueError('Âncora não encontrada.')
    if not isinstance(result['text'],str) or len(result['text'])>300:raise ValueError('Use texto próprio de até 300 caracteres por elemento.')
    if not isinstance(result['cue'],str) or len(result['cue'])>80:raise ValueError('Use uma pista semântica curta da fala.')
    if item.get('phrase'):
        if item['phrase'] not in PHRASE_BANK:raise ValueError('Frase não encontrada na biblioteca.')
        if result['text']:raise ValueError('Escolha texto próprio ou uma frase da biblioteca.')
        result['text']=PHRASE_BANK[item['phrase']]['text']
    if 'x' in item or 'y' in item:
        if 'x' not in item or 'y' not in item:raise ValueError('Informe x e y juntos.')
        result.update(x=number(item['x'],0,1),y=number(item['y'],0,1))
    icon=item.get('icon','')
    if icon:
        if icon not in ICONS:raise ValueError('Ícone não encontrado. Consulte a biblioteca, não invente IDs.')
        result['recipe']=copy.deepcopy(ICONS[icon]);result['icon']=icon
    parts=item.get('parts',[])
    if not isinstance(parts,list) or len(parts)>6:raise ValueError('Use até seis primitivas por símbolo composto.')
    result['parts']=[]
    for part in parts:
        if not isinstance(part,dict) or set(part)-{'primitive','slot'}:raise ValueError('Primitiva inválida.')
        if part.get('primitive') not in PRIMITIVES or part.get('slot','centro') not in SLOTS:raise ValueError('Primitiva ou encaixe não encontrado.')
        result['parts'].append({'primitive':part['primitive'],'slot':part.get('slot','centro')})
    if not result['text'] and not icon and not parts:raise ValueError('Um elemento precisa de texto ou símbolo.')
    result['colors']=PALETTES[result['palette']]
    return result


def validate_request(request):
    if not isinstance(request,dict):raise ValueError('Composição inválida.')
    allowed={'action','elements','layout','id','text','icon','anchor','x','y','animation','palette','role','cue','scale','parts','pinned','duration'}
    if set(request)-allowed:raise ValueError('Pedido contém campos não autorizados.')
    action=request.get('action','compose')
    if action not in ('compose','update','focus','remove','pin','unpin','clear','inspect'):raise ValueError('Ação visual inválida.')
    if request.get('layout','livre') not in LAYOUTS:raise ValueError('Composição fora da gramática visual.')
    result={'action':action,'layout':request.get('layout','livre'),'duration':number(request.get('duration',45),5,300)}
    if action=='compose':
        items=request.get('elements',[])
        if not isinstance(items,list) or not 1<=len(items)<=12:raise ValueError('Use entre 1 e 12 elementos.')
        result['elements']=[validate_element(item) for item in items]
        ids=[item['id'] for item in result['elements']]
        if len(set(ids))!=len(ids):raise ValueError('Os IDs da composição devem ser únicos.')
        if sum(len(item['text']) for item in result['elements'])>1800:raise ValueError('Texto demais para uma composição legível.')
    elif action!='inspect' and action!='clear':
        identifier=request.get('id','')
        if not isinstance(identifier,str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,48}',identifier):raise ValueError('Informe o ID real do elemento.')
        result['id']=identifier
        if action=='update':result['patch']={k:v for k,v in request.items() if k in {'text','icon','anchor','x','y','animation','palette','role','cue','scale','parts','pinned'}}
    return result


def intersects(a,b,gap=10):
    return a['x']<b['x']+b['width']+gap and a['x']+a['width']+gap>b['x'] and a['y']<b['y']+b['height']+gap and a['y']+a['height']+gap>b['y']


def resolve_layout(items,width,height,blocked=(),layout='livre',measure=None):
    result=[];occupied=list(blocked)
    usable_width=max(1,width-24);top=90 if height>=400 else 54;bottom=20
    for index,item in enumerate(items):
        symbol=bool(item.get('recipe') or item.get('parts'))
        box_width=min(usable_width,230 if item['text'] else 108)
        lines=math.ceil(len(item['text'])/max(12,int(box_width/9)))
        text_height=measure(item,box_width) if measure else max(26,lines*23+10)
        box_height=(88 if symbol else 0)+text_height
        anchor=ANCHORS[item['anchor']]
        preferred={'x':item.get('x',anchor['x']),'y':item.get('y',anchor['y'])}
        if 'x' not in item and layout!='livre':
            if layout in ('vertical','hierarquia','ranking','pilha'):preferred={'x':.78,'y':.2+(index+.5)*.6/max(1,len(items))}
            elif layout in ('horizontal','sequencia','linha-do-tempo'):preferred={'x':(index+.5)/len(items),'y':.76}
            elif layout in ('comparacao','duas-colunas','causa-efeito'):preferred={'x':.2 if index%2==0 else .8,'y':.24+(index//2)*.22}
            elif layout in ('radial','arco','constelacao'):preferred={'x':.5+math.cos(index*math.tau/len(items))*.36,'y':.5+math.sin(index*math.tau/len(items))*.30}
            else:preferred={'x':.2+(index%3)*.3,'y':.22+(index//3)*.2}
        candidates=[preferred,*sorted(ANCHORS.values(),key=lambda pos:(pos['x']-preferred['x'])**2+(pos['y']-preferred['y'])**2)]
        placement=None
        for position in candidates:
            if box_height>height-top-bottom:break
            box={'x':round(max(12,min(width-box_width-12,position['x']*width-box_width/2))),
                 'y':round(max(top,min(height-box_height-bottom,position['y']*height-box_height/2))),
                 'width':box_width,'height':box_height}
            if not any(intersects(box,other) for other in occupied):placement=box;occupied.append(box);break
        result.append({**item,'visible':placement is not None,'bounds':placement,
                       'placement_note':None if placement else 'Sem espaço seguro para o texto completo; elemento secundário oculto.'})
    return result
