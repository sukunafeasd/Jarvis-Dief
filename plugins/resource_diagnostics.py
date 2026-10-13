"""Inspecao limitada e reparacao declarada, nao um instalador remoto arbitrario."""
import json
import threading
from pathlib import Path
from core.essential_plugins import respond
from core.resource_jobs import request
PLUGIN={'name':'resource_diagnostics','description':'Verifica pacotes declarados e arquivos essenciais. repair_dependencies instala SOMENTE pacotes ausentes de requirements.txt pelo bootstrap existente, com confirmacao humana, sem comandos/URLs do modelo. Nao autoriza contas sozinho. Lista catalogo de plugins sem retornar credenciais.',
 'parameters':{'type':'OBJECT','properties':{'action':{'type':'STRING','enum':['status','dependencies','plugins','repair_dependencies','catalog','guide']},'tool':{'type':'STRING','description':'Nome exato da ferramenta para consultar seu manual de uso, exemplos e limites.'}},'required':['action']}}


def execute(p):
    from core.startup import missing_dependencies
    from core.plugin_loader import discover_plugins
    root=Path(__file__).resolve().parents[1]
    action=p.get('action','status')
    if action in ('catalog','guide'):
        from core import resource_manual
        return resource_manual.catalog() if action=='catalog' else resource_manual.guide(p.get('tool',''))
    if action in ('status','dependencies'):
        missing=missing_dependencies()
        absent=[name for name in ('core/prompt.txt','core/spatial/index.html','core/spatial/presentation.html','core/face_model.obj') if not (root/name).is_file()]
        return {'available':True,'missing_dependencies':missing,'missing_files':absent,'ready':not missing and not absent,'accounts_tested':False}
    if action=='plugins':
        registry=discover_plugins(root/'plugins',set(),logger=lambda _:None)
        return {'items':[{key:value for key,value in row.items() if key!='description'} for row in registry.list_for_ui()],'connections_verified':False}
    if action=='repair_dependencies':
        missing=missing_dependencies()
        if not missing:return {'ok':True,'installed':False,'note':'Nenhum pacote declarado ausente.'}
        def repair():
            import subprocess,sys
            if getattr(sys,'frozen',False) or sys.prefix==sys.base_prefix:raise ValueError('Reparacao exige ambiente virtual; no EXE precisa do instalador apropriado.')
            result=subprocess.run([sys.executable,'-m','pip','--isolated','install','--no-input','--index-url','https://pypi.org/simple',*missing],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=300,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            import importlib
            importlib.invalidate_caches()
            remaining=missing_dependencies()
            return {'ok':result.returncode==0 and not remaining,'remaining':remaining,'restart_recommended':True}
        return request('Instalar dependencias declaradas',f'{len(missing)} pacotes ausentes; origem oficial PyPI.',repair)
    raise ValueError('Acao invalida.')

def run(parameters,**kwargs):return respond(lambda:execute(parameters))
