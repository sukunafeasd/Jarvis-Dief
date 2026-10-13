"""Estados publicos de conexao. Credencial salva nao equivale a teste aprovado."""
import copy
import threading
import time

STATES={
 'connected':('Conectado','ok','Testar conexão'),
 'disconnected':('Não conectado','muted','Conectar'),
 'pending':('Verificação pendente','notice','Testar conexão'),
 'awaiting':('Aguardando autorização','notice','Verificar conexão'),
 'testing':('Verificando…','notice','Aguarde…'),
 'connecting':('Conectando…','notice','Aguarde…'),
 'error':('Falha no teste','error','Testar novamente'),
 'auth_required':('Autorização necessária','notice','Conectar'),
 'disabled':('Desativado','muted','Ativar plugin'),
 'broken':('Erro no plugin','error','Ver detalhes'),
 'available':('Disponível','ok','Testar controle'),
 'local':('Plugin ativo','ok','Configurar'),
 'unverified':('Não verificado','muted','Abrir no Windows'),
}


class ConnectionChecks:
    def __init__(self,clock=time.monotonic):
        self.clock=clock;self.lock=threading.RLock();self.records={};self.sequence=0

    def begin(self,provider,connecting=False):
        with self.lock:
            record=self.records.get(provider,{})
            if record.get('busy'):return None
            self.sequence+=1
            self.records[provider]={**record,'generation':self.sequence,'busy':True,
                'state':'connecting' if connecting else 'testing','message':'','at':self.clock()}
            return self.sequence

    def finish(self,provider,generation,state,message):
        with self.lock:
            record=self.records.get(provider,{})
            if record.get('generation')!=generation or not record.get('busy'):return False
            if state not in STATES:state='error'
            self.records[provider]={'generation':generation,'busy':False,'state':state,
                'message':str(message)[:500],'at':self.clock(),'checked':time.strftime('%H:%M:%S')}
            return True

    def get(self,provider):
        with self.lock:
            result=copy.deepcopy(self.records.get(provider,{}))
            if result and not result.get('busy') and self.clock()-result.get('at',0)>300:
                result['stale']=True
            return result

    def invalidate(self,provider):
        with self.lock:self.records.pop(provider,None)


def resolve(provider,local,checked=None,plugin=None):
    checked=checked or {};plugin=plugin or {}
    if plugin and not plugin.get('valid',False):return 'broken'
    if plugin and not plugin.get('enabled',False):return 'disabled'
    if checked.get('busy'):return checked['state']
    if provider=='ai':
        if checked.get('state')=='error':return 'error'
        return 'connected' if local.get('connected') else 'disconnected'
    if provider=='gmail':
        if checked.get('state') in ('error','auth_required'):return checked['state']
        if not local.get('connected'):return 'auth_required' if checked.get('state')=='auth_required' else 'disconnected'
        return checked.get('state','pending')
    if provider=='whatsapp':return checked.get('state','pending' if local.get('saved_session') else 'disconnected')
    if 'local_available' in local:
        return checked.get('state','available' if local['local_available'] else 'error')
    if provider=='desktop':return checked.get('state','available' if plugin.get('valid',True) else 'broken')
    if provider=='iphone':return 'unverified'
    if provider in ('google_calendar','google_drive','spotify_control','gmail_compose','home_automation','outlook_service','mcp_bridge','notion_service'):
        return checked.get('state','pending' if local.get('connected') or local.get('authorization_pending') else 'disconnected')
    if plugin.get('valid') and plugin.get('enabled'):return checked.get('state','local')
    return 'unverified'
