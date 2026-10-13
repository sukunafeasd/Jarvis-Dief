from core.office_resources import run as execute
from core.essential_plugins import respond
PLUGIN={'name':'office_resources','description':'Le documentos paginados, compara trechos e cria DOCX/TXT/MD e XLSX/CSV NOVOS. rows_json e uma matriz JSON; chart cria barras dos dados reais; edit_spreadsheet edita celulas numa copia nova. statistics calcula coluna numerica sem executar formulas. convert_image e annotate_image preservam o original. Gravacao requer confirmacao humana; result no task_execution consulta job_id. Nao abre macros, nao executa codigo nem sobrescreve arquivos.',
 'parameters':{'type':'OBJECT','properties':{'action':{'type':'STRING','enum':['status','read','compare','document','spreadsheet','statistics','convert_image','edit_spreadsheet','annotate_image']},
 **{key:{'type':'STRING'} for key in ('path','other','title','text','rows_json','sheet')},
 'edits_json':{'type':'STRING','description':'Lista JSON [{"cell":"A1","value":"texto"}]. other=fonte XLSX; path=destino NOVO. Texto de formula permanece literal.'},
 'annotations_json':{'type':'STRING','description':'Lista JSON de {type:rect,coords:[x1,y1,x2,y2],color:cyan} ou {type:text,coords:[x,y],text:legenda,color:white}; pixels dentro da imagem, maximo 50.'},
 'chart':{'type':'BOOLEAN','description':'Em spreadsheet XLSX, criar grafico de barras real; primeira coluna=categorias, column=coluna numerica, primeira linha=cabecalho.'},
 'column':{'type':'INTEGER'},'offset':{'type':'INTEGER'},'max_chars':{'type':'INTEGER'}},'required':['action']}}
def run(parameters,**kwargs):return respond(lambda:execute(parameters))
