from core import fish_audio
from core.essential_plugins import respond
PLUGIN={'name':'fish_audio','description':'Voz Fish Audio padrao local. status informa configuracao; autorizacao somente nas Conexoes. Nao sintetize por ferramenta enquanto o pipeline de fala ja apresenta a resposta.',
 'parameters':{'type':'OBJECT','properties':{'action':{'type':'STRING','enum':['status']}},'required':['action']}}
PLUGIN_SETTINGS={'namespace':'fish_audio','title':'Voz Fish Audio','fields':[
 {'key':'access_token','label':'Chave Fish Audio (protegida neste PC)','type':'secret'},
 {'key':'voice_id','label':'ID da voz (vazio usa a voz padrao DIEF JARVIS)','type':'text'}],
 'setup_url':'https://fish.audio/app/api-keys','setup_label':'Abrir conta Fish Audio',
 'action':{'label':'Testar voz','run':fish_audio.verify}}
def run(parameters,**kwargs):return respond(fish_audio.status)
