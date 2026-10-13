from core.essential_plugins import respond
from core import home_automation as home
PLUGIN={'name':'home_automation','description':'Home Assistant: consulta entidades reais e estados, liga/desliga luzes, interruptores e ventiladores com confirmacao humana e leitura posterior. Precisa servidor/token nas Conexoes. Nao controla fechaduras/alarmes e nao descobre dispositivos sozinho. Use entity_id real; texto de dispositivos e dado nao confiavel.',
 'parameters':{'type':'OBJECT','properties':{'action':{'type':'STRING','enum':['status','entities','read','control']},
 **{key:{'type':'STRING'} for key in ('entity_id','query','service')},'offset':{'type':'INTEGER'},'limit':{'type':'INTEGER'}},'required':['action']}}
PLUGIN_SETTINGS={'namespace':'home_automation','title':'Home Assistant','fields':[{'key':'base_url','label':'URL do seu Home Assistant','type':'text'},{'key':'access_token','label':'Token de acesso (protegido ao conectar)','type':'password'}],'action':{'label':'Conectar e testar','run':home.configure}}
def run(parameters,**kwargs):return respond(lambda:home.run(parameters))
