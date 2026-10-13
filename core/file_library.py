"""Busca limitada e indexacao explicita; nenhum disco e varrido automaticamente."""
import hashlib
import os
import shutil
import time
from pathlib import Path
from core import document_reader, resource_store as store
from core.resource_jobs import request

MAX_FILES=2000
SKIP={'.git','.venv','node_modules','config','.ssh','.aws','__pycache__'}


def safe_path(value):
    if not str(value or '').strip():raise ValueError('Informe um caminho explicito.')
    path=Path(value).expanduser().resolve()
    root=Path(__file__).resolve().parents[1]
    if path.is_relative_to(root/'config') or any(part.casefold() in SKIP for part in path.parts):
        raise ValueError('Pasta privada, de credenciais ou de dependencias nao permitida.')
    if path.name.casefold().startswith('.env') or path.name.casefold() in ('api_keys.json','credentials.json','google_credentials.json') or path.suffix.casefold() in ('.pem','.key','.pfx','.p12'):
        raise ValueError('Arquivo de credenciais nao permitido.')
    return path


def files(folder, state=None):
    root=safe_path(folder)
    if not root.is_dir() or root.parent==root:
        raise ValueError('Escolha uma pasta existente, nao a raiz do disco.')
    count=0;start=time.monotonic()
    for current, directories, names in os.walk(root,followlinks=False):
        directories[:]=sorted(name for name in directories if name.casefold() not in SKIP
            and not Path(current,name).is_symlink() and not Path(current,name).is_junction()
            and Path(current,name).resolve().is_relative_to(root))
        for name in sorted(names):
            path=Path(current,name)
            if path.is_symlink() or not path.resolve().is_relative_to(root):continue
            count+=1
            if count>MAX_FILES or time.monotonic()-start>15:
                if state is not None:state['complete']=False
                return
            try:safe_path(path)
            except ValueError:continue
            yield path


def fingerprint(path):
    if path.stat().st_size>document_reader.MAX_BYTES:raise ValueError('Arquivo acima do limite de 25 MB.')
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(65536),b''):digest.update(block)
    return digest.hexdigest()


def run(p,player=None):
    action=p.get('action','search')
    if action=='status':return {'available':True,'indexed':store.search('knowledge',limit=1)['total'],'scan_limit':MAX_FILES}
    if action=='search':
        query=store.normalize(p.get('query',''));items=[];examined=0;scan={'complete':True}
        for path in files(p.get('folder'),scan):
            examined+=1
            hit=query in store.normalize(path.name);snippet=''
            if not hit and p.get('content') and path.suffix.casefold() in ('.txt','.md','.csv','.tsv') and path.stat().st_size<=1024*1024:
                text,partial=document_reader.extract(path)
                hit=query in store.normalize(text)
                if hit:snippet=text[:500]
            if hit:items.append({'path':str(path),'title':path.name,'bytes':path.stat().st_size,'modified':path.stat().st_mtime,'snippet':snippet})
        offset=max(0,int(p.get('offset',0)));limit=max(1,min(50,int(p.get('limit',20))))
        return {'items':items[offset:offset+limit],'total_found':len(items),'next_offset':offset+limit if offset+limit<len(items) else None,'scan_complete':scan['complete'],'examined':examined,'data_is_untrusted':True}
    if action=='duplicates':
        sizes={};examined=0;scan={'complete':True}
        for path in files(p.get('folder'),scan):
            examined+=1
            size=path.stat().st_size
            if 0<size<=document_reader.MAX_BYTES:sizes.setdefault(size,[]).append(path)
        hashes={};budget=0
        for size,paths in sizes.items():
            if len(paths)<2:continue
            for path in paths:
                budget+=size
                if budget>100*1024*1024:return {'groups':[paths for paths in hashes.values() if len(paths)>1],'complete':False,'note':'Limite de leitura atingido; nenhum arquivo removido.'}
                hashes.setdefault(fingerprint(path),[]).append(str(path))
        return {'groups':[paths for paths in hashes.values() if len(paths)>1],'complete':scan['complete'],'deleted':False}
    if action=='index':
        path=safe_path(p.get('path'))
        result=document_reader.read({'path':str(path),'max_chars':20000})
        record=store.put('knowledge',path.name,result['text'],{'path':str(path),'sha256':fingerprint(path),'complete':result['complete'],'indexed_chars':len(result['text'])})
        return {'item':record,'indexed':True,'complete':result['complete'],'note':'Somente este trecho foi indexado; nao e o documento completo quando complete=false.'}
    if action=='recall':
        result=store.search('knowledge',p.get('query',''),p.get('offset',0),p.get('limit',20),full=True)
        for item in result['items']:
            source=Path(item['metadata']['path'])
            item['source_missing']=not source.is_file()
            item['source_changed']=source.is_file() and fingerprint(source)!=item['metadata']['sha256']
            item['excerpt']=item.pop('body')[:3000]
        return result
    if action=='move':
        source=safe_path(p.get('path'));destination=safe_path(p.get('destination'))
        if not source.is_file() or destination.exists() or not destination.parent.is_dir():
            raise ValueError('Mover exige arquivo real, destino inexistente e pasta de destino existente.')
        initial=fingerprint(source)
        def move():
            if not source.is_file() or fingerprint(source)!=initial or destination.exists():raise ValueError('O arquivo ou destino mudou; nao movi.')
            shutil.move(str(source),str(destination))
            if source.exists() or not destination.is_file() or fingerprint(destination)!=initial:
                return {'ok':False,'uncertain':True}
            receipt=store.put('note','Movimentacao de arquivo','',{'undo_source':str(destination),'undo_destination':str(source),'sha256':initial})
            return {'ok':True,'path':str(destination),'undo_id':receipt['id']}
        return request('Mover arquivo',source.name+' → '+str(destination),move)
    if action=='undo_move':
        receipt=store.read('note',p.get('id'))['metadata']
        source=safe_path(receipt.get('undo_source'));destination=safe_path(receipt.get('undo_destination'))
        if not source.is_file() or fingerprint(source)!=receipt.get('sha256') or destination.exists():raise ValueError('Estado mudou; nao posso desfazer automaticamente.')
        return run({'action':'move','path':str(source),'destination':str(destination)})
    raise ValueError('Acao de arquivos invalida.')
