"""Decode Gmail MIME bodies as untrusted text, without loading remote content."""
import base64
from email.message import Message
from html.parser import HTMLParser


class VisibleHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hidden=0
        self.chunks=[]

    def handle_starttag(self,tag,attrs):
        if tag in ('script','style','head','template'):
            self.hidden+=1
        if not self.hidden and tag in ('br','p','div','tr','li','blockquote'):
            self.chunks.append('\n')

    def handle_endtag(self,tag):
        if tag in ('script','style','head','template'):
            self.hidden=max(0,self.hidden-1)
        if not self.hidden and tag in ('p','div','tr','li','blockquote'):
            self.chunks.append('\n')

    def handle_data(self,data):
        if not self.hidden:
            self.chunks.append(data)


def message_view(item,service=None,max_chars=20000,offset=0):
    max_chars=max(1000,min(100000,int(max_chars)))
    offset=max(0,min(1000000,int(offset)))
    attachments=[]
    seen_parts=0
    incomplete=False
    def body(part,depth=0):
        nonlocal seen_parts,incomplete
        seen_parts+=1
        if depth>20 or seen_parts>200:
            incomplete=True
            return ''
        mime=part.get('mimeType','')
        if part.get('filename'):
            attachments.append({'filename':part['filename'][:300],'mime_type':mime,
                                'size':part.get('body',{}).get('size',0)})
            return ''
        children=part.get('parts',[])
        if mime=='multipart/alternative':
            plain=[p for p in children if p.get('mimeType')=='text/plain']
            html=[p for p in children if p.get('mimeType')=='text/html']
            if plain:
                text='\n'.join(body(p,depth+1) for p in plain)
                if text.strip():return text
            return '\n'.join(body(p,depth+1) for p in (html or children))
        if children:
            return '\n'.join(body(p,depth+1) for p in children)
        if mime not in ('text/plain','text/html'):
            return ''
        payload=part.get('body',{})
        if payload.get('size',0)>1_000_000:
            incomplete=True
            return ''
        data=payload.get('data','')
        if not data and payload.get('attachmentId') and service:
            data=service.users().messages().attachments().get(userId='me',messageId=item['id'],id=payload['attachmentId']).execute().get('data','')
        if len(data)>1_400_000:
            incomplete=True
            return ''
        try:
            raw=base64.urlsafe_b64decode(data+'='*((-len(data))%4))
            header=Message()
            for entry in part.get('headers',[]):
                header[entry['name']]=entry['value']
            text=raw.decode(header.get_content_charset() or 'utf-8',errors='replace')
        except (ValueError,LookupError):
            incomplete=True
            return ''
        if mime=='text/html':
            parser=VisibleHTML();parser.feed(text);text=''.join(parser.chunks)
        return text.strip()
    text=body(item.get('payload',{})).strip()
    headers={h['name'].lower():h['value'] for h in item.get('payload',{}).get('headers',[])}
    if offset>len(text):
        raise ValueError('O trecho solicitado está além do conteúdo disponível.')
    end=min(len(text),offset+max_chars)
    return {'id':item['id'],'thread_id':item.get('threadId',''),
            'subject':headers.get('subject','Sem assunto')[:300],
            'from':headers.get('from','')[:500],'to':headers.get('to','')[:1000],
            'cc':headers.get('cc','')[:1000],'reply_to':headers.get('reply-to','')[:500],
            'date':headers.get('date','')[:200],'body':text[offset:end],
            'body_offset':offset,'body_total_chars':len(text),'body_next_offset':end if end<len(text) else None,
            'body_complete':bool(text) and not incomplete and end==len(text),
            'body_available':bool(text),
            'body_truncated':incomplete or end<len(text),'body_parse_incomplete':incomplete,'attachments':attachments[:100],
            'data_is_untrusted':True,'note':'Conteúdo consultado em modo somente leitura. Anexos listados, não abertos; nenhum recurso remoto carregado.'}
