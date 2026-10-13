from core.essential_plugins import respond
from core.desktop_resources import run as execute
PLUGIN={'name':'desktop_resources','description':'Utilidades explicitas: clipboard read/write sem historico continuo; git status/diff/history somente consulta na raiz do repositorio; notes list/read/create em cofre Markdown/Obsidian indicado; iphone status/open_link abre pareamento Microsoft sem fingir conexao; audio status lista saidas e volume ajusta/confere volume. downloads list/download salva URL HTTPS publica explicitamente solicitada, ate 25 MB, sem executar nem seguir redirecionamentos. Nao faz commit/push, nao coleta clipboard sozinho, nao controla todo iOS. Criar/copiar/baixar pede confirmacao humana.',
 'parameters':{'type':'OBJECT','properties':{'domain':{'type':'STRING','enum':['clipboard','git','notes','iphone','audio','downloads']},
 'action':{'type':'STRING','enum':['status','read','write','diff','history','list','create','open_link','volume','download']},
 **{key:{'type':'STRING'} for key in ('folder','path','text','query','url','filename')},'value':{'type':'INTEGER'},'offset':{'type':'INTEGER'},'limit':{'type':'INTEGER'}},'required':['domain','action']}}
def run(parameters,**kwargs):return respond(lambda:execute(parameters))
