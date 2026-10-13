"""Instalacao por versoes, com manifesto assinado e dados fora do pacote."""
from __future__ import annotations
import base64
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import tempfile
import threading
import urllib.error
import urllib.request
import zipfile
import uuid
from core.release_identity import REPOSITORY, PUBLIC_KEY, SCHEMA, MANIFEST_ASSET

MAX_DOWNLOAD = 1024 * 1024 * 1024


def version(value):
    match = re.fullmatch(r'v?(\d+)\.(\d+)\.(\d+)', str(value))
    if not match: raise ValueError('Versao de release invalida.')
    return tuple(map(int, match.groups()))


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode('utf-8')


def verified_manifest(value, public_key=PUBLIC_KEY):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    body = value['release']
    Ed25519PublicKey.from_public_bytes(base64.b64decode(public_key, validate=True)).verify(
        base64.b64decode(value['signature'], validate=True), canonical(body))
    if body.get('schema') != SCHEMA or body.get('repository') != REPOSITORY:
        raise ValueError('Este pacote nao pertence ao canal oficial.')
    version(body['version'])
    for key in ('application', 'runtime','launcher'):
        item = body[key]
        suffix='exe' if key=='launcher' else 'zip'
        if not re.fullmatch(r'[A-Za-z0-9._-]+\.'+suffix, item['name']): raise ValueError('Nome de arquivo invalido.')
        if not re.fullmatch(r'[a-f0-9]{64}', item['sha256']): raise ValueError('Resumo de integridade invalido.')
        if not isinstance(item['size'], int) or not 0 < item['size'] <= MAX_DOWNLOAD: raise ValueError('Tamanho de pacote invalido.')
    return body


def official_url(value):
    prefix = f'https://github.com/{REPOSITORY}/releases/download/'
    if not value.startswith(prefix) or '?' in value or '#' in value: raise ValueError('Origem de download nao autorizada.')
    if len(value[len(prefix):].split('/')) != 2: raise ValueError('Caminho de release invalido.')
    return value


def request_json(url, limit=1024*1024):
    request = urllib.request.Request(url, headers={'User-Agent':'DIEF-JARVIS/1.0', 'Accept':'application/vnd.github+json'})
    with urllib.request.urlopen(request, timeout=20) as response:
        data = response.read(limit + 1)
    if len(data) > limit: raise ValueError('Resposta de atualizacao muito grande.')
    return json.loads(data)


def latest_release():
    info = request_json(f'https://api.github.com/repos/{REPOSITORY}/releases/latest')
    if info.get('draft') or info.get('prerelease'): raise ValueError('Release nao estavel.')
    asset = next(a for a in info['assets'] if a['name'] == MANIFEST_ASSET)
    body = verified_manifest(request_json(official_url(asset['browser_download_url']), 65536))
    if version(info['tag_name']) != version(body['version']): raise ValueError('Tag e manifesto divergem.')
    tag = 'v' + body['version']
    urls = {a['name']:a['browser_download_url'] for a in info['assets']}
    for key in ('application', 'runtime','launcher'):
        item = body[key]
        item['url'] = official_url(urls[item['name']])
        if item['url'] != f'https://github.com/{REPOSITORY}/releases/download/{tag}/{item["name"]}':
            raise ValueError('Pacote pertence a outra versao.')
    return body


def download(item, target, progress, stop):
    digest = hashlib.sha256(); size = 0
    request = urllib.request.Request(official_url(item['url']), headers={'User-Agent':'DIEF-JARVIS/1.0'})
    try:
        with urllib.request.urlopen(request, timeout=30) as response, Path(target).open('xb') as output:
            while chunk := response.read(256*1024):
                if stop.is_set(): raise InterruptedError('Instalacao cancelada.')
                size += len(chunk)
                if size > item['size'] or size > MAX_DOWNLOAD: raise ValueError('Pacote excedeu o tamanho informado.')
                digest.update(chunk); output.write(chunk)
                progress(f'Baixando {size*100//item["size"]}%')
        if size != item['size'] or digest.hexdigest() != item['sha256']: raise ValueError('Integridade do download nao confirmada.')
    except Exception:
        Path(target).unlink(missing_ok=True)
        raise


def extract(package, destination):
    destination = Path(destination).resolve()
    with zipfile.ZipFile(package) as archive:
        members = archive.infolist()
        if len(members) > 100000 or sum(i.file_size for i in members) > 4*MAX_DOWNLOAD:
            raise ValueError('Pacote descompactado excede o limite.')
        seen = set()
        for item in members:
            name = item.filename
            if item.orig_filename != name or any(ord(c)<32 for c in name):raise ValueError('Nome de arquivo ambiguo no pacote.')
            relative = PurePosixPath(name)
            key = name.casefold()
            if '\\' in name or ':' in name or relative.is_absolute() or '..' in relative.parts or key in seen:
                raise ValueError('Caminho inseguro no pacote.')
            if any(part.rstrip(' .') != part or part.upper().split('.')[0] in {'CON','PRN','AUX','NUL', *(f'COM{i}' for i in range(1,10)), *(f'LPT{i}' for i in range(1,10))} for part in relative.parts):
                raise ValueError('Nome reservado no pacote.')
            if stat.S_ISLNK(item.external_attr >> 16): raise ValueError('Links nao sao aceitos no pacote.')
            target = destination.joinpath(*relative.parts).resolve()
            if not target.is_relative_to(destination): raise ValueError('Extracao fora do destino.')
            seen.add(key)
        archive.extractall(destination)


def atomic_json(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    with temporary.open('w', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2); stream.flush(); os.fsync(stream.fileno())
    os.replace(temporary, path)


class Installation:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.state_file = self.root/'installation.json'
        self.journal=self.root/'transaction.json'
        self.recover()

    def recover(self):
        if not self.journal.exists():return
        transaction=json.loads(self.journal.read_text(encoding='utf-8'))
        number=transaction['next'];version(number)
        prior=transaction['prior']
        backup_name=transaction['backup']
        if not re.fullmatch(r'runtime-backup-[a-f0-9]{32}',backup_name):raise ValueError('Registro de recuperacao invalido.')
        current=self.state()
        if current.get('current')==number:
            self.journal.unlink();return
        backup=self.root/backup_name
        launcher_name=transaction.get('launcher_next')
        if launcher_name:
            if not re.fullmatch(r'launcher-next-[a-f0-9]{32}\.exe',launcher_name):raise ValueError('Registro de inicializador invalido.')
            (self.root/launcher_name).unlink(missing_ok=True)
        if transaction['runtime_changed']:
            if backup.exists():
                self.discard(self.root/'runtime');os.replace(backup,self.root/'runtime')
            elif not transaction['had_runtime']:self.discard(self.root/'runtime')
        if prior.get('current'):
            version(prior['current']);self.activate_shared(self.application(prior['current']))
        self.discard(self.application(number))
        atomic_json(self.state_file,prior);self.journal.unlink()

    def state(self):
        try:
            value = json.loads(self.state_file.read_text(encoding='utf-8'))
        except FileNotFoundError: return {}
        for field in ('current','previous'):
            if value.get(field): version(value[field])
        return value

    def application(self, number):
        version(number)
        path=self.root/'versions'/number
        if not path.resolve().is_relative_to(self.root):raise ValueError('Pasta de versao fora da instalacao.')
        return path

    def activate_shared(self,application):
        for folder in ('config','memory'):
            source=application/'.shared-code'/folder
            shared=self.root/'data'/folder
            for file in source.iterdir():
                temporary=shared/(file.name+'.update-tmp')
                shutil.copy2(file,temporary);os.replace(temporary,shared/file.name)

    def discard(self,path):
        path=Path(path)
        if not path.resolve().is_relative_to(self.root) or path.resolve()==self.root:raise ValueError('Limpeza fora da instalacao.')
        if path.exists():shutil.rmtree(path)

    def install(self, release, progress, stop):
        number = release['version']; version(number)
        state = self.state()
        if state.get('rejected') == number and state.get('current'):return self.application(state['current'])
        if state.get('current') and version(number) <= version(state['current']): return self.application(state['current'])
        with tempfile.TemporaryDirectory(prefix='jarvis-stage-', dir=self.root) as temporary:
            stage = Path(temporary)
            for key in ('runtime','application'):
                if key == 'runtime' and state.get('runtime_sha256') == release[key]['sha256'] and (self.root/'runtime/python.exe').exists(): continue
                package = stage/(key+'.zip')
                download(release[key], package, lambda text:progress('Atualizações', text, 'working'), stop)
                extract(package, stage/key)
            launcher_next=None
            if getattr(__import__('sys'),'frozen',False):
                running=Path(__import__('sys').executable)
                if hashlib.sha256(running.read_bytes()).hexdigest()!=release['launcher']['sha256']:
                    download(release['launcher'],stage/'launcher.exe',lambda text:progress('Atualizações',text,'working'),stop)
                    launcher_next='launcher-next-'+uuid.uuid4().hex+'.exe'
            app = stage/'application'
            required = ('main.py','requirements.txt','core/startup.py','config/defaults.json','memory/config_manager.py')
            if not all((app/file).is_file() for file in required): raise ValueError('Aplicativo incompleto.')
            if json.loads((app/'VERSION.json').read_text(encoding='utf-8'))['version'] != number: raise ValueError('Versao interna divergente.')
            if (stage/'runtime').exists() and not (stage/'runtime/python.exe').is_file():raise ValueError('Runtime incompleto.')
            progress('Arquivos', 'Organizando contas e memoria separadamente', 'working')
            for folder in ('config','memory'):
                shared = self.root/'data'/folder; shared.mkdir(parents=True, exist_ok=True)
                source = app/folder
                for file in source.iterdir():
                    if not (file.is_file() and (file.suffix in {'.py','.ico','.png'} or file.name == 'defaults.json')):
                        raise ValueError('Estado pessoal inesperado no pacote.')
                code=app/'.shared-code'/folder;code.parent.mkdir(exist_ok=True)
                os.replace(source,code)
                if os.name=='nt':
                    import _winapi
                    _winapi.CreateJunction(str(shared),str(source))
                else:os.symlink(shared, source, target_is_directory=True)
            destination = self.application(number)
            destination.parent.mkdir(exist_ok=True)
            if destination.exists():self.discard(destination)
            runtime_changed=(stage/'runtime').exists();swapped=False
            old=self.root/('runtime-backup-'+uuid.uuid4().hex)
            atomic_json(self.journal,{'next':number,'prior':state,'runtime_changed':runtime_changed,
                'had_runtime':(self.root/'runtime').exists(),'backup':old.name,'launcher_next':launcher_next})
            try:
                if runtime_changed:
                    if (self.root/'runtime').exists():os.replace(self.root/'runtime',old)
                    os.replace(stage/'runtime',self.root/'runtime');swapped=True
                os.replace(app, destination)
                self.activate_shared(destination)
                if launcher_next:os.replace(stage/'launcher.exe',self.root/launcher_next)
                atomic_json(self.state_file, {'current':number,'previous':state.get('current'),
                    'runtime_sha256':release['runtime']['sha256'],'previous_runtime_sha256':state.get('runtime_sha256'),
                    'runtime_changed':runtime_changed,'runtime_backup':old.name,'application_sha256':release['application']['sha256'],
                    'previous_application_sha256':state.get('application_sha256'),
                    'pending_launcher':{'name':launcher_next,'sha256':release['launcher']['sha256']} if launcher_next else None,'pending':True})
                self.journal.unlink()
            except Exception:
                if swapped:self.discard(self.root/'runtime')
                if runtime_changed and old.exists():os.replace(old,self.root/'runtime')
                if state.get('current'):self.activate_shared(self.application(state['current']))
                self.discard(destination)
                if launcher_next:(self.root/launcher_next).unlink(missing_ok=True)
                self.journal.unlink(missing_ok=True)
                raise
            return destination

    def confirm(self):
        state = self.state(); state['pending'] = False; atomic_json(self.state_file, state)

    def rollback(self):
        state = self.state()
        if not state.get('previous'): return False
        state['rejected']=state['current']
        pending=state.get('pending_launcher')
        if pending:
            if not re.fullmatch(r'launcher-next-[a-f0-9]{32}\.exe',pending['name']):raise ValueError('Inicializador pendente invalido.')
            (self.root/pending['name']).unlink(missing_ok=True);state['pending_launcher']=None
        state['current'],state['previous'] = state['previous'],None
        state['pending'] = False
        state['application_sha256']=state.get('previous_application_sha256')
        backup_name=state.get('runtime_backup','')
        if backup_name and not re.fullmatch(r'runtime-backup-[a-f0-9]{32}',backup_name):raise ValueError('Pasta de recuperacao invalida.')
        backup=self.root/backup_name if backup_name else None
        if state.get('runtime_changed') and backup and backup.exists():
            rejected=self.root/'runtime.rejected'
            self.discard(rejected)
            os.replace(self.root/'runtime',rejected);os.replace(backup,self.root/'runtime')
            state['runtime_sha256']=state.get('previous_runtime_sha256')
        self.activate_shared(self.application(state['current']))
        atomic_json(self.state_file, state)
        return True

    def prepare_python(self, stop):
        executable = self.root/'environment/Scripts/python.exe'
        if executable.exists():
            try:run([str(executable),'-I','-c','import pip,ssl,venv'],stop,timeout=30)
            except InterruptedError:raise
            except Exception:self.discard(self.root/'environment')
        if not executable.exists():
            run([str(self.root/'runtime/python.exe'),'-I','-m','venv',str(self.root/'environment')], stop)
        if not executable.exists(): raise RuntimeError('Ambiente Python nao foi criado.')
        run([str(executable),'-I','-c','import pip,ssl,venv'],stop,timeout=30)
        return executable


def run(command, stop, timeout=1800, env=None, cwd=None):
    from core.installer_process import spawn,close_tree,environment
    process = spawn(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, env=env or environment(), cwd=cwd)
    # Drain stderr while waiting so a verbose installer cannot fill the pipe.
    tail = bytearray()
    def drain():
        while chunk := process.stderr.read(8192):
            tail.extend(chunk)
            if len(tail)>16384: del tail[:-16384]
    reader = threading.Thread(target=drain, daemon=True); reader.start()
    import time
    until = time.monotonic()+timeout
    while process.poll() is None:
        if stop.wait(.2) or time.monotonic()>until:
            close_tree(process);reader.join(timeout=5);process.stderr.close()
            raise InterruptedError('Preparacao cancelada ou tempo esgotado.')
    close_tree(process)
    reader.join(timeout=5)
    process.stderr.close()
    if process.returncode: raise RuntimeError('Nao foi possivel preparar o ambiente: '+tail.decode('utf-8',errors='replace')[-600:])


def prepare_dependencies(python, application, progress, stop):
    progress('Dependências', 'Verificando e reparando pacotes desta versao', 'working')
    locked=application/'requirements-win.lock'
    requirements=locked if locked.exists() else application/'requirements.txt'
    run([str(python),'-I','-m','pip','--isolated','install','--no-input','--disable-pip-version-check',
        '--index-url','https://pypi.org/simple',*(['--require-hashes'] if locked.exists() else []),'-r',str(requirements)], stop)
    from core.dependency_integrity import repair
    repair(python,application,progress,stop)
    from core.installer_process import environment
    import sys
    browser_root=Path(python).resolve().parents[2]/'browsers'
    env=environment();env['PLAYWRIGHT_BROWSERS_PATH']=str(browser_root)
    check='from pathlib import Path;from playwright.sync_api import sync_playwright;p=sync_playwright().start();ready=Path(p.chromium.executable_path).is_file();p.stop();raise SystemExit(0 if ready else 1)'
    try:run([str(python),'-I','-c',check],stop,timeout=30,env=env)
    except InterruptedError:raise
    except RuntimeError:
        progress('Dependências','Preparando o navegador privado de automacao','working')
        run([str(python),'-I','-m','playwright','install','chromium'],stop,env=env)
        run([str(python),'-I','-c',check],stop,timeout=30,env=env)
    progress('Dependências', 'Ambiente Python preparado', 'ok')
