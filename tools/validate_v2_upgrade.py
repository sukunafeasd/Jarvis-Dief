"""Exercise the actual v1 updater against v2 artifacts in an isolated root."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import types
from unittest.mock import patch


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--repository',type=Path,required=True)
    parser.add_argument('--artifacts',type=Path,required=True)
    parser.add_argument('--root',type=Path,required=True)
    args=parser.parse_args()
    sys.path.insert(0,str(args.repository))
    source=subprocess.run(['git','show','v1.0.0:core/distribution.py'],cwd=args.repository,check=True,capture_output=True,text=True).stdout
    old=types.ModuleType('v1_updater');exec(compile(source,'v1_distribution.py','exec'),old.__dict__)
    release=old.verified_manifest(json.loads((args.artifacts/'release.json').read_text()))
    stop=threading.Event()
    installation=old.Installation(args.root)
    with patch.object(old,'request_json',wraps=old.request_json):
        import urllib.request
        info=old.request_json('https://api.github.com/repos/sukunafeasd/Jarvis-Dief/releases/tags/v1.0.0')
        manifest=next(a['browser_download_url'] for a in info['assets'] if a['name']=='release.json')
        prior=old.verified_manifest(old.request_json(manifest))
        for key in ('application','runtime','launcher'):
            prior[key]['url']=next(a['browser_download_url'] for a in info['assets'] if a['name']==prior[key]['name'])
        installation.install(prior,lambda *a:None,stop);installation.confirm()
    marker=args.root/'data/config/upgrade-fixture.json';marker.write_text('{"fixture":"preserve"}')
    def local_download(item,target,progress,cancel):
        source=args.artifacts/item['name']
        if hashlib.sha256(source.read_bytes()).hexdigest()!=item['sha256']:raise ValueError('Hash mismatch')
        shutil.copy2(source,target)
    with patch.object(old,'download',side_effect=local_download):
        app=installation.install(release,lambda *a:None,stop)
    assert installation.state()['current']=='2.0.0'
    assert installation.state()['previous']=='1.0.0'
    assert json.loads(marker.read_text())['fixture']=='preserve'
    assert (app/'resources/ui-icons/plug.svg').is_file()
    assert (app/'core/spectro.py').is_file()
    assert (app/'core/forge/runtime.py').is_file()
    assert installation.rollback()
    assert installation.state()['current']=='1.0.0'
    assert json.loads(marker.read_text())['fixture']=='preserve'
    result={'passed':True,'v1_signature_accepts_v2':True,'upgrade':True,'data_preserved':True,'rollback':True}
    (args.root/'upgrade-validation.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result))


if __name__=='__main__':main()
