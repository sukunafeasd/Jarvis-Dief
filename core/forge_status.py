"""Factual, concise status shared by the panel and voice, not raw agent logs."""

def summary(state):
    phase=state.get('phase','idle')
    validation=state.get('preview_validation','none')
    if state.get('command_pending'):
        return {'title':'Preparando seu pedido','detail':'O novo comando esta em processamento. A previa anterior nao representa a conclusao deste pedido.','status':'waiting'}
    if phase=='error':
        return {'title':'Trabalho interrompido','detail':state.get('error') or 'O motor encontrou uma falha. O projeto foi preservado.','status':'failed'}
    if phase=='running':
        activities=state.get('activities') or []
        current=next((item for item in reversed(activities) if item.get('status') in ('running','streaming','inProgress','working')),{})
        kind=current.get('title','')
        title={'File changes':'Atualizando os arquivos','Command execution':'Verificando o projeto','Agent message':'Preparando a criacao'}.get(kind,'Criacao em andamento')
        return {'title':title,'detail':'O Codex trabalha no projeto atual. Ajustes continuam nesse mesmo projeto.','status':'running'}
    if phase=='recovering':
        return {'title':'Conclusao ainda nao confirmada','detail':'A etapa salva estava em andamento. O resultado ainda precisa ser confirmado pelo motor; os arquivos e a previa anterior foram preservados.','status':'waiting'}
    if state.get('preview_error'):
        return {'title':'Previa precisa de correcao','detail':state['preview_error'],'status':'failed'}
    if validation=='pending':
        return {'title':'Conferindo a previa','detail':'Verificando os recursos, a imagem e o enquadramento.','status':'waiting'}
    if state.get('preview_url') and validation=='passed':
        return {'title':'Previa pronta','detail':'A versao verificada esta na area de criacao.','status':'completed'}
    if state.get('generation_verified'):
        return {'title':'Etapa concluida','detail':'Os arquivos foram preservados. Ainda nao ha uma previa visual verificada.','status':'completed'}
    if not state.get('authenticated'):
        return {'title':'Conexao necessaria','detail':'Conecte sua conta em Configuracoes > Conexoes > Codex / Modo Forja.','status':'waiting'}
    return {'title':'Aguardando seu pedido','detail':'Descreva o que deseja criar ou ajustar.','status':'pending'}


def project_snapshot(state):
    project=state.get('project') or {}
    return {'project':project.get('name','') if isinstance(project,dict) else str(project),
            'state':state.get('phase','idle'),'visible':True,
            'engine':'Codex' if state.get('authenticated') else 'Conexao necessaria',
            'preview_url':state.get('preview_url'),
            'preview_version':project.get('revision') if isinstance(project,dict) else None,
            'activities':[{'id':'forge-status',**summary(state)}]}


def snapshot_current(state,runtime):
    fence=getattr(runtime,'display_epoch',None)
    if not callable(fence):return True
    current=fence()
    return type(current) is not int or state.get('command_epoch',0)==current
