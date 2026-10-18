"""Direct reversible desktop-presence requests; other speech stays conversational."""
import re
from core.protocol_commands import normalize


def request(text,active=False):
    value=normalize(text)
    prefix=r'(?:(?:por favor|pode|poderia|quero)\s+)?'
    if re.fullmatch(prefix+r'(?:ative|ativa|ativar|entre|entrar|liga|ligue|abrir|abra)\s+(?:o |no )?(?:modo )?espectro',value):return ('enter',{})
    if re.fullmatch(prefix+r'(?:desative|desativa|desativar|saia|sair|feche|fechar|desligue)\s+(?:o |do )?(?:modo )?espectro',value) or active and value in ('volte para a base','volta pra base','voltar para a base','volta para a base','volte para o jarvis','volta pra base do jarvis'):
        return ('exit',{})
    value=re.sub(r'^(?:(?:por favor|pode|poderia|quero que voce|quero que vc|quero)\s+)+','',value)
    value=re.sub(r'[, ]+por favor$','',value)
    if value in ('pare de observar minha tela','pare de observar a tela','pare de observar','ative a privacidade','ativar privacidade','nao observe minha tela','nao acompanhe minha tela','pare de observar o computador'):return 'privacy',{}
    if value in ('volte a observar','retome a observacao','continue observando'):return 'resume_observation',{}
    if value in ('o que voce esta vendo','o que esta vendo','o que voce consegue ver','analise esta janela','analise essa janela'):return 'context',{}
    if not active:return None
    value=re.sub(r'^(?:(?:por favor|pode|poderia|quero que voce|quero que vc|quero)\s+)+','',value)
    value=re.sub(r'[, ]+por favor$','',value)
    for before,after in (('ficar','fique'),('diminuir','diminua'),('aumentar','aumente'),('mover','mova'),('se mover','se mova'),('acompanhar','acompanhe'),('observar','observe'),('monitorar','monitore')):
        value=re.sub(r'^'+before+r'\b',after,value)
    if value=='nao me interrompa':return 'quiet',{'enabled':True}
    if value in ('nao observe minha tela','nao acompanhe minha tela','pare de observar o computador'):return 'privacy',{}
    if re.match(r'^(?:nao|como|porque|por que|se(?!\s+mova\b)|e se|voce consegue)\b',value):return None
    if value in ('diminua','diminui','reduza','diminua seu tamanho','diminua o tamanho','diminua o seu tamanho','diminua o holograma','diminui o tamanho','reduza o tamanho','fica um pouco menor','fique um pouco menor','fique mais pequeno'):
        return 'scale',{'factor':.8}
    if value in ('aumente','aumenta','aumente seu tamanho','aumenta o tamanho','aumente o tamanho'):
        return 'scale',{'factor':1.2}
    if re.fullmatch(r'(?:fique|fica|deixe|deixa|torne|torna)(?: voce| o holograma| o nucleo| o espectro)? (?:um pouco )?mais transparente',value):return 'opacity',{'delta':-.15}
    if value in ('voce esta atrapalhando a tela','esta atrapalhando a tela','sai da frente','fique mais discreto','fica mais discreto'):
        return 'minimal',{}
    if value in ('limpe a tela','limpa a tela','limpe as marcacoes','tire as marcacoes','remova os destaques'):return 'clear',{}
    if value in ('pare de observar minha tela','pare de observar a tela','pare de observar','ative a privacidade','ativar privacidade','modo privado'):
        return 'privacy',{}
    if value in ('acompanhe este aplicativo','acompanha esse aplicativo','observe este aplicativo','observe essa janela','pode acompanhar esse aplicativo','acompanhe esta janela'):
        return 'observe_current',{}
    if value in ('volte a observar','retome a observacao','continue observando'):return 'resume_observation',{}
    if value in ('o que voce esta vendo','o que esta vendo','o que voce consegue ver','analise esta janela','analise essa janela'):return 'context',{}
    if value in ('fique em silencio','presenca silenciosa','nao me interrompa'):return 'quiet',{'enabled':True}
    if value in ('dar sugestoes','pode dar sugestoes','volte a dar sugestoes','ative as sugestoes'):return 'quiet',{'enabled':False}
    numeric=re.fullmatch(r'(?:deixe|deixa|coloque|coloca|defina)(?: o holograma| o nucleo| o espectro)?(?: com| em)?\s+(\d{1,3})\s*(?:%|por cento)\s+de\s+(opacidade|transparencia|tamanho)',value)
    if numeric:
        amount=int(numeric[1])/100
        if numeric[2]=='tamanho':return 'scale',{'size':round(320*amount)}
        return 'opacity',{'value':1-amount if numeric[2]=='transparencia' else amount}
    movement=re.fullmatch(r'(?:va|vai|vem|fique|fica|mova|mova-se|se mova)(?: para| pra| pro| ao)?(?: o| a| no| na| do| da)?\s+(lado esquerdo|lado direito|canto esquerdo|canto direito|esquerda|direita|outro canto|centro|cima|baixo|outro monitor)',value)
    if movement:
        anchor={'lado esquerdo':'left','canto esquerdo':'left','esquerda':'left','lado direito':'right','canto direito':'right','direita':'right','outro canto':'opposite','centro':'center','cima':'top','baixo':'bottom','outro monitor':'next_monitor'}[movement[1]]
        return 'position',{'anchor':anchor}
    if value in ('menor','um pouco menor'):return 'scale',{'factor':.8}
    if value in ('maior','um pouco maior'):return 'scale',{'factor':1.2}
    if value=='mais transparente':return 'opacity',{'delta':-.12}
    if value in ('menos transparente','mais visivel'):return 'opacity',{'delta':.12}
    if value in ('aumente a transparencia','aumente transparencia','reduza a opacidade','fique transparente','fica transparente'):return 'opacity',{'delta':-.15}
    if value in ('diminua a transparencia','reduza a transparencia','aumente a opacidade'):return 'opacity',{'delta':.15}
    if value in ('observe minha tela','acompanhe meu trabalho','acompanhe o que estou fazendo','acompanhe esse aplicativo','observe esse aplicativo','monitore este aplicativo'):
        return 'observe_current',{}
    relative=re.fullmatch(r'(?:um pouco|mais) (?:para|pra) (?:a |o )?(esquerda|direita|cima|baixo)',value)
    if relative:return 'position',{'dx':-60 if relative[1]=='esquerda' else 60 if relative[1]=='direita' else 0,'dy':-60 if relative[1]=='cima' else 60 if relative[1]=='baixo' else 0}
    for pattern,operation,settings in (
        (r'(?:fica|fique|deixe|torne|reduza|diminua)(?: o holograma)? (?:um pouco |mais )?(?:menor|pequeno|discreto)', 'scale',{'factor':.8}),
        (r'(?:fica|fique|deixe)(?: o holograma)? (?:um pouco |mais )?maior','scale',{'factor':1.2}),
        (r'(?:fica|fique|deixe)(?: o holograma)? mais transparente','opacity',{'delta':-.12}),
        (r'(?:fica|fique|deixe)(?: o holograma)? (?:mais visivel|menos transparente)','opacity',{'delta':.12}),
        (r'(?:volte|volta|restaure)(?: ao| para o)? tamanho normal','reset',{}),
        (r'(?:desapareca um pouco|presenca minima|fique discreto)','minimal',{}),
    ):
        if re.fullmatch(prefix+pattern,value):return operation,settings
    match=re.fullmatch(prefix+r'(?:va|vai|fique|fica|mova|mova-se)(?: para| pra)? (?:a |o |na |no )?(esquerda|direita|outro canto|centro)',value)
    if match:return 'position',{'anchor':{'esquerda':'left','direita':'right','outro canto':'opposite','centro':'center'}[match[1]]}
    return None
