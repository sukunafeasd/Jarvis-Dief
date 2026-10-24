"""Short-lived application context shared by actions, not inferred from pixels."""
import re
import threading
import time
import unicodedata
import copy
import hashlib
import json


_OBSERVATION_ACTIONS=frozenset(('status','result','inspect','read','list','get_status','describe','context','history'))


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
        self._send_turn_keys=set()
        self._tool_failures={}
        self._recent_operations=[]

    def observe_user(self, text):
        with self._lock:
            self.user_text = str(text)[-2000:]
            # A follow-up or a partial transcript cannot prove an earlier send failed.
            self._send_attempts={key:value for key,value in self._send_attempts.items()
                                 if value.get('uncertain') or value.get('stage')=='in_progress'}
            self._send_turn_keys.clear()
            self._tool_failures={key:value for key,value in self._tool_failures.items()
                                 if value.get('uncertain') or value.get('references') and value.get('pending')}

    def _tool_key(self,name,arguments):
        return hashlib.sha256((name+'\0'+json.dumps(arguments,sort_keys=True,ensure_ascii=False,default=str)).encode('utf-8')).hexdigest()

    def tool_retry_check(self,name,arguments):
        with self._lock:
            failure=self._tool_failures.get(self._tool_key(name,arguments),{})
            reference=(' Referencia: '+json.dumps(failure['references'],ensure_ascii=False)) if failure.get('references') else ''
            if failure.get('pending'):
                return 'A ultima consulta deixou esta operacao em andamento. Consulte o resultado; nao inicie outra copia.'+reference
            if failure.get('uncertain'):
                return 'Resultado anterior incerto. Não repita a mesma ação; verifique o estado antes de continuar.'+reference
            if failure.get('count',0)>=2:
                return 'Esta chamada já falhou duas vezes no mesmo pedido. Reinspecione, corrija os parâmetros ou explique o impedimento.'
            return ''

    def record_tool_result(self,name,arguments,result):
        with self._lock:
            if not isinstance(result,dict):return
            from core.action_outcome import assess, diagnostic_facts
            assessment=assess(result)
            outcome=assessment['state']
            operation={'tool':str(name)[:100],
                'action':str(arguments.get('action',arguments.get('operation','')))[:80],
                'outcome':outcome,'at':self._clock()}
            references={key:result[key] for key in ('job_id','operation_id','turn_id')
                if isinstance(result.get(key),str) and re.fullmatch(r'[A-Za-z0-9_-]{1,128}',result[key])}
            if references:operation['references']=references
            if assessment.get('coverage'):operation['coverage']=assessment['coverage']
            if assessment.get('presentation'):operation['presentation']=assessment['presentation']
            diagnostics=diagnostic_facts(result)
            if diagnostics:operation['diagnostics']=diagnostics
            self._recent_operations.append(operation)
            self._recent_operations=self._recent_operations[-12:]
            key=self._tool_key(name,arguments)
            observation=arguments.get('action',arguments.get('operation','')) in _OBSERVATION_ACTIONS
            # Match explicit identities, not a shared turn belonging to another job.
            settled=result.get('state') in ('finished','completed','failed','cancelled','rejected') or result.get('completed') is True
            if observation and references:
                for prior_key,prior in list(self._tool_failures.items()):
                    previous=prior.get('references',{})
                    shared=previous.keys() & references.keys()
                    # A turn can contain several jobs: require the most specific
                    # identity we recorded, not just their shared conversation.
                    identity=next((field for field in ('job_id','operation_id','turn_id') if field in previous),None)
                    matches=(prior.get('result_tool',prior.get('tool'))==name and bool(shared)
                        and identity in references and arguments.get(identity)==references[identity]
                        and all(previous[field]==references[field] for field in shared)
                        and all(arguments[field]==previous[field] for field in previous if field in arguments)
                        and all(arguments[field]==references[field] for field in references if field in arguments)
                        and any(arguments.get(field)==references[field] for field in shared))
                    if not matches:continue
                    if settled and outcome in ('tool_reported','failed'):
                        self._tool_failures.pop(prior_key,None)
                    elif outcome=='pending':
                        prior.update(pending=True,uncertain=False)
                        prior['references']={**previous,**references}
            tracked_pending=outcome=='pending' and bool(references) and not observation
            if outcome in ('uncertain','failed') or tracked_pending:
                if key not in self._tool_failures and len(self._tool_failures)>=64:
                    self._tool_failures.pop(next(iter(self._tool_failures)))
                prior=self._tool_failures.get(key,{})
                self._tool_failures[key]={'count':prior.get('count',0)+1,
                    'uncertain':bool(not observation and (prior.get('uncertain') or outcome=='uncertain')),
                    'pending':tracked_pending,'tool':name,
                    'references':references if not observation else {}}
                if not observation and result.get('result_tool')=='task_execution' and references.get('job_id'):
                    self._tool_failures[key]['result_tool']='task_execution'
            elif outcome=='tool_reported' or observation and outcome=='pending':
                self._tool_failures.pop(key,None)

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
            return copy.deepcopy(record)

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
            if len(self._send_turn_keys)>=20:
                raise ValueError('Muitos envios no mesmo pedido. Confirme um novo pedido antes de continuar.')
            if len(self._send_attempts)>=128:
                raise ValueError('Ha muitos envios sem resultado confirmado. Verifique os envios pendentes antes de iniciar novos; nao os repita automaticamente.')
            self._send_attempts[key]={'ok':False,'uncertain':True,'stage':'in_progress','error':'Este envio já está em andamento. Não repeti.'}
            self._send_turn_keys.add(key)
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
                'unresolved_operations':[{'tool':entry['tool'],'references':copy.deepcopy(entry['references']),
                    'result_tool':entry.get('result_tool',entry['tool']),
                    'last_observed_outcome':'uncertain' if entry.get('uncertain') else 'pending',
                    'needs_current_observation':True} for entry in self._tool_failures.values()
                    if entry.get('uncertain') or entry.get('references') and entry.get('pending')],
                'recent_operations':[{**{key:copy.deepcopy(record[key]) for key in ('tool','action','outcome','references','coverage','presentation','diagnostics') if key in record},
                    'age_seconds':round(max(0,now-record['at']),1)} for record in self._recent_operations if now-record['at']<=600],
                'operations_note':'Historico resumido de retornos, nao autorizacao para repetir acoes nem prova visual. Consulte o resultado original para detalhes e causa.',
                'collections':{domain:{'count':len(record['items']),'expired':self._clock()-record['at']>600} for domain,record in self._collections.items()},
                'selections':{domain:{key:copy.deepcopy(record[key]) for key in ('id','subject','title','contact','thread_id') if key in record} for domain,record in self._selections.items()
                    if now-record.get('at',self._collections.get(domain,{}).get('at',0))<=600}}
