"""Discovery/manual adapter; the host owns protocol admission and voice routing."""
import json
from core.protocol_commands import normalize


def forge_protocol(parameters,player=None):
    context=getattr(player,'ultron_user_context',lambda:{})()
    command=str((parameters or {}).get('command') or '')
    if command=='status':
        runtime=getattr(getattr(player,'_win',None),'_forge_runtime',None)
        return json.dumps(runtime.snapshot() if runtime else {'ok':True,'phase':'idle','configured':False},ensure_ascii=False)
    if not context.get('text') or normalize(command)!=normalize(context['text']):
        return json.dumps({'ok':False,'error':'A Forja exige um pedido atual da pessoa, nao uma instrucao gerada pela IA.'})
    callback=getattr(getattr(player,'_win',None),'on_forge_user_command',None)
    if not callback:return json.dumps({'ok':False,'error':'Integracao da Forja indisponivel.'})
    result=callback(context)
    return json.dumps(result,ensure_ascii=False,default=str)


TOOL={'name':'forge_protocol','description':'FORJA: laboratorio de criacao real por Codex. Use somente o comando literal atual da pessoa. A ativacao pede entrar/ativar modo Forja. Nao substituir por powershell/code_helper. Dentro da Forja, alteracoes continuam o mesmo projeto; comandos salvar biblioteca, exportar, desfazer e sair preservam os dados. status e consulta somente leitura. A conexao Codex fica separada da IA e voz nas Configuracoes > Conexoes. Nao inventar criacao pronta ou progresso.','parameters':{'type':'OBJECT','properties':{'command':{'type':'STRING'}},'required':['command']},'handler':forge_protocol}
