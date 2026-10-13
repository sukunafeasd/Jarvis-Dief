"""Downloads solicitados explicitamente: HTTPS, limite de tamanho, sem executar arquivos."""
import ipaddress
import socket
import time
from urllib.parse import urlsplit
from pathlib import Path
import requests
from core import document_reader,resource_store
from core.resource_jobs import request


def validate_url(value):
    url=urlsplit(str(value or ''))
    if url.scheme!='https' or not url.hostname or url.username or url.password or url.fragment or url.port not in (None,443):
        raise ValueError('Use URL HTTPS final, sem senha ou porta personalizada.')
    addresses=socket.getaddrinfo(url.hostname,443,type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(record[4][0]).is_global for record in addresses):
        raise ValueError('Download exige endereco publico; nao acesso servidor interno por esta ferramenta.')
    return value


def execute(url,name):
    validate_url(url)
    with requests.get(url,stream=True,timeout=(5,20),allow_redirects=False) as response:
        if 300<=response.status_code<400:raise ValueError('Use a URL final do arquivo; redirecionamento nao seguido automaticamente.')
        response.raise_for_status()
        size=int(response.headers.get('Content-Length','0'))
        if size>document_reader.MAX_BYTES:raise ValueError('Arquivo acima do limite de 25 MB.')
        blocks=[];total=0;started=time.monotonic()
        for block in response.iter_content(chunk_size=65536):
            if not block:continue
            total+=len(block)
            if time.monotonic()-started>60:raise ValueError('Tempo total de download esgotado; arquivo nao foi salvo.')
            if total>document_reader.MAX_BYTES:raise ValueError('Arquivo ultrapassou o limite durante a transferencia.')
            blocks.append(block)
        if size and response.headers.get('Content-Encoding','identity')=='identity' and total!=size:raise ValueError('Transferencia incompleta; arquivo nao foi salvo.')
        path=document_reader.save_download(name,b''.join(blocks))
    source=urlsplit(url)
    record=resource_store.put('note','Download: '+path.name,'',{'download_path':str(path),'bytes':total,'source':source.scheme+'://'+source.netloc+source.path})
    return {'ok':True,'downloaded':True,'path':str(path),'bytes':total,'record_id':record['id'],'executed':False,'note':'Arquivo salvo, nunca executado. Use o leitor de documentos para formatos suportados.'}


def run(p):
    action=p.get('action','status')
    if action=='status':return {'available':True,'max_bytes':document_reader.MAX_BYTES,'executes_files':False,'https_only':True}
    if action=='list':
        page=resource_store.search('note','Download:',p.get('offset',0),p.get('limit',20))
        return {'items':[item for item in page['items'] if item['metadata'].get('download_path')],'next_offset':page['next_offset'],'data_is_untrusted':True}
    if action!='download':raise ValueError('Acao de download invalida.')
    url=validate_url(p.get('url',''));name=str(p.get('filename') or Path(urlsplit(url).path).name or 'arquivo')
    return request('Baixar arquivo solicitado',urlsplit(url).hostname+' · '+name,lambda:execute(url,name))
