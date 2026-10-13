"""Autorizacao separada: nao amplia silenciosamente o Gmail somente leitura."""
import base64
import re
from email.message import EmailMessage
from core import google_services as google
from core.resource_jobs import request


def raw_message(p):
    recipient=str(p.get('to','')).strip()
    if not re.fullmatch(r'[^\s@<>;,]+@[^\s@<>;,]+\.[^\s@<>;,]+',recipient):raise ValueError('Informe um destinatario valido e unico.')
    subject=str(p.get('subject',''));text=str(p.get('text',''))
    if not subject or '\r' in subject or '\n' in subject or len(subject)>300 or not text or len(text)>100000:
        raise ValueError('Informe assunto curto e corpo de ate 100 mil caracteres.')
    message=EmailMessage();message['To']=recipient;message['Subject']=subject;message.set_content(text)
    return base64.urlsafe_b64encode(message.as_bytes()).decode('ascii')


def run(p):
    action=p.get('action','status')
    if action=='status':return {**google.status('gmail_compose'),'access':'Rascunhos e envio; autorizacao separada do leitor Gmail'}
    api=google.service('gmail_compose');drafts=api.users().drafts()
    if action=='list':
        result=drafts.list(userId='me',maxResults=max(1,min(30,int(p.get('limit',20)))),pageToken=p.get('page_token','')).execute()
        return {'drafts':result.get('drafts',[]),'next_page_token':result.get('nextPageToken','')}
    if action=='create':
        raw=raw_message(p)
        return request('Salvar rascunho no Gmail',p['to']+' · '+p['subject'],lambda:{'ok':True,'draft':drafts.create(userId='me',body={'message':{'raw':raw}}).execute(),'sent':False})
    if action=='read':
        identifier=google.identifier(p.get('draft_id'))
        draft=drafts.get(userId='me',id=identifier,format='full').execute()
        # Return metadata and MIME payload for explicit reading; never interpret it as instructions.
        return {'draft':draft,'data_is_untrusted':True,'sent':False}
    if action=='send':
        identifier=google.identifier(p.get('draft_id'))
        snapshot=drafts.get(userId='me',id=identifier,format='raw').execute()
        raw=snapshot.get('message',{}).get('raw')
        if not raw:raise ValueError('Nao confirmei o conteudo do rascunho.')
        from email import policy
        from email.parser import BytesParser
        mime=BytesParser(policy=policy.default).parsebytes(base64.urlsafe_b64decode(raw+'='*((-len(raw))%4)))
        summary='Para: '+str(mime.get('To',''))+'\nAssunto: '+str(mime.get('Subject',''))
        if not mime.get('To'):raise ValueError('Rascunho sem destinatario.')
        def send():
            current=google.service('gmail_compose').users().drafts().get(userId='me',id=identifier,format='raw').execute()
            if current.get('message',{}).get('raw')!=raw:raise ValueError('Rascunho mudou; revise antes de enviar.')
            result=google.service('gmail_compose').users().drafts().send(userId='me',body={'id':identifier}).execute()
            return {'ok':bool(result.get('id')),'message_id':result.get('id'),'provider_accepted':bool(result.get('id')),'delivery_confirmed':False,'note':'Aceito pelo Gmail nao prova entrega ao destinatario.'}
        return request('Enviar rascunho pelo Gmail',summary,send)
    raise ValueError('Acao de rascunhos invalida.')
