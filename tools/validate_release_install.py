"""Instala uma copia limpa dos artefatos em pasta de teste, sem contas."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
from unittest.mock import patch
BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE))
from core.distribution import Installation,verified_manifest,prepare_dependencies
from desktop_launcher import clean_child_environment,run_probe


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--artifacts',type=Path,required=True)
    parser.add_argument('--root',type=Path,required=True);parser.add_argument('--skip-dependencies',action='store_true')
    args=parser.parse_args();artifacts=args.artifacts.resolve();root=args.root.resolve()
    manifest=json.loads((artifacts/'release.json').read_text());release=verified_manifest(manifest)
    def local_download(item,target,progress,stop):
        source=artifacts/item['name']
        if hashlib.sha256(source.read_bytes()).hexdigest()!=item['sha256']:raise ValueError('Hash do artefato divergente.')
        shutil.copy2(source,target)
    def progress(*entry):print(json.dumps(entry,ensure_ascii=True),flush=True)
    stop=threading.Event();installation=Installation(root)
    with patch('core.distribution.download',side_effect=local_download):app=installation.install(release,progress,stop)
    python=installation.prepare_python(stop)
    env=clean_child_environment();env['DIEF_MANAGED_ROOT']=str(root)
    subprocess.run([str(python),'-I','-c','import sys,tkinter,ssl,venv;print(sys.version);print(sys.prefix);print("runtime-ok")'],check=True,env=env)
    if not args.skip_dependencies:
        prepare_dependencies(python,app,progress,stop)
        run_probe(python,app,progress,stop,env)
        subprocess.run([str(python),'-m','pip','check'],check=True,env=env)
    from core.distribution import atomic_json
    atomic_json(root/'validation.json',{'version':release['version'],'dependencies':not args.skip_dependencies,
        'artifacts':{key:release[key]['sha256'] for key in ('application','runtime','launcher')},
        'application_opened':False,'installer_opened':False})
    print(json.dumps({'ok':True,'application':str(app),'python':str(python)}))


if __name__=='__main__':main()
