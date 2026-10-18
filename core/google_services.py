"""Agenda e Drive com tokens isolados do Gmail e APIs oficiais."""
import json
import re
import threading
from datetime import datetime,timezone
from core import integration_tokens as tokens

PROVIDERS={
 'google_calendar':('calendar','v3',['https://www.googleapis.com/auth/calendar.events',
    'https://www.googleapis.com/auth/calendar.calendarlist.readonly']),
 'google_drive':('drive','v3',['https://www.googleapis.com/auth/drive.readonly']),
 'gmail_compose':('gmail','v1',['https://www.googleapis.com/auth/gmail.compose'])}
LOCKS={name:threading.RLock() for name in PROVIDERS}


class GoogleConnectionProblem(ValueError):
    def __init__(self,message,state='error'):
        super().__init__(message);self.state=state


def error_details(error):
    if isinstance(error,GoogleConnectionProblem):return {'state':error.state,'message':str(error)}
    code=getattr(getattr(error,'resp',None),'status',None)
    try:
        payload=json.loads(getattr(error,'content',b'{}')).get('error',{})
        reasons=[item.get('reason','') for item in payload.get('errors',[])+payload.get('details',[])]
        disabled=any(reason in ('accessNotConfigured','SERVICE_DISABLED') for reason in reasons)
    except (ValueError,TypeError,AttributeError):disabled=False
    if disabled:return {'state':'error','message':'A conta autorizou o Jarvis, mas a API deste servico esta desativada no Google Cloud. Ative a API no projeto da credencial e teste novamente; repetir o login nao resolve essa causa.'}
    if code==401:return {'state':'auth_required','message':'A autorizacao Google expirou ou foi recusada. Use Reconectar e escolha a conta desejada.'}
    if code==403:return {'state':'auth_required','message':'Google recusou este acesso (403). Confira a permissao solicitada, a conta de teste e o projeto OAuth; nao e uma confirmacao interna do Jarvis.'}
    if isinstance(error,ValueError):return {'state':'auth_required','message':str(error)}
    return {'state':'error','message':'Nao consegui verificar o Google ('+type(error).__name__+'). Confira a internet e a configuracao do servico.'}


def settings(name):
    from memory.config_manager import get_plugin_config
    return get_plugin_config(name)


def status(name):
    try:
        value=tokens.read(name)
        return {'connected':bool(value.get('refresh_token') or value.get('token')),
            'account':value.get('jarvis_account_email',''),'configured':credential_path(name).exists(),
            'authorization_pending':bool(tokens.read(name+'_pending'))}
    except Exception:return {'connected':False,'configured':False}


def credential_path(name):
    from pathlib import Path
    from core.gmail_connection import CREDENTIALS
    value=settings(name).get('credentials_path','').strip()
    return Path(value).expanduser() if value else CREDENTIALS


def client_configuration(path):
    value=json.loads(path.read_text(encoding='utf-8')).get('installed',{})
    if not re.fullmatch(r'[A-Za-z0-9_-]+\.apps\.googleusercontent\.com',value.get('client_id','')) or not value.get('client_secret'):
        raise ValueError('Use um JSON OAuth do Google para aplicativo de computador, não uma chave de IA.')
    return {'installed':{'client_id':value['client_id'],'client_secret':value['client_secret'],
        'auth_uri':'https://accounts.google.com/o/oauth2/auth','token_uri':'https://oauth2.googleapis.com/token',
        'redirect_uris':['http://localhost']}}


def build(name,credentials,api=None,version=None):
    import httplib2
    from google_auth_httplib2 import AuthorizedHttp
    from googleapiclient.discovery import build as google_build
    spec=PROVIDERS[name]
    return google_build(api or spec[0],version or spec[1],
        http=AuthorizedHttp(credentials,http=httplib2.Http(timeout=15)),cache_discovery=False)


def service(name):
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    value=tokens.read(name)
    if not value:raise ValueError('Conecte esta conta nas configurações do Jarvis.')
    expected=settings(name).get('expected_email','').strip()
    if expected and value.get('jarvis_account_email','').casefold()!=expected.casefold():
        raise ValueError('A conta salva não é a conta solicitada. Autorize a conta correta nas configurações.')
    credentials=Credentials.from_authorized_user_info(value)
    if not credentials.valid:
        if not credentials.refresh_token:raise ValueError('Autorize a conta novamente.')
        credentials.refresh(Request())
        fresh=json.loads(credentials.to_json());fresh['jarvis_account_email']=value.get('jarvis_account_email','')
        tokens.write(name,fresh)
    return build(name,credentials)


def check_api(name,api):
    if name=='google_calendar':api.calendarList().list(maxResults=1).execute()
    elif name=='gmail_compose':api.users().drafts().list(userId='me',maxResults=1).execute()
    else:api.about().get(fields='user(emailAddress)').execute()


def connect(name):
    from google_auth_oauthlib.flow import InstalledAppFlow
    path=credential_path(name)
    if not path.exists():return False,'Importe a credencial Google no Gmail ou informe o caminho do JSON OAuth deste serviço.'
    with LOCKS[name]:
        scopes=PROVIDERS[name][2]+['https://www.googleapis.com/auth/userinfo.email','openid']
        flow=InstalledAppFlow.from_client_config(client_configuration(path),scopes)
        expected=settings(name).get('expected_email','').strip()
        credentials=flow.run_local_server(port=0,timeout_seconds=180,open_browser=True,
            prompt='consent select_account',**({'login_hint':expected} if expected else {}),
            authorization_prompt_message='Autorize a conta Google na janela do navegador.',
            success_message='Autorização recebida pelo Dief Jarvis. Pode fechar esta janela.')
        email=build(name,credentials,'oauth2','v2').userinfo().get().execute()['email']
        if expected and email.casefold()!=expected.casefold():return False,'A conta autorizada não é a conta solicitada. A conexão anterior foi preservada.'
        # Verify API access before persisting the new account.
        api=build(name,credentials)
        value=json.loads(credentials.to_json());value['jarvis_account_email']=email
        try:check_api(name,api)
        except Exception as error:
            # Keep authorization separate from verified API access.
            tokens.write(name+'_pending',value)
            details=error_details(error)
            raise GoogleConnectionProblem(details['message'],details['state']) from error
        tokens.write(name,value);tokens.remove(name+'_pending')
        return True,'Conta conectada: '+email


def verify(name):
    with LOCKS[name]:
        candidate=tokens.read(name+'_pending')
        if candidate:
            from google.oauth2.credentials import Credentials
            expected=settings(name).get('expected_email','').strip()
            if expected and candidate.get('jarvis_account_email','').casefold()!=expected.casefold():
                raise GoogleConnectionProblem('A autorizacao pendente pertence a outra conta. Reconecte com a conta desejada.','auth_required')
            credentials=Credentials.from_authorized_user_info(candidate)
            if not credentials.valid:
                from google.auth.transport.requests import Request
                credentials.refresh(Request())
            try:check_api(name,build(name,credentials))
            except Exception as error:
                details=error_details(error);raise GoogleConnectionProblem(details['message'],details['state']) from error
            value=json.loads(credentials.to_json());value['jarvis_account_email']=candidate['jarvis_account_email']
            tokens.write(name,value);tokens.remove(name+'_pending')
        api=service(name)
        check_api(name,api)
        return True,'Conexão confirmada com o Google: '+status(name).get('account','')


def identifier(value):
    if not re.fullmatch(r'[A-Za-z0-9_@.\-]{1,1024}',str(value or '')):raise ValueError('Informe um identificador real obtido na consulta anterior.')
    return value


def calendar(parameters):
    action=parameters.get('action','list');api=service('google_calendar')
    calendar_id=identifier(parameters.get('calendar_id','primary'))
    if action=='calendars':return {'calendars':api.calendarList().list(maxResults=100,pageToken=parameters.get('page_token','')).execute()}
    events=api.events()
    if action=='list':
        args={'calendarId':calendar_id,'maxResults':max(1,min(100,int(parameters.get('limit',20)))),
              'singleEvents':True,'orderBy':'startTime','timeMin':parameters.get('date_from') or datetime.now(timezone.utc).isoformat()}
        include_birthdays = parameters.get('include_birthdays') is True
        if not include_birthdays:
            args['eventTypes'] = ['default','focusTime','fromGmail','outOfOffice','workingLocation']
        for key,dest in (('date_to','timeMax'),('query','q'),('page_token','pageToken')):
            if parameters.get(key):args[dest]=parameters[key]
        for key in ('timeMin','timeMax'):
            if key in args and datetime.fromisoformat(args[key].replace('Z','+00:00')).tzinfo is None:
                raise ValueError('Informe um horário ISO com fuso, por exemplo -03:00.')
        result=events.list(**args).execute();items=result.get('items',[])
        if not include_birthdays:
            items=[item for item in items if item.get('eventType') != 'birthday']
        return {'items':items,'next_page_token':result.get('nextPageToken',''),'complete':not bool(result.get('nextPageToken'))}
    if action=='read':return {'event':events.get(calendarId=calendar_id,eventId=identifier(parameters.get('event_id'))).execute()}
    if action=='delete':
        if not parameters.get('confirmed'):raise ValueError('Excluir exige um pedido explícito do usuário e confirmed=true.')
        events.delete(calendarId=calendar_id,eventId=identifier(parameters.get('event_id')),sendUpdates='none').execute()
        return {'deleted':True}
    if action not in ('create','update'):raise ValueError('Ação de agenda inválida.')
    body={}
    for source,target in (('title','summary'),('description','description'),('location','location')):
        if source in parameters:body[target]=str(parameters[source])[:4000]
    for source in ('start','end'):
        if parameters.get(source):
            moment=datetime.fromisoformat(parameters[source].replace('Z','+00:00'))
            if moment.tzinfo is None:raise ValueError('Data de agenda precisa de fuso horário.')
            body[source]={'dateTime':moment.isoformat()}
    if action=='create' and (not body.get('summary') or not all(k in body for k in ('start','end'))):raise ValueError('Informe título, início e fim com fuso horário.')
    if action=='update':
        event_id=identifier(parameters.get('event_id'))
        current=events.get(calendarId=calendar_id,eventId=event_id).execute()
        dates={key:body.get(key,current.get(key,{})) for key in ('start','end')}
    else:dates=body
    if all(dates.get(k,{}).get('dateTime') for k in ('start','end')):
        if datetime.fromisoformat(dates['end']['dateTime'].replace('Z','+00:00'))<=datetime.fromisoformat(dates['start']['dateTime'].replace('Z','+00:00')):
            raise ValueError('O fim deve ocorrer depois do início.')
    if not body:raise ValueError('Informe o campo que deseja alterar.')
    result=(events.insert(calendarId=calendar_id,body=body,sendUpdates='none') if action=='create'
        else events.patch(calendarId=calendar_id,eventId=event_id,body=body,sendUpdates='none')).execute()
    return {'event':result,'confirmed':True}


def drive(parameters):
    api=service('google_drive');action=parameters.get('action','list')
    if action=='list':
        query='trashed=false'
        if parameters.get('query'):
            text=str(parameters['query']).replace('\\','\\\\').replace("'","\\'")[:300]
            query+=" and name contains '"+text+"'"
        result=api.files().list(q=query,pageSize=max(1,min(100,int(parameters.get('limit',20)))),
            pageToken=parameters.get('page_token',''),fields='nextPageToken,files(id,name,mimeType,size,modifiedTime,webViewLink)',orderBy='modifiedTime desc').execute()
        return {'files':result.get('files',[]),'next_page_token':result.get('nextPageToken',''),'complete':not bool(result.get('nextPageToken'))}
    file_id=identifier(parameters.get('file_id'))
    info=api.files().get(fileId=file_id,fields='id,name,mimeType,size,modifiedTime,webViewLink,capabilities(canDownload)').execute()
    if action=='read':return {'file':info,'note':'Metadados apenas; use download para ler o conteúdo.'}
    if action!='download':raise ValueError('Ação de Drive inválida.')
    if not info.get('capabilities',{}).get('canDownload',True):raise ValueError('A conta não permite baixar este arquivo.')
    if int(info.get('size',0))>25*1024*1024:raise ValueError('Arquivo acima do limite de leitura de 25 MB.')
    from core.document_reader import save_download
    from googleapiclient.http import MediaIoBaseDownload
    import io
    mime=info['mimeType'];exports={'application/vnd.google-apps.document':('text/plain','.txt'),
        'application/vnd.google-apps.spreadsheet':('application/vnd.openxmlformats-officedocument.spreadsheetml.sheet','.xlsx'),
        'application/vnd.google-apps.presentation':('application/pdf','.pdf')}
    filename=info['name']
    if mime.startswith('application/vnd.google-apps.'):
        if mime not in exports:raise ValueError('Tipo Google não exportável por este leitor.')
        export,extension=exports[mime];filename+=extension;request=api.files().export_media(fileId=file_id,mimeType=export)
    else:request=api.files().get_media(fileId=file_id)
    output=io.BytesIO();downloader=MediaIoBaseDownload(output,request,chunksize=256*1024);done=False
    while not done:
        _,done=downloader.next_chunk(num_retries=0)
        if output.tell()>25*1024*1024:raise ValueError('Download ultrapassou o limite de 25 MB.')
    path=save_download(filename,output.getvalue())
    return {'file':info,'path':str(path),'downloaded':True,'note':'Arquivo não executado. Use documentos para ler o caminho retornado.'}
