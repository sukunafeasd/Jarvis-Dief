"""Resultados verificaveis de operacoes confirmadas no painel, nunca pelo modelo."""
import copy
import threading
import time
import uuid
from core import confirm

LOCK=threading.RLock()
JOBS={}


def snapshot(identifier):
    with LOCK:
        if identifier not in JOBS:
            raise ValueError('Operacao desconhecida ou expirada.')
        return copy.deepcopy(JOBS[identifier])


def request(title, detail, callback):
    with LOCK:
        for key,value in list(JOBS.items()):
            if time.monotonic()-value['at']>600 and value['state']!='running':
                JOBS.pop(key)
        if len(JOBS)>=32:
            removable=next((key for key,value in JOBS.items() if value['state'] in ('done','failed','cancelled')),None)
            if removable is None:
                raise ValueError('Ha operacoes demais em andamento.')
            JOBS.pop(removable)
        identifier=uuid.uuid4().hex
        JOBS[identifier]={'id':identifier,'state':'awaiting_confirmation','at':time.monotonic(),'completed':False}
    def resolved(accepted):
        with LOCK:
            JOBS[identifier]['state']='running' if accepted else 'cancelled'
    def execute():
        try:
            result=callback()
            if not isinstance(result,dict):
                raise ValueError('Operacao sem resultado estruturado.')
            with LOCK:
                JOBS[identifier].update(state='done' if result.get('ok',True) and not result.get('uncertain') else 'failed',completed=bool(result.get('ok',True) and not result.get('uncertain')),result=result)
            return 'Resultado registrado. Consulte a operacao '+identifier+'.'
        except Exception as error:
            with LOCK:
                JOBS[identifier].update(state='failed',completed=False,error=type(error).__name__,uncertain=True)
            return 'Nao confirmei o resultado. Consulte a operacao '+identifier+'.'
    message=confirm.request('resource:'+identifier,title,detail,execute,on_resolve=resolved)
    if '[CONFIRMATION_PENDING]' not in message:
        with LOCK:JOBS.pop(identifier,None)
        return {'ok':False,'completed':False,'error':message}
    return {'ok':True,'completed':False,'state':'awaiting_confirmation','job_id':identifier,'message':message}
