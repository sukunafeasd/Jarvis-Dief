"""Structured operations for the desktop presence, shared with direct voice routing."""
import json


def spectro_control(parameters,player=None):
    if player is None:return json.dumps({'ok':False,'error':'Interface indisponivel.'})
    operation=parameters.get('operation','inspect')
    if operation=='inspect':
        result=player.control_interface('inspect')
        return json.dumps({'ok':True,'spectro':result.get('screen',{}).get('spectro',{'active':False}),
                           'source':'application_state'} if result.get('ok') else result,ensure_ascii=False)
    context=None
    if operation in ('observe_current','resume_observation'):
        from core.spectro_commands import request
        context=getattr(player,'ultron_user_context',lambda:{})()
        parsed=request(context.get('text',''),True)
        if not parsed or parsed[0]!=operation:
            return json.dumps({'ok':False,'error':'Observacao requer pedido atual explicito, por exemplo acompanhe este aplicativo. Nenhuma observacao foi habilitada.'})
    settings={key:value for key,value in parameters.items() if key!='operation'}
    if context is not None:
        return json.dumps(player.control_interface('spectro',operation,json.dumps(settings),user_context=context),ensure_ascii=False)
    return json.dumps(player.control_interface('spectro',operation,json.dumps(settings)),ensure_ascii=False)


TOOL={'name':'spectro_control','description':'Controle SEU holograma no desktop Windows. enter/exit entra e volta a base; scale usa factor relativo ou size em pixels logicos; opacity usa value absoluto 0.18-1 ou delta; position usa anchor; reset restaura; minimal reduz presenca. clear limpa somente marcacoes temporarias. observe_current autoriza acompanhar APENAS o app em primeiro plano mediante fala atual; privacy interrompe observacao e apaga contexto/marcacoes; resume_observation requer fala atual e reutiliza somente apps permitidos. context consulta observacao real; highlight usa control_id real do contexto; note mostra texto temporario; quiet pausa sugestoes. inspect consulta estado. Nao confirme efeito sem completed/estado real. Nao invente alvos ou permissao de observacao.','parameters':{'type':'OBJECT','properties':{
    'operation':{'type':'STRING','enum':['inspect','enter','exit','scale','opacity','position','reset','minimal','clear','observe_current','resume_observation','privacy','context','highlight','note','quiet','forget_app']},
    'factor':{'type':'NUMBER'},'size':{'type':'INTEGER'},'value':{'type':'NUMBER'},'delta':{'type':'NUMBER'},
    'anchor':{'type':'STRING','enum':['left','right','center','opposite','top','bottom','next_monitor']},
    'control_id':{'type':'STRING'},'text':{'type':'STRING'},'enabled':{'type':'BOOLEAN'},'app':{'type':'STRING'}},'required':['operation']},'handler':spectro_control}
TOOL['parameters']['properties']['shape']={'type':'STRING','enum':['outline','circle','arrow','marker','underline','cross']}
TOOL['parameters']['properties']['color']={'type':'STRING','description':'Cor #RRGGBB ou amarelo/vermelho/verde/azul/roxo/branco.'}
TOOL['parameters']['properties']['dx']={'type':'NUMBER','description':'Deslocamento horizontal em pixels logicos, negativo para esquerda.'}
TOOL['parameters']['properties']['dy']={'type':'NUMBER','description':'Deslocamento vertical em pixels logicos, negativo para cima.'}
TOOL['description']+=' Em inspect, transition informa animacao e destino; marking.state informa pending/visible/lost/idle. So confirme marcacao visivel quando annotations.count/items confirmarem. Marcar ou mostrar uma nota nao clica nem executa acoes; use as ferramentas existentes para agir e confira seu resultado.'
TOOL['description']+=' A observacao automatica agora inicia por padrao em todos os modos; context consulta a janela em primeiro plano sem nova autorizacao. privacy pausa. observe_current/resume_observation continuam sendo pedidos explicitos para retomar uma pausa. highlight aceita marker (marca-texto), underline, cross e color. Use os control_id observados; nao invente coordenadas.'
TOOL['parameters']['properties']['operation']['enum'].append('draw')
TOOL['parameters']['properties']['points']={'type':'ARRAY','items':{'type':'ARRAY','items':{'type':'NUMBER'}},'description':'2 a 32 pares [x,y] de 0 a 1 no monitor escolhido. Obtenha posicoes da tela observada.'}
TOOL['parameters']['properties']['screen']={'type':'STRING','description':'Nome real do monitor; omitido usa o monitor do holograma.'}
TOOL['description']='Controle do holograma Espectro: enter/exit; scale factor/size; opacity value/delta; position anchor/dx/dy; reset/minimal. Observacao da janela ativa e automatica em todos os modos; context consulta controles acessiveis reais, sem nova permissao. privacy pausa; resume_observation/observe_current retomam somente mediante pedido atual. highlight usa control_id real, shape outline/circle/arrow/marker/underline/cross e color #RRGGBB ou nome. draw desenha linhas e simbolos com points normalizados no monitor screen; consultar imagem real antes de escolher coordenadas. note mostra texto. clear limpa marcacoes, quiet pausa sugestoes, forget_app remove preferencia e pausa. inspect informa transicao, observacao e marcacoes realmente visiveis. Nao confirme marcacao sem annotations.count/items; nao invente alvos. Desenhos sao sobreposicoes temporarias e nao clicam: use ferramentas de computador para agir e confira o resultado.'
