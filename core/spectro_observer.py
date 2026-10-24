"""Bounded background UI observation with immediate privacy invalidation."""
import time
from core.bounded_work import BoundedWork
from core.spectro_initiative import Initiative
from core import spectro_perception as perception

# One process-wide worker bounds even providers that cannot be interrupted.
_OBSERVATION_WORK=BoundedWork(workers=1,capacity=2,name='EspectroObservation')


def matching_controls(controls,query):
    from core.protocol_commands import normalize
    import re
    query=normalize(query)
    candidates=[item for item in controls if item.get('control_id')]
    exact=[item for item in candidates if normalize(item.get('name',''))==query]
    if exact:return exact
    words=re.findall(r'\w+',query)
    if not words:return []
    return [item for item in candidates if all(any(
        actual==word or len(word)>=4 and actual.startswith(word)
        for actual in re.findall(r'\w+',normalize(item.get('name','')))) for word in words)]


class Observer:
    def __init__(self,store,clock=time.monotonic,automatic=False):
        self.automatic=automatic
        self.store=store;self.clock=clock;self.enabled=automatic and not store.read().get('observation_paused',False);self.closed=False;self.generation=0
        self.current={};self.allowed=set(store.read()['allowed_apps']);self.pending=None
        self.pool=_OBSERVATION_WORK
        self.at=-float('inf');self.epoch=0;self.initiative=Initiative(clock);self.target=None;self.target_result=None
        self.last_error='';self.audit=[];self.audit_available=True
        self.target_lost=False;self.target_at=-float('inf');self.target_error=''
    def record(self,event,**data):
        self.audit=(self.audit+[{'event':event,'at':self.clock(),**data}])[-40:]
        try:self.store.audit(event,data)
        except (OSError,ValueError):self.audit_available=False
    def allow_current(self,expected=None):
        state=perception.foreground()
        if not state.get('ok'):raise ValueError(state.get('error','Janela indisponivel.'))
        if expected is not None and (state.get('handle'),state.get('process_id'),state.get('app'))!=(expected.get('handle'),expected.get('process_id'),expected.get('app')):
            raise ValueError('A janela mudou desde o pedido. Selecione o aplicativo e autorize novamente.')
        self.store.allow(state['app']);self.allowed.add(state['app']);self.enabled=True;self.generation+=1
        if self.automatic:self.store.update(lambda s:s.update(observation_paused=False))
        self.current={};self.target=None;self.target_result=None;self.initiative.clear();self.at=0
        self.target_lost=False;self.target_error=''
        self.record('authorized',app=state['app']);return state['app']
    def privacy(self,persist=True):
        self.enabled=False;self.generation+=1;self.current={};self.target=None;self.target_result=None
        self.target_lost=False;self.target_error=''
        if self.pending and self.pending.cancel():self.pending=None
        self.initiative.clear();self.record('privacy')
        if persist and self.automatic:
            try:self.store.update(lambda s:s.update(observation_paused=True))
            except (OSError,ValueError):self.last_error='Observacao pausada nesta sessao; nao consegui salvar a preferencia.'
    def resume(self):
        if not self.allowed and not self.automatic:raise ValueError('Nenhum aplicativo autorizado. Diga acompanhe este aplicativo.')
        if self.automatic:self.store.update(lambda s:s.update(observation_paused=False))
        self.enabled=True;self.generation+=1;self.current={};self.at=0;self.record('resumed')
    def clear_target(self,lost=False):
        self.generation+=1;self.target=None;self.target_result=None;self.target_lost=lost
        self.target_error='Nao consegui revalidar o alvo. Ele pode ter mudado, expirado ou ficado fora do limite da consulta. Consulte novamente antes de marcar.' if lost else ''
    def poll(self):
        if self.closed:return
        if self.pending is not None:
            if not self.pending.done():return
            future=self.pending;self.pending=None
            try:
                result=future.result()
                if not self.enabled or result['generation']!=self.generation:return
                observed=result.get('context',self.current)
                if 'context' in result:self.current=observed
                if 'target' in result:
                    self.target_result=result['target']
                    if self.target and result['target'] is None:self.clear_target(lost=True)
                self.last_error=observed.get('error','')
                if not observed.get('ok'):
                    if self.target:self.clear_target(lost=True)
                    return
                for item in observed.get('controls',[]) if 'context' in result else []:
                    text=item.get('name','')
                    if any(word in text.casefold() for word in ('test failed','tests failed','traceback','erro de compilacao','build failed')):
                        self.initiative.offer(observed['app']+':failure',
                            'A interface do aplicativo acompanhado mostra uma indicacao de falha. Quer que eu consulte os detalhes?',
                            {'app':observed['app'],'handle':observed['handle'],'process_id':observed['process_id'],
                             'control_id':item['control_id'],'observed_text':text})
                        break
            except Exception as error:
                self.current={};self.target_result=None;self.last_error=type(error).__name__;self.record('observation_failed',kind=type(error).__name__)
                if self.target:self.clear_target(lost=True)
        if not self.enabled:return
        now=self.clock();refresh=now-self.at>=4;track=bool(self.target and now-self.target_at>=.5)
        if not refresh and not track:return
        if refresh:self.at=now
        if track:self.target_at=now
        generation=self.generation;allowed=self.permissions();target=self.target
        def authorized():return not self.closed and self.enabled and generation==self.generation
        def work():
            if not authorized():return {'generation':generation,'context':{'ok':False,'cancelled':True}}
            result={'generation':generation}
            if refresh:result['context']=perception.inspect_foreground(allowed,authorized=authorized)
            if target and result.get('context',{'ok':True}).get('ok') and authorized():
                try:result['target']=perception.target_rect(target,allowed,authorized=authorized)
                except (ValueError,OSError):result['target']=None
            return result
        self.pending=self.pool.submit(work)
    def context(self):
        if not self.enabled:return {'ok':False,'privacy':True,'error':'Observacao esta pausada.'}
        if not self.current.get('ok'):return {'ok':False,'error':self.last_error or 'Consultando o aplicativo autorizado; aguarde os dados reais.'}
        if time.time()-self.current.get('observed_at',0)>12:
            if self.target:self.clear_target(lost=True)
            return {'ok':False,'error':'Observacao antiga; aguardando nova consulta.'}
        # A fresh foreground check avoids displaying cached text from another app.
        state=perception.foreground()
        if not state.get('ok') or state.get('handle')!=self.current.get('handle') or state.get('process_id')!=self.current.get('process_id'):
            self.current={};self.target_result=None
            if self.target:self.clear_target(lost=True)
            return {'ok':False,'error':'A janela mudou. Aguarde uma nova observacao.'}
        return dict(self.current)
    def permissions(self):return {'*'} if self.automatic else set(self.allowed)
    def highlight(self,control_id=None,query=None):
        current=self.context()
        if not current.get('ok'):raise ValueError(current.get('error'))
        if not control_id and isinstance(query,str) and query.strip():
            matches=matching_controls(current.get('controls',[]),query)
            if len(matches)!=1:
                names=', '.join(str(item.get('name',''))[:60] for item in matches[:4])
                raise ValueError('Encontrei mais de um alvo: '+names+'. Pergunte qual deles devo marcar.' if matches else
                    'Esse alvo nao apareceu nos elementos acessiveis da janela atual. Consulte a tela novamente; nao afirme que marcou nem invente coordenadas.')
            control_id=matches[0]['control_id']
        if not any(item.get('control_id')==control_id for item in current.get('controls',[])):raise ValueError('Consulte um controle real da observacao atual.')
        self.generation+=1;self.target=control_id;self.target_result=None;self.target_lost=False;self.target_error='';self.target_at=-float('inf')
    def forget(self,app):
        self.store.forget(app);self.allowed.discard(app);self.privacy();self.record('revoked',app=app)
    def close(self):
        if self.closed:return
        self.privacy(persist=False);self.closed=True
        if self.pending:self.pending.cancel()
