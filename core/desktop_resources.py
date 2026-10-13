"""Utilidades explicitas de desktop; sem coleta continua de clipboard ou capturas."""
import json
import os
import subprocess
from pathlib import Path
from urllib.parse import urlencode
from core.file_library import safe_path
from core.office_resources import write_new
from core.resource_jobs import request


def git(p):
    path=safe_path(p.get('folder'))
    if not path.is_dir() or not (path/'.git').exists():raise ValueError('Escolha a raiz de um repositorio Git real.')
    action=p.get('action','status')
    commands={'status':['status','--short'],'diff':['diff','--no-ext-diff','--no-textconv','--stat'],'history':['log','-10','--format=%h %ad %s','--date=short']}
    if action not in commands:raise ValueError('Este plugin Git consulta; nao publica nem executa hooks.')
    executable=__import__('shutil').which('git')
    if not executable:raise ValueError('Git nao instalado.')
    environment={**os.environ,'GIT_TERMINAL_PROMPT':'0','GIT_CONFIG_NOSYSTEM':'1'}
    result=subprocess.run([executable,'--no-pager',*commands[action]],cwd=path,env=environment,capture_output=True,timeout=15,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    return {'ok':result.returncode==0,'exit_code':result.returncode,'output':result.stdout.decode('utf-8',errors='replace')[:12000],'data_is_untrusted':True,'published':False}


def run(p):
    action=p.get('action','status');domain=p.get('domain','clipboard')
    if domain=='downloads':
        from core.resource_downloads import run as downloads
        return downloads(p)
    if domain=='git':return git(p)
    if domain=='clipboard':
        import pyperclip
        if action=='read':
            text=pyperclip.paste()
            return {'text':text[:12000],'complete':len(text)<=12000,'data_is_untrusted':True,'monitoring':False}
        if action=='write':
            text=str(p.get('text',''))
            if not text or len(text)>12000:raise ValueError('Texto vazio ou longo demais.')
            def copy():
                pyperclip.copy(text)
                return {'ok':pyperclip.paste()==text,'verified':pyperclip.paste()==text}
            return request('Substituir area de transferencia','Copiar texto solicitado; nao coleta historico.',copy)
        if action=='status':return {'available':True,'monitoring':False}
    if domain=='notes':
        folder=safe_path(p.get('folder'))
        if not folder.is_dir():raise ValueError('Configure ou indique a pasta do seu cofre de notas.')
        if action=='list':
            from core.file_library import run as search
            result=search({'action':'search','folder':str(folder),'query':p.get('query',''),'limit':p.get('limit',20),'offset':p.get('offset',0)})
            result['items']=[item for item in result['items'] if Path(item['path']).suffix.lower()=='.md'];return result
        path=safe_path(p.get('path'))
        if not path.is_relative_to(folder) or path.suffix.lower()!='.md':raise ValueError('A nota deve ser MD dentro do cofre escolhido.')
        if action=='read':
            from core.document_reader import read
            return read({'path':str(path),'max_chars':12000,'offset':p.get('offset',0)})
        if action=='create':
            text=str(p.get('text',''))
            if not text or len(text)>100000:raise ValueError('Texto vazio ou longo demais.')
            return request('Criar nota no cofre',str(path),lambda:write_new(path,lambda target:target.write_text(text,encoding='utf-8')))
    if domain=='iphone':
        if action=='status':return {'available':os.name=='nt','connected':False,'verified':False,'note':'Pareamento confirmado pelo Windows; nao ofereco controle irrestrito do iPhone.'}
        if action=='open_link':
            if os.name!='nt':raise ValueError('Vincular ao Celular exige Windows.')
            os.startfile('shell:AppsFolder\\Microsoft.YourPhone_8wekyb3d8bbwe!App')
            return {'opened':True,'connected':False,'note':'Finalize o pareamento no aplicativo do Windows.'}
    if domain=='audio':
        from actions.computer_settings import volume_get,volume_set
        if action=='status':
            import sounddevice
            devices=sounddevice.query_devices()
            return {'volume':volume_get(),'devices':[{'index':i,'name':d['name'],'outputs':d['max_output_channels']} for i,d in enumerate(devices) if d['max_output_channels']]}
        if action=='volume':
            value=int(p.get('value',-1))
            if not 0<=value<=100:raise ValueError('Volume entre 0 e 100.')
            volume_set(value);observed=volume_get()
            return {'ok':observed is not None and abs(observed-value)<=2,'volume':observed,'uncertain':observed is None or abs(observed-value)>2}
    raise ValueError('Acao ou dominio nao suportado.')
