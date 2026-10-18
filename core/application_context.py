"""Short-lived application context shared by actions, not inferred from pixels."""
import re
import threading
import time
import unicodedata
import copy
import hashlib
import json


def normalized(text):
    return ''.join(c for c in unicodedata.normalize('NFKD', str(text).lower())
                   if not unicodedata.combining(c)).strip()


class ApplicationContext:
    def __init__(self, clock=time.monotonic):
        self._clock = clock
        self._lock = threading.RLock()
        self._app = ''
        self._at = 0
        self.user_text = ''
        self._collections={}
        self._selections={}
        self._send_attempts={}
        self._tool_failures={}
        self._recent_operations=[]

    def observe_user(self, text):
        with self._lock:
            self.user_text = str(text)[-2000:]
            self._send_attempts.clear()
            self._tool_failures.clear()

    def _tool_key(self,name,arguments):
        return hashlib.sha256((name+'\0'+json.dumps(arguments,sort_keys=True,ensure_ascii=False,default=str)).encode('utf-8')).hexdigest()

    def tool_retry_check(self,name,arguments):
        with self._lock:
            failure=self._tool_failures.get(self._tool_key(name,arguments),{})
            if failure.get('uncertain'):
                return 'Resultado anterior incerto. Não repita a mesma ação; verifique o estado antes de continuar.'
            if failure.get('count',0)>=2:
                return 'Esta chamada já falhou duas vezes no mesmo pedido. Reinspecione, corrija os parâmetros ou explique o impedimento.'
            return ''

    def record_tool_result(self,name,arguments,result):
        with self._lock:
            if not isinstance(result,dict):return
            from core.action_outcome import assess
            outcome=assess(result)['state']
            operation={'tool':str(name)[:100],
                'action':str(arguments.get('action',''))[:80],
                'outcome':outcome,'at':self._clock()}
            references={key:result[key] for key in ('job_id','operation_id','turn_id')
                if isinstance(result.get(key),str) and re.fullmatch(r'[A-Za-z0-9_-]{1,128}',result[key])}
            if references:operation['references']=references
            self._recent_operations.append(operation)
            self._recent_operations=self._recent_operations[-12:]
            key=self._tool_key(name,arguments)
            if outcome in ('uncertain','failed'):
                if key not in self._tool_failures and len(self._tool_failures)>=64:
                    self._tool_failures.pop(next(iter(self._tool_failures)))
                prior=self._tool_failures.get(key,{})
                self._tool_failures[key]={'count':prior.get('count',0)+1,
                    'uncertain':bool(prior.get('uncertain') or outcome=='uncertain')}
            elif outcome=='tool_reported':self._tool_failures.pop(key,None)

    def record_collection(self,domain,items,**metadata):
        with self._lock:
            records=[]
            for item in items[:100]:
                records.append({key:copy.deepcopy(item[key]) for key in ('id','title','subject','contact','thread_id','due','priority','date') if key in item})
            self._collections[domain]={'items':records,'at':self._clock(),'metadata':copy.deepcopy(metadata)}
            self._selections.pop(domain,None)

    def collection(self,domain):
        with self._lock:
            item=self._collections.get(domain)
            if not item or self._clock()-item['at']>600:
                raise ValueError('A lista expirou. Consulte o domínio novamente antes de selecionar.')
            return copy.deepcopy(item)

    def resolve_record(self,domain,selection):
        with self._lock:
            collection=self.collection(domain)
            if not isinstance(selection,int) or isinstance(selection,bool) or not 1<=selection<=len(collection['items']):
                raise ValueError('Número fora da lista consultada. Não selecionei um item ao acaso.')
            record=collection['items'][selection-1]
            self._selections[domain]={**copy.deepcopy(record),'at':self._clock()}
            return record

    def remember_selection(self,domain,record):
        fields=('id','subject','title','contact','thread_id','body_next_offset')
        with self._lock:self._selections[domain]={**{key:copy.deepcopy(record[key]) for key in fields if key in record},'at':self._clock()}

    def selection(self,domain):
        with self._lock:
            record=self._selections.get(domain)
            if not record or self._clock()-record.get('at',self._collections.get(domain,{}).get('at',0))>600:
                raise ValueError('Nenhum item selecionado recentemente. Consulte a lista e selecione um item.')
            return copy.deepcopy(record)

    def begin_send(self,platform,receiver,message):
        key=hashlib.sha256((platform+'\0'+normalized(receiver)+'\0'+message).encode('utf-8')).hexdigest()
        with self._lock:
            if key in self._send_attempts:
                return key,copy.deepcopy(self._send_attempts[key])
            if len(self._send_attempts)>=20:
                raise ValueError('Muitos envios no mesmo pedido. Confirme um novo pedido antes de continuar.')
            self._send_attempts[key]={'ok':False,'uncertain':True,'stage':'in_progress','error':'Este envio já está em andamento. Não repeti.'}
            return key,None

    def finish_send(self,key,result):
        with self._lock:
            if key in self._send_attempts:self._send_attempts[key]=copy.deepcopy(result)

    def select(self, app):
        with self._lock:
            self._app, self._at = str(app), self._clock()

    def current(self):
        with self._lock:
            return self._app if self._clock() - self._at < 600 else ''

    def search_target(self, scope='auto', text=None):
        text = normalized(self.user_text if text is None else text)
        if scope == 'web' or re.search(r'\b(google|internet|navegador|web|bing)\b', text):
            return ''
        for name in ('spotify', 'excel', 'word', 'discord', 'telegram', 'notepad'):
            if re.search(r'\b(?:no|na|dentro (?:do|da)|in)\s+' + name + r'\b', text):
                return name
        if scope == 'app' or re.search(r'\b(pesquis\w*|busc\w*|procur\w*|search|find)\b', text):
            return self.current()
        return ''

    def snapshot(self):
        with self._lock:
            now=self._clock()
            return {'active_app': self.current(), 'expires_after_seconds': 600,
                'recent_operations':[{**{key:copy.deepcopy(record[key]) for key in ('tool','action','outcome','references') if key in record},
                    'age_seconds':round(max(0,now-record['at']),1)} for record in self._recent_operations if now-record['at']<=600],
                'operations_note':'Historico resumido de retornos, nao autorizacao para repetir acoes nem prova visual. Consulte o resultado original para detalhes e causa.',
                'collections':{domain:{'count':len(record['items']),'expired':self._clock()-record['at']>600} for domain,record in self._collections.items()},
                'selections':{domain:{key:record[key] for key in ('id','subject','title','contact','thread_id') if key in record} for domain,record in self._selections.items()
                    if now-record.get('at',self._collections.get(domain,{}).get('at',0))<=600}}
