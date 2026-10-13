from core.resource_backups import run as execute
from core.essential_plugins import respond
PLUGIN={'name':'resource_backups','description':'Backup de memoria e registros locais com manifesto/hash. Nunca inclui tokens, sessoes, credenciais ou arquivos arbitrarios. create e restore pedem confirmacao humana; restore recupera para pasta NOVA sem substituir bancos em uso. inspect verifica integridade. Consulte job_id no task_execution para resultado real.',
 'parameters':{'type':'OBJECT','properties':{'action':{'type':'STRING','enum':['status','create','inspect','restore']},'path':{'type':'STRING'},'destination':{'type':'STRING'}},'required':['action']}}
def run(parameters,**kwargs):return respond(lambda:execute(parameters))
