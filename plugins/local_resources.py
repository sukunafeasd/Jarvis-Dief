from core.essential_plugins import respond
from core.local_resources import run as execute
PLUGIN={'name':'local_resources','description':'Contatos locais com apelidos e desambiguacao; notas; projetos/subtarefas; reunioes. list/search/read/create/update/complete/delete. transcribe envia arquivo de audio explicitamente fornecido ao Gemini somente apos confirmacao humana e retorna texto para revisao; nao grava microfone nem cria tarefas automaticamente. summarize extrai frases e candidatos a tarefas. Nunca escolha entre contatos ambiguos. ID vem da consulta. Exclusao exige confirmacao no painel. Nao e uma conta externa sincronizada.',
 'parameters':{'type':'OBJECT','properties':{
 'action':{'type':'STRING','enum':['status','list','search','resolve','read','create','update','complete','delete','summarize','transcribe']},
 'kind':{'type':'STRING','enum':['contact','note','project','meeting']},
 **{k:{'type':'STRING'} for k in ('id','title','text','query','email','phone','due','parent_id','priority','path')},
 'aliases':{'type':'ARRAY','items':{'type':'STRING'}},'offset':{'type':'INTEGER'},'limit':{'type':'INTEGER'}},'required':['action','kind']}}
def run(parameters,player=None,**kwargs):return respond(lambda:execute(parameters,player))
