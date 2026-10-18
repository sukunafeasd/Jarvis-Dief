"""Scientific source facts shared with the artistic solar scene."""
import json
from pathlib import Path
from core.essential_plugins import respond
PLUGIN={'name':'planet_knowledge','description':'Fatos NASA usados nas fichas do sistema solar. list/read/compare consultam medidas aproximadas com fonte. planet e other sao IDs do catalogo. Para focar planeta use interface_control environment; para fixar os fatos consultados use visual_composer com dados e fontes. Nao representa posicoes reais nem cria conexao com relogio/celular.',
 'parameters':{'type':'OBJECT','properties':{'action':{'type':'STRING','enum':['list','read','compare']},'planet':{'type':'STRING'},'other':{'type':'STRING'},'show':{'type':'BOOLEAN','description':'Em read, focar o planeta consultado no cenario. Padrao verdadeiro.'}},'required':['action']}}


def facts(parameters):
    catalog=json.loads((Path(__file__).resolve().parents[1]/'core/spatial/planet-facts.json').read_text(encoding='utf-8'))
    if parameters.get('action')=='list':return {'ok':True,'items':[{'id':key,'name':value['name']} for key,value in catalog.items()]}
    identifiers=[parameters.get('planet')]
    if parameters.get('action')=='compare':identifiers.append(parameters.get('other'))
    if any(identifier not in catalog for identifier in identifiers):raise ValueError('Use um ID real retornado por list.')
    return {'ok':True,'items':[{'id':key,**catalog[key]} for key in identifiers],'artistic_scale':True,'values':'Medidas arredondadas, nao efemerides atuais.'}


def run(parameters,player=None,**kwargs):
    def execute():
        result=facts(parameters)
        if parameters.get('action')=='read' and parameters.get('show',True) and player:
            result['presentation']=player.control_interface('environment',parameters['planet'],'')
        return result
    return respond(execute)
