"""Consulta somente o canal assinado; atualizacao ocorre na proxima abertura."""
import os
import urllib.error
from core.essential_plugins import respond
from core.release_identity import VERSION,REPOSITORY
from core.distribution import latest_release,version

PLUGIN={'name':'resource_updates',
 'description':'Consulta versoes oficiais DIEF JARVIS com assinatura verificada. Na instalacao EXE, novas versoes sao preparadas automaticamente pelo inicializador na proxima abertura, preservando dados. Nao altera o codigo enquanto a sessao esta ativa. Nunca afirme que instalou uma versao apenas por consultar a release.',
 'parameters':{'type':'OBJECT','properties':{'action':{'type':'STRING','enum':['status','check']}},'required':['action']}}


def execute(p):
    managed=bool(os.environ.get('DIEF_MANAGED_ROOT'))
    status={'checker_available':True,'automatic_install_available':managed,'local_version':VERSION,
        'repository':REPOSITORY,'update_on_next_launch':managed,'installed':False,
        'data_preservation':'Contas e memoria locais separadas das versoes.'}
    if p.get('action')=='status':return status
    if p.get('action')!='check':raise ValueError('Acao invalida.')
    try:release=latest_release()
    except urllib.error.HTTPError as error:
        if error.code==404:return {**status,'published_release':False,'update_available':False}
        raise
    return {**status,'published_release':True,'tag':'v'+release['version'],
        'update_available':version(release['version'])>version(VERSION),'signature_verified':True,
        'page':f'https://github.com/{REPOSITORY}/releases/tag/v{release["version"]}'}


def run(parameters,**kwargs):return respond(lambda:execute(parameters))
