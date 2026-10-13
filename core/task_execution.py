"""Planejamento observavel sem executar acoes implicitas ou aceitar sucesso inventado."""
import copy
import threading
import time
import uuid
from collections import deque


class ExecutionLedger:
    def __init__(self):
        self.lock=threading.RLock();self.events=deque(maxlen=128);self.plans={}

    def record(self,name,result):
        with self.lock:
            evidence='unverified'
            if isinstance(result,dict):
                if result.get('uncertain'):evidence='uncertain'
                elif result.get('ok') is False or result.get('error'):evidence='failed'
                elif result.get('completed') is False or result.get('state') in ('awaiting_confirmation','running'):evidence='pending'
                elif result.get('ok') is True:evidence='tool_reported'
            identifier=uuid.uuid4().hex
            self.events.append({'id':identifier,'tool':name,'evidence':evidence,'at':time.time(),
                'verification_required':True,'note':'Retorno da ferramenta, nao prova independente do objetivo.'})
            return identifier

    def run(self,p):
        with self.lock:
            action=p.get('action','history')
            if action=='history':return {'events':list(self.events)[-20:]}
            if action=='create':
                steps=p.get('steps',[])
                if not p.get('title') or not isinstance(steps,list) or not 1<=len(steps)<=20 or any(not isinstance(s,str) or not s.strip() or len(s)>400 for s in steps):
                    raise ValueError('Informe titulo e de uma a vinte etapas curtas.')
                if len(self.plans)>=20:
                    expired=next((k for k,v in self.plans.items() if v['state']=='cancelled'),None)
                    if expired is None:raise ValueError('Limite de planos ativos atingido.')
                    self.plans.pop(expired)
                identifier=uuid.uuid4().hex
                self.plans[identifier]={'id':identifier,'title':str(p['title'])[:300],'state':'planned','steps':[{'text':s,'evidence_ids':[]} for s in steps],'execution_started':False}
                return copy.deepcopy(self.plans[identifier])
            identifier=p.get('id')
            if identifier not in self.plans:raise ValueError('Consulte um plano real primeiro.')
            plan=self.plans[identifier]
            if action=='cancel':plan['state']='cancelled'
            elif action=='attach':
                index=int(p.get('step',0))-1
                if plan['state']=='cancelled' or not 0<=index<len(plan['steps']):raise ValueError('Etapa invalida ou plano cancelado.')
                evidence=next((e for e in self.events if e['id']==p.get('evidence_id')),None)
                if evidence is None:raise ValueError('Evidencia desconhecida. Nao aceito completed=true do modelo.')
                if evidence['id'] not in plan['steps'][index]['evidence_ids']:plan['steps'][index]['evidence_ids'].append(evidence['id'])
                plan['state']='tracking'
            elif action!='read':raise ValueError('Acao invalida.')
            return copy.deepcopy(plan)

LEDGER=ExecutionLedger()
