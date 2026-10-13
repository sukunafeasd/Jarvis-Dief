"""Monitoramento opt-in de arquivos, limitado e silencioso ate haver mudanca."""
import threading
from core import resource_store as store
from core.file_library import safe_path,fingerprint

LOCK=threading.RLock()


def run(p):
    with LOCK:
        action=p.get('action','list')
        if action=='list':return store.search('watch',limit=100)
        if action=='create':
            path=safe_path(p.get('path'))
            if not path.is_file():raise ValueError('Escolha um arquivo existente para observar.')
            if store.search('watch',limit=1)['total']>=20:raise ValueError('Limite de vinte monitores locais.')
            item=store.put('watch',path.name,'',{'path':str(path),'sha256':fingerprint(path),'enabled':True,'missing':False})
            return {'item':item,'note':'Verifica enquanto o Jarvis esta aberto; nao monitora com o aplicativo fechado.'}
        if action in ('enable','disable','delete'):
            item=store.read('watch',p.get('id'))
            if action=='delete':return store.delete('watch',item['id'])
            meta=item['metadata'];meta['enabled']=action=='enable'
            return {'item':store.put('watch',item['title'],item['body'],meta,item['id'])}
        if action=='check':return {'changes':poll()}
        raise ValueError('Acao de monitoramento invalida.')


def poll():
    with LOCK:
        changes=[]
        for item in store.search('watch',limit=20,full=True)['items']:
            meta=item['metadata']
            if not meta.get('enabled'):continue
            path=safe_path(meta['path']);missing=not path.is_file()
            digest=None if missing else fingerprint(path)
            if digest!=meta.get('sha256') or missing!=meta.get('missing'):
                changes.append({'title':item['title'],'path':str(path),'missing':missing,'content_read':False})
                store.put('watch',item['title'],'',{**meta,'sha256':digest,'missing':missing},item['id'])
        return changes
