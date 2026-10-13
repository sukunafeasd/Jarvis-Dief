"""Publicacao explicita; credencial lida pelo Git, nunca impressa ou exportada."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import requests

BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE))
from core.release_identity import REPOSITORY,VERSION


def session():
    token=os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN')
    if not token:
        result=subprocess.run(['git','credential','fill'],input='protocol=https\nhost=github.com\n\n',
            capture_output=True,text=True,timeout=120)
        values=dict(line.split('=',1) for line in result.stdout.splitlines() if '=' in line)
        token=values.get('password')
    if not token:raise RuntimeError('Autenticacao do GitHub indisponivel.')
    client=requests.Session();client.headers.update({'Authorization':'Bearer '+token,
        'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28','User-Agent':'DIEF-JARVIS-Release'})
    return client


def call(client,method,path,**kwargs):
    response=client.request(method,'https://api.github.com'+path,timeout=60,**kwargs)
    if not response.ok:raise RuntimeError(f'GitHub retornou {response.status_code} em {path}.')
    return response.json() if response.content else {}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=['info','create','publish','delete-old'])
    parser.add_argument('--artifacts',type=Path);parser.add_argument('--verified-install',type=Path)
    args=parser.parse_args();client=session()
    user=call(client,'GET','/user');owner,name=REPOSITORY.split('/')
    if user['login'].casefold()!=owner.casefold():raise RuntimeError('A conta autenticada nao e a proprietaria do projeto.')
    if args.command=='info':
        print(json.dumps({'account':user['login'],'id':user['id'],'repository':REPOSITORY}));return
    if args.command=='create':
        response=client.get('https://api.github.com/repos/'+REPOSITORY,timeout=30)
        if response.status_code==404:
            info=call(client,'POST','/user/repos',json={'name':name,'description':'DIEF JARVIS: assistente desktop espacial em portugues para Windows.',
                'private':False,'auto_init':False,'has_issues':True,'has_wiki':False})
        elif response.ok:
            info=response.json()
            if info.get('size',0)>0:raise RuntimeError('O novo repositorio ja contem arquivos; nao sera sobrescrito automaticamente.')
        else:raise RuntimeError('Nao foi possivel consultar o repositorio.')
        print(json.dumps({'url':info['html_url'],'created':True}));return
    if args.command=='publish':
        output=args.artifacts.resolve();tag='v'+VERSION
        required=['DIEF-JARVIS-Setup.exe',f'DIEF-JARVIS-{VERSION}-application.zip','DIEF-JARVIS-python-3.12-win-x64.zip','release.json','SHA256SUMS.txt']
        if not all((output/name).is_file() for name in required):raise RuntimeError('Artefatos incompletos.')
        release=call(client,'POST','/repos/'+REPOSITORY+'/releases',json={'tag_name':tag,'target_commitish':'main',
            'name':'DIEF JARVIS '+VERSION,'draft':True,'prerelease':False,
            'body':(BASE/'CHANGELOG.md').read_text(encoding='utf-8')+'\n\nBaixe DIEF-JARVIS-Setup.exe. A primeira preparacao requer internet. O EXE usa o certificado local autoassinado Equipe Dief; outros computadores podem exibir aviso de editor desconhecido. Nenhuma conta pessoal acompanha a distribuicao.'})
        upload=release['upload_url'].split('{')[0]
        for name in required:
            path=output/name
            with path.open('rb') as stream:
                response=client.post(upload,params={'name':name},data=stream,headers={'Content-Type':'application/octet-stream','Content-Length':str(path.stat().st_size)},timeout=900)
            if not response.ok:raise RuntimeError('Falha ao enviar artefato '+name+': '+str(response.status_code))
        final=call(client,'PATCH','/repos/'+REPOSITORY+'/releases/'+str(release['id']),json={'draft':False,'make_latest':'true'})
        print(json.dumps({'release':final['html_url'],'assets':required}));return
    if args.command=='delete-old':
        old=owner+'/Dief-Jarvis'
        if old.casefold()==REPOSITORY.casefold():raise RuntimeError('Nao e permitido apagar o novo repositorio.')
        if not args.verified_install:raise RuntimeError('Informe o registro do teste de instalacao antes da remocao.')
        receipt=json.loads(args.verified_install.read_text(encoding='utf-8'))
        from core.distribution import latest_release,download
        release=latest_release()
        if release['version']!=VERSION or receipt.get('version')!=VERSION or receipt.get('application_opened') is not True or receipt.get('installer_opened') is not True or receipt.get('exit_code')!=0:
            raise RuntimeError('Instalador e aplicativo precisam ser testados antes da remocao.')
        with tempfile.TemporaryDirectory(prefix='jarvis-verify-release-') as directory:
            for key in ('application','runtime','launcher'):
                item=release[key]
                if receipt.get('artifacts',{}).get(key)!=item['sha256']:raise RuntimeError('O teste nao corresponde ao artefato publicado.')
                download(item,Path(directory)/item['name'],lambda _:None,threading.Event())
        call(client,'DELETE','/repos/'+old)
        print(json.dumps({'deleted':old,'preserved':REPOSITORY}))


if __name__=='__main__':main()
