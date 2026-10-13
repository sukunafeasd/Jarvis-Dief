from core.essential_plugins import respond
from core.resource_monitor import run as execute
PLUGIN={'name':'resource_monitor','description':'Monitor opt-in de arquivos explicitamente escolhidos; avisa somente quando hash ou existencia muda. create/list/check/enable/disable/delete, IDs reais. Maximo vinte; verifica com Jarvis aberto e nao executa conteudo nem le o arquivo para a IA automaticamente. Nao monitora contas externas por este plugin.',
 'parameters':{'type':'OBJECT','properties':{'action':{'type':'STRING','enum':['create','list','check','enable','disable','delete']},'path':{'type':'STRING'},'id':{'type':'STRING'}},'required':['action']}}
def run(parameters,**kwargs):return respond(lambda:execute(parameters))
