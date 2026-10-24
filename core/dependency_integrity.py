"""RECORD das distribuicoes detecta arquivos removidos ou alterados."""
import argparse
import base64
import hashlib
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys
import re
import shlex
import tempfile
import time
import stat


def repair_requirements(locked, damaged):
    """Select exact locked entries without dropping their approved hashes."""
    from pip._vendor.packaging.requirements import Requirement
    from pip._vendor.packaging.utils import canonicalize_name
    wanted={canonicalize_name(name) for name in damaged}
    found={}
    for line in locked.read_text(encoding='utf-8').replace('\\\n',' ').splitlines():
        text=line.strip()
        if not text or text.startswith('#'):continue
        try:
            tokens=shlex.split(text)
            requirement=Requirement(tokens[0])
        except (ValueError,IndexError):return None
        specs=list(requirement.specifier)
        if (requirement.url or requirement.marker or requirement.extras or len(specs)!=1
                or specs[0].operator!='==' or '*' in specs[0].version):return None
        if len(tokens)<2 or not all(re.fullmatch(r'--hash=sha256:[a-fA-F0-9]{64}',token) for token in tokens[1:]):return None
        name=canonicalize_name(requirement.name)
        if name in found:return None
        found[name]=text
    if not wanted or not wanted.issubset(found):return None
    return '\n'.join(found[name] for name in sorted(wanted))+'\n'


def environment_state(requirements):
    """Invalidate the fast path on changed requirements, interpreter or packages."""
    packages=sorted((d.metadata['Name'].lower(),d.version)
                    for d in importlib.metadata.distributions() if d.metadata['Name'])
    return {'schema':1,'requirements_sha256':hashlib.sha256(Path(requirements).read_bytes()).hexdigest(),
            'python':sys.version,'executable':str(Path(sys.executable).resolve()),
            'packages':packages}


def check_environment_state(requirements, stamp):
    try:
        saved=json.loads(Path(stamp).read_text(encoding='utf-8'))
        return saved==json.loads(json.dumps(environment_state(requirements)))
    except (OSError,ValueError,TypeError):
        return False


def broken_distributions(cache_path=None):
    root=Path(sys.prefix).resolve();broken=[]
    cache_path=Path(cache_path) if cache_path else root/'dependency-integrity.json'
    now=time.time();previous={};verified_at=now
    try:
        saved=json.loads(cache_path.read_text(encoding='utf-8'))
        age=now-float(saved['verified_at'])
        if saved.get('schema')==1 and saved.get('root')==str(root) and 0<=age<86400 and isinstance(saved.get('files'),dict):
            previous=saved['files'];verified_at=saved['verified_at']
    except (OSError,ValueError,TypeError,KeyError):pass
    current={};parents={}
    for distribution in importlib.metadata.distributions():
        for entry in distribution.files or []:
            if entry.hash is None:continue
            located=Path(distribution.locate_file(entry))
            # Resolve each directory once per inspection, not once per file.
            # File-level links still need their own canonical target check.
            parent=parents.get(located.parent)
            if parent is None:
                parent=located.parent.resolve();parents[located.parent]=parent
            path=parent/located.name
            try:
                info=path.lstat()
                if stat.S_ISLNK(info.st_mode) or getattr(info,'st_file_attributes',0)&getattr(stat,'FILE_ATTRIBUTE_REPARSE_POINT',1024):
                    path=path.resolve()
                    if not path.is_relative_to(root):continue
                    info=path.stat()
            except FileNotFoundError:
                if not path.is_relative_to(root):continue
                broken.append(distribution.metadata['Name']);break
            if not path.is_relative_to(root):continue
            if not stat.S_ISREG(info.st_mode):broken.append(distribution.metadata['Name']);break
            fingerprint=[info.st_size,info.st_mtime_ns,info.st_ctime_ns,info.st_ino,entry.hash.mode,entry.hash.value]
            key=str(path)
            if previous.get(key)==fingerprint:
                current[key]=fingerprint
                continue
            digest=hashlib.new(entry.hash.mode)
            with path.open('rb') as stream:
                while chunk:=stream.read(1024*1024):digest.update(chunk)
            actual=base64.urlsafe_b64encode(digest.digest()).rstrip(b'=').decode()
            if actual!=entry.hash.value:broken.append(distribution.metadata['Name']);break
            current[key]=fingerprint
    # Only successful inspections may seed the accelerator. A daily full scan
    # remains mandatory; this cache is not an anti-malware trust boundary.
    if not broken:
        try:
            with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=cache_path.parent,delete=False,suffix='.integrity.tmp') as stream:
                temporary=Path(stream.name)
                json.dump({'schema':1,'root':str(root),'verified_at':verified_at,'files':current},stream)
            temporary.replace(cache_path)
        except OSError:
            if 'temporary' in locals():
                try:temporary.unlink(missing_ok=True)
                except OSError:pass
    return sorted(set(broken))


def repair(python,application,progress,stop):
    from core.installer_process import spawn,close_tree
    def inspect():
        progress('Dependências','Conferindo integridade dos arquivos instalados','working')
        command=[str(python),'-I',str(application/'core/dependency_integrity.py'),'--inspect']
        process=spawn(command,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,encoding='utf-8')
        import time
        until=time.monotonic()+180
        while process.poll() is None:
            if stop.wait(.1) or time.monotonic()>until:close_tree(process);process.stdout.close();raise InterruptedError('Verificacao de integridade interrompida.')
        close_tree(process);output=process.stdout.read();process.stdout.close()
        if process.returncode:raise RuntimeError('Nao foi possivel conferir a integridade das dependencias.')
        value=json.loads(output)
        if not isinstance(value,list) or not all(isinstance(name,str) for name in value):raise ValueError('Relatorio de integridade invalido.')
        return value
    damaged=inspect()
    if damaged:
        from core.distribution import run
        locked=application/'requirements-win.lock'
        requirements=locked if locked.exists() else application/'requirements.txt'
        progress('Dependências','Reparando arquivos de '+', '.join(damaged[:4]),'working')
        selected=repair_requirements(locked,damaged) if locked.exists() else None
        with tempfile.TemporaryDirectory(prefix='dief-dependency-repair-') as folder:
            if selected:
                requirements=Path(folder)/'requirements.lock'
                requirements.write_text(selected,encoding='utf-8')
            run([str(python),'-I','-m','pip','--isolated','install','--force-reinstall','--no-deps','--no-input',
                '--disable-pip-version-check','--index-url','https://pypi.org/simple',
                *(['--require-hashes'] if locked.exists() else []),'-r',str(requirements)],stop)
        if inspect():raise RuntimeError('Dependencias ainda apresentam arquivos danificados.')
    progress('Dependências','Pacotes e arquivos internos verificados','ok')


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--inspect',action='store_true')
    parser.add_argument('--requirements',type=Path)
    parser.add_argument('--stamp',type=Path)
    group=parser.add_mutually_exclusive_group()
    group.add_argument('--check-state',action='store_true')
    group.add_argument('--record-state',action='store_true')
    group.add_argument('--state-capability',action='store_true')
    args=parser.parse_args()
    if args.state_capability:raise SystemExit(0)
    if args.check_state or args.record_state:
        if not args.requirements or not args.stamp:parser.error('requirements e stamp obrigatorios')
        if args.check_state:raise SystemExit(0 if check_environment_state(args.requirements,args.stamp) else 1)
        value=environment_state(args.requirements)
        temporary=args.stamp.with_suffix('.tmp')
        temporary.write_text(json.dumps(value),encoding='utf-8')
        temporary.replace(args.stamp)
    else:
        print(json.dumps(broken_distributions()))
