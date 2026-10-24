"""Gera EXE e pacotes publicos; a chave de assinatura fica fora do projeto."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile

BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE))
from core.distribution import canonical
from core.release_identity import VERSION,REPOSITORY


def keypair(path):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization
    path=Path(path).resolve()
    if path.is_relative_to(BASE):raise ValueError('A chave privada deve ficar fora do projeto.')
    if path.exists():key=serialization.load_pem_private_key(path.read_bytes(),password=None)
    else:
        key=Ed25519PrivateKey.generate();path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb') as stream:stream.write(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
    if not isinstance(key,Ed25519PrivateKey):raise ValueError('A chave nao e Ed25519.')
    public=base64.b64encode(key.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)).decode()
    return key,public


def create_zip(destination,root,files):
    with zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        for relative in sorted(files):
            path=root/relative
            if path.is_symlink():raise ValueError('Links nao sao distribuidos.')
            archive.write(path,relative.as_posix())


def descriptor(path):
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        while chunk:=stream.read(1024*1024):digest.update(chunk)
    return {'name':path.name,'size':path.stat().st_size,'sha256':digest.hexdigest()}


def application_files(source):
    """Keep development evidence in source exports, not in the installed app."""
    from tools.prepare_public_release import candidates
    development_directories = {'tests', 'docs', 'validation', '.github'}
    development_files = {'.gitignore', '.gitattributes'}
    return [path for path in candidates(source)
            if path.parts[0] not in development_directories
            and path.as_posix() not in development_files]


def runtime_files(root):
    files=[]
    for name in ('python.exe','pythonw.exe','python3.dll','python312.dll','vcruntime140.dll','vcruntime140_1.dll','LICENSE.txt'):
        if not (root/name).is_file():raise ValueError('Runtime Python 3.12 incompleto: '+name)
        files.append(Path(name))
    for folder in ('Lib','DLLs','tcl'):
        for path in (root/folder).rglob('*'):
            if not path.is_file() or any(p in {'site-packages','__pycache__','test','tests','idlelib'} for p in path.relative_to(root).parts):continue
            if path.suffix in {'.pyc','.pyo'}:continue
            files.append(path.relative_to(root))
    if Path('Lib/ensurepip/__init__.py') not in files:raise ValueError('Runtime sem reparador de pip.')
    return files


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--public',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--signing-key',type=Path,required=True)
    parser.add_argument('--runtime-base',type=Path,default=Path(sys.base_prefix));parser.add_argument('--skip-exe',action='store_true')
    parser.add_argument('--certificate-thumbprint',default='B77C85CDABB34F3C30A9432413A6A6A83D1329C6')
    args=parser.parse_args();source=args.public.resolve();output=args.output.resolve();output.mkdir(parents=True,exist_ok=True)
    if args.signing_key.resolve().is_relative_to(source):raise ValueError('A chave privada nao pode ficar na copia publica.')
    if output.is_relative_to(source):raise ValueError('Artefatos devem ficar fora da copia publica.')
    key,public=keypair(args.signing_key)
    from core.release_identity import PUBLIC_KEY
    if PUBLIC_KEY!=public:raise ValueError('Configure PUBLIC_KEY com a chave publica antes de exportar. Publica: '+public)
    from tools.prepare_public_release import audit
    files=application_files(source);audit(source,files)
    application=output/f'DIEF-JARVIS-{VERSION}-application.zip'
    runtime=output/'DIEF-JARVIS-python-3.12-win-x64.zip'
    create_zip(application,source,files)
    create_zip(runtime,args.runtime_base.resolve(),runtime_files(args.runtime_base.resolve()))
    if not args.skip_exe:
        work=output/'pyinstaller-work';work.mkdir(exist_ok=True)
        command=[sys.executable,'-m','PyInstaller','--noconfirm','--clean','--onefile','--windowed','--noupx','--uac-admin',
            '--name','DIEF-JARVIS-Setup','--icon',str(source/'config/dief-jarvis.ico'),
            '--version-file',str(source/'tools/windows_version.txt'),
            '--distpath',str(output),'--workpath',str(work),'--specpath',str(work),
            '--paths',str(source),'--add-data',str(source/'config/dief-jarvis.ico')+os.pathsep+'config',
            '--add-data',str(source/'core/spatial/assets/deep-space.png')+os.pathsep+'core/spatial/assets',
            '--exclude-module','PyQt6','--exclude-module','numpy','--exclude-module','google',
            '--exclude-module','sounddevice','--exclude-module','win32com',str(source/'desktop_launcher.py')]
        subprocess.run(command,check=True,cwd=source)
    if args.certificate_thumbprint:
        subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-File',str(source/'tools/sign_installer.ps1'),
            '-Path',str(output/'DIEF-JARVIS-Setup.exe'),'-CertificateThumbprint',args.certificate_thumbprint],check=True)
    if not (output/'DIEF-JARVIS-Setup.exe').is_file():raise ValueError('EXE ausente; nao ha release completo.')
    body={'schema':1,'repository':REPOSITORY,'version':VERSION,'application':descriptor(application),'runtime':descriptor(runtime),
        'launcher':descriptor(output/'DIEF-JARVIS-Setup.exe')}
    signature=base64.b64encode(key.sign(canonical(body))).decode()
    (output/'release.json').write_text(json.dumps({'release':body,'signature':signature},indent=2),encoding='utf-8')
    artifacts=[application,runtime,output/'release.json']
    if (output/'DIEF-JARVIS-Setup.exe').is_file():artifacts.append(output/'DIEF-JARVIS-Setup.exe')
    (output/'SHA256SUMS.txt').write_text(''.join(descriptor(p)['sha256']+'  '+p.name+'\n' for p in artifacts),encoding='utf-8')
    print(json.dumps({'version':VERSION,'artifacts':[p.name for p in artifacts]}))


if __name__=='__main__':main()
