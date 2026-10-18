"""Exportacao por lista permitida, sem estado pessoal nem ambientes locais."""
import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path

DIRECTORIES=('actions','core','dashboard','docs','plugins','tests','tools','.github','resources')
ROOT_FILES=('.gitignore','.gitattributes','LICENSE','NOTICE.md','VERSION.json','CHANGELOG.md','README.md','main.py','ui.py','setup.py','requirements.txt','requirements-win.lock','requirements-extensions.txt','desktop_launcher.py','launch.py','INICIAR-JARVIS.cmd','LEIA-ME.md')
CONFIG_FILES=('__init__.py','defaults.json','dief-jarvis.ico','dief-jarvis.png','jarvis.ico')
VALIDATION_FILES=('essential-plugins-guide.md','settings-connections-pass.md')
EXTENSIONS={'.py','.mjs','.js','.cjs','.html','.css','.json','.md','.txt','.obj','.png','.ico','.svg','.jpg','.jpeg','.webp','.woff2','.cmd','.yml','.yaml','.ps1'}


def candidates(source):
    source=Path(source).resolve();result=[]
    for name in ROOT_FILES:
        if (source/name).is_file():result.append(Path(name))
    for folder in DIRECTORIES:
        for path in (source/folder).rglob('*'):
            if path.is_symlink():raise ValueError('Links externos não são permitidos na distribuição.')
            if not path.is_file() or '__pycache__' in path.parts:continue
            if path.suffix.lower() in EXTENSIONS or path.name=='LICENSE':result.append(path.relative_to(source))
    for name in CONFIG_FILES:
        if (source/'config'/name).is_file():result.append(Path('config')/name)
    result.extend(path.relative_to(source) for path in (source/'memory').glob('*.py'))
    result.extend(Path('validation')/name for name in VALIDATION_FILES if (source/'validation'/name).is_file())
    return sorted(set(result))


def private_literals(source):
    value=json.loads((source/'config/api_keys.json').read_text(encoding='utf-8')) if (source/'config/api_keys.json').exists() else {}
    output=[]
    def visit(item,key=''):
        if isinstance(item,dict):
            for field,entry in item.items():visit(entry,field)
        elif isinstance(item,str) and len(item)>=8:
            if re.search(r'key|token|secret|password|email',key,re.I):output.append(item)
    visit(value)
    return output


def audit(source,files,private=(),allow_document_paths=False):
    findings=[]
    for relative in files:
        name=relative.as_posix();path=source/relative
        if path.suffix.lower() in ('.png','.ico','.jpg','.jpeg','.webp','.woff2'):continue
        data=path.read_bytes();text=data.decode('utf-8',errors='replace')
        if any(secret in text for secret in private):findings.append((name,'credencial ou conta local encontrada'))
        if re.search(r'AIza[0-9A-Za-z_-]{30,}|GOCSPX-[0-9A-Za-z_-]{20,}|sk-(?:proj-)?[0-9A-Za-z_-]{35,}',text):findings.append((name,'possível chave de acesso'))
        if re.search(r'-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----',text):findings.append((name,'chave privada de assinatura encontrada'))
        if not (allow_document_paths and relative.parts[0]=='docs') and re.search(r'C:[/\\]Users[/\\][A-Za-z0-9._-]+[/\\]',text,re.I):findings.append((name,'caminho pessoal fixo'))
    if findings:raise ValueError('Auditoria bloqueou a publicação: '+json.dumps(findings,ensure_ascii=False))


def export(source,destination):
    source=Path(source).resolve();destination=Path(destination).resolve()
    if source==destination or destination.is_relative_to(source):raise ValueError('A cópia pública deve ficar fora da instalação pessoal.')
    if not (destination/'.git').is_dir():raise ValueError('Use um clone Git separado como destino.')
    files=candidates(source);audit(source,files,private_literals(source),allow_document_paths=True)
    manifest={}
    for relative in files:
        target=destination/relative;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source/relative,target)
        if relative.parts[0]=='docs' and target.suffix in ('.md','.txt'):
            text=target.read_text(encoding='utf-8')
            text=re.sub(r'C:[/\\]Users[/\\][A-Za-z0-9._-]+[/\\]',lambda m:'%USERPROFILE%/',text,flags=re.I)
            target.write_text(text,encoding='utf-8')
        data=target.read_bytes()
        if target.suffix not in ('.png','.ico'):data=data.replace(b'\r\n',b'\n')
        manifest[relative.as_posix()]=hashlib.sha256(data).hexdigest()
    upstream=source/'docs/UPSTREAM-README.md'
    if not upstream.is_file():upstream=source/'readme.md'
    if upstream.is_file():
        target=destination/'docs/UPSTREAM-README.md';shutil.copy2(upstream,target)
        audit(destination,[Path('docs/UPSTREAM-README.md')],private_literals(source))
    (destination/'PUBLIC-RELEASE.json').write_text(json.dumps({'schema':1,'text_newlines':'LF','files':manifest},indent=2),encoding='utf-8')
    audit(destination,files,private_literals(source))
    return len(files)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('source',type=Path);parser.add_argument('destination',type=Path)
    args=parser.parse_args();print('Arquivos públicos copiados:',export(args.source,args.destination))
