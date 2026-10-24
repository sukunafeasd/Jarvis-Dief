from core.essential_plugins import respond
from core.task_execution import LEDGER
from core.resource_jobs import snapshot
PLUGIN={'name':'task_execution','description':'Planeja etapas create/read/cancel; history mostra evidencias registradas automaticamente pelas ferramentas e attach liga evidencia REAL a etapa. Nunca executa acoes por criar plano e nunca declara objetivo concluido so porque uma ferramenta retornou ok. result consulta job_id de uma operacao aguardando confirmacao humana. Planejamento nao substitui reinspecao da interface ou consulta ao provedor.',
 'parameters':{'type':'OBJECT','properties':{'action':{'type':'STRING','enum':['history','list','create','read','cancel','archive','attach','checkpoint','result']},
 **{k:{'type':'STRING'} for k in ('title','id','evidence_id','job_id','note')},'step':{'type':'INTEGER'},'steps':{'type':'ARRAY','items':{'type':'STRING'}}},'required':['action']}}
PLUGIN['description']+=' list recupera planos desta sessao; read inclui resultados reais por etapa. checkpoint usa id/step/note para registrar bloqueio e proximo passo; nao conclui tarefas. Evidencia expirada deve ser consultada novamente.'
PLUGIN['description']+=' Planos persistem localmente entre sessoes. archive encerra o acompanhamento SEM declarar sucesso. Evidencia anexada e uma referencia: confira se a ferramenta verificou o alvo e o objetivo desta etapa antes de narrar um resultado. Retomar plano nao autoriza repetir acoes anteriores; consulte estado atual.'
def run(parameters,**kwargs):return respond(lambda:snapshot(parameters.get('job_id')) if parameters.get('action')=='result' else LEDGER.run(parameters))
