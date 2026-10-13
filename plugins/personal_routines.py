from core.essential_plugins import respond
from core import personal_routines as routines
PLUGIN={'name':'personal_routines','description':'Rotinas pessoais determinísticas, persistentes: combinar consultas de tarefas, agenda Google ou local, Gmail importante, clima e notícias. briefing consulta agora; create agenda uma vez ou diariamente enquanto Jarvis estiver aberto. Exige horário futuro ISO com fuso. Não executa código, envios ou ações arbitrárias. list mostra IDs; enable/disable/delete usam ID real. Não prometa execução com aplicativo fechado.',
 'parameters':{'type':'OBJECT','properties':{
    'action':{'type':'STRING','enum':['briefing','create','list','enable','disable','delete']},
    'domains':{'type':'ARRAY','items':{'type':'STRING','enum':list(routines.DOMAINS)}},
    **{key:{'type':'STRING'} for key in ('title','due','id')},'repeat':{'type':'STRING','enum':['once','daily']}},'required':['action']}}
def run(parameters,player=None,**kwargs):return respond(lambda:routines.run(parameters,player))
