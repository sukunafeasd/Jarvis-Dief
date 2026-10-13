"""Microsoft Graph com MSAL, login interativo e cache protegido por usuario."""
import re
import threading
from urllib.parse import quote
import requests
from core import integration_tokens as tokens
LOCK=threading.RLock()
SCOPES=['User.Read','Mail.Read','Calendars.Read','Contacts.Read','Mail.Send']


def configuration():
    from memory.config_manager import get_plugin_config
    return get_plugin_config('outlook_service')


def client():
    import msal
    config=configuration();client_id=str(config.get('client_id','')).strip()
    if not re.fullmatch(r'[a-fA-F0-9-]{36}',client_id):raise ValueError('Informe o identificador do aplicativo publico Microsoft nas Conexoes.')
    cache=msal.SerializableTokenCache()
    saved=tokens.read('outlook_service')
    if saved.get('cache') and saved.get('client_id')==client_id:cache.deserialize(saved['cache'])
    app=msal.PublicClientApplication(client_id,authority='https://login.microsoftonline.com/common',token_cache=cache)
    return app,cache


def persist(cache,account):tokens.write('outlook_service',{'cache':cache.serialize(),'account':account,'client_id':configuration().get('client_id','').strip()})


def connect(values=None):
    with LOCK:
        app,cache=client()
        result=app.acquire_token_interactive(scopes=SCOPES,timeout=180,prompt='select_account')
        if 'access_token' not in result:return False,'A Microsoft nao confirmou a autorizacao. A conexao anterior foi preservada.'
        profile=graph('/me?$select=displayName,mail,userPrincipalName',result['access_token'])
        account=profile.get('mail') or profile.get('userPrincipalName','')
        expected=configuration().get('expected_email','').strip()
        if expected and expected.casefold()!=account.casefold():return False,'Conta autorizada diferente da solicitada; conexao anterior preservada.'
        persist(cache,account);return True,'Conta Microsoft conectada: '+account


def access_token():
    with LOCK:
        app,cache=client();expected=configuration().get('expected_email','').strip()
        accounts=app.get_accounts(username=expected) if expected else app.get_accounts()
        if len(accounts)!=1:raise ValueError('Reconecte e escolha uma unica conta Microsoft.')
        result=app.acquire_token_silent(SCOPES,account=accounts[0])
        if not result or 'access_token' not in result:raise ValueError('Autorize a conta Microsoft nas Conexoes.')
        persist(cache,accounts[0].get('username',''));return result['access_token']


def graph(path,token=None):
    if not path.startswith('/'):raise ValueError('Caminho Microsoft invalido.')
    response=requests.get('https://graph.microsoft.com/v1.0'+path,headers={'Authorization':'Bearer '+(token or access_token()),'Prefer':'outlook.body-content-type="text"'},timeout=(5,20),allow_redirects=False)
    response.raise_for_status()
    if len(response.content)>2*1024*1024:raise ValueError('Resposta Microsoft acima do limite.')
    return response.json()


def status():
    try:
        saved=tokens.read('outlook_service')
        configured=configuration()
        matches=saved.get('client_id')==configured.get('client_id','').strip()
        expected=configured.get('expected_email','').strip()
        matches=matches and (not expected or expected.casefold()==saved.get('account','').casefold())
        return {'connected':bool(saved.get('cache') and matches),'configured':bool(configured.get('client_id')),'account':saved.get('account','') if matches else '', 'verified':False}
    except Exception:return {'connected':False,'configured':False,'verified':False}


def verify():graph('/me?$select=id');return True,'Conexao Microsoft confirmada.'


def run(p):
    action=p.get('action','status')
    if action=='status':return status()
    if action=='send':
        from core.gmail_compose import raw_message
        from core.resource_jobs import request
        raw_message(p)
        prepared=tokens.read('outlook_service')
        account=prepared.get('account','');client_id=prepared.get('client_id','')
        if not account or not status()['connected']:raise ValueError('Conecte a conta Microsoft correta antes de preparar o envio.')
        body={'message':{'subject':p['subject'],'body':{'contentType':'Text','content':p['text']},'toRecipients':[{'emailAddress':{'address':p['to']}}]},'saveToSentItems':True}
        def send():
            current=tokens.read('outlook_service')
            if current.get('account')!=account or current.get('client_id')!=client_id:raise ValueError('Conta Microsoft mudou; revise o envio.')
            token=access_token()
            response=requests.post('https://graph.microsoft.com/v1.0/me/sendMail',headers={'Authorization':'Bearer '+token},json=body,timeout=(5,20),allow_redirects=False)
            response.raise_for_status()
            accepted=response.status_code==202
            return {'ok':accepted,'provider_accepted':accepted,'delivery_confirmed':False,'uncertain':not accepted,'note':'Microsoft aceitou a solicitacao; isso nao confirma processamento final nem entrega. Nao repetir sem conferir enviados.'}
        return request('Enviar email pela Microsoft',account+' → '+p['to']+'\n'+p['subject'],send)
    domain=p.get('domain','mail')
    if domain not in ('mail','calendar','contacts'):raise ValueError('Dominio Microsoft invalido.')
    if action=='list':
        limit=max(1,min(30,int(p.get('limit',20))))
        paths={'mail':'/me/messages?$select=id,subject,from,receivedDateTime,isRead&$orderby=receivedDateTime desc',
               'calendar':'/me/events?$select=id,subject,start,end,location',
               'contacts':'/me/contacts?$select=id,displayName,emailAddresses,mobilePhone'}
        path=paths[domain]+'&$top='+str(limit)
        if p.get('page_url'):
            from urllib.parse import urlsplit
            url=urlsplit(p['page_url'])
            if url.scheme!='https' or url.netloc!='graph.microsoft.com' or not url.path.startswith('/v1.0/me/'):raise ValueError('Pagina nao pertence ao Microsoft Graph autorizado.')
            path=url.path.removeprefix('/v1.0')+('?' + url.query if url.query else '')
        result=graph(path)
        return {'items':result.get('value',[]),'next_page_url':result.get('@odata.nextLink'),'complete':not bool(result.get('@odata.nextLink')),'data_is_untrusted':True}
    if action=='read':
        identifier=str(p.get('id',''))
        if not identifier or len(identifier)>2000:raise ValueError('Use ID real obtido na lista.')
        name={'mail':'messages','calendar':'events','contacts':'contacts'}[domain]
        result=graph('/me/'+name+'/'+quote(identifier,safe=''))
        if domain=='mail':
            body=result.get('body',{});text=body.get('content','')
            offset=max(0,int(p.get('offset',0)));end=min(len(text),offset+12000)
            result['body']={**body,'content':text[offset:end]};result['next_offset']=end if end<len(text) else None
        return {'item':result,'data_is_untrusted':True}
    raise ValueError('Acao Microsoft invalida.')
