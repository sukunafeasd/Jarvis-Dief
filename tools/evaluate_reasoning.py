"""Opt-in provider evaluation using synthetic scenarios, never executing tools."""
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parents[1]


CASES=[
    {'id':'informal_reference','user':'bota aquele segundo compromisso na tela pra mim',
     'context':{'calendar_items':[{'id':'event-a','title':'Consulta'},{'id':'event-b','title':'Revisao'}]},
     'expected':{'decision':'tool','target_id':'event-b'}},
    {'id':'uncertain_send','user':'e ai, mandou? tenta de novo entao',
     'context':{'last_result':{'tool':'message_send','uncertain':True,'job_id':'job-a'}},
     'expected':{'decision':'inspect','target_id':'job-a'}},
    {'id':'ambiguous_reference','user':'continua aquele projeto',
     'context':{'projects':[{'id':'proj-a','title':'Loja'},{'id':'proj-b','title':'Agenda'}],
                'selected_project':None},'expected':{'decision':'clarify','target_id':None}},
    {'id':'novel_multistep','user':'compare os dois relatórios, confira divergências e só crie a apresentação se os números baterem',
     'context':{'attachments':['report-a','report-b'],'reports_read':False},
     'expected':{'decision':'plan','target_id':None}},
    {'id':'display_error','user':'o compromisso foi salvo mas nao apareceu aqui, arruma isso',
     'context':{'last_result':{'ok':True,'event':{'id':'event-c'},'presentation':{'ok':False}}},
     'expected':{'decision':'inspect','target_id':'event-c'}},
    {'id':'conversation_not_command','user':'voce acha que vale a pena fazer um site pra essa ideia ou estou exagerando?',
     'context':{'mode':'forja','project':None},'expected':{'decision':'conversation','target_id':None}},
]


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--credentials',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    # Read only the selected provider key; no personal history or account data is sent.
    key=json.loads(args.credentials.read_text(encoding='utf-8')).get('gemini_api_key','')
    if not key:raise SystemExit('Chave Gemini ausente; avaliacao nao executada.')
    os.environ['QT_QPA_PLATFORM']='offscreen'
    os.environ['DIEF_JARVIS_DATA_DIR']=tempfile.mkdtemp(prefix='dief-reasoning-eval-')
    sys.path.insert(0,str(ROOT))
    from core import gemini
    from core.personality import BASE_INSTRUCTIONS
    from core.intent_context import build
    base=(ROOT/'core/prompt.txt').read_text(encoding='utf-8')
    for field,value in {'assistant_name':'DIEF JARVIS','platform':'Windows',
                        'capabilities':'Consulte, apresente e compare dados; nenhuma ferramenta e executada nesta avaliacao.',
                        'limits':'Somente evidencias sinteticas fornecidas.'}.items():
        base=base.replace('{'+field+'}',value)
    results=[]
    for case in CASES:
        started=time.monotonic()
        request={'pedido':case['user'],'estado_observado':case['context'],
                 'interpretation':build(case['user'])}
        prompt=base+'\n'+BASE_INSTRUCTIONS+'\n'+(
            'AVALIACAO SEM EXECUCAO: escolha somente o proximo passo, sem executar nada. '
            'Retorne JSON com decision (conversation, clarify, inspect, tool ou plan), '
            'target_id (ID real do alvo, ou null quando falta alvo ou ha varios) e reply '
            '(uma resposta natural curta em portugues). Plan representa trabalho com etapas e condicoes; '
            'inspect representa verificar o estado antes de alterar. Nao invente resultados.\n')+json.dumps(request,ensure_ascii=False)
        reply=gemini.as_json(prompt,timeout_ms=20000,key=key,default=None)
        parsed=reply if isinstance(reply,dict) else {}
        passed=all(parsed.get(k)==v for k,v in case['expected'].items()) and bool(parsed.get('reply'))
        results.append({'id':case['id'],'passed':passed,'elapsed_seconds':round(time.monotonic()-started,2),
                        'expected':case['expected'],'actual':parsed})
        print(json.dumps({k:results[-1][k] for k in ('id','passed','elapsed_seconds')}),flush=True)
    report={'scope':'Synthetic text decisions with provider; not end-to-end Live audio or tool execution',
            'passed':all(row['passed'] for row in results),'cases':results}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return 0 if report['passed'] else 1


if __name__=='__main__':sys.exit(main())
