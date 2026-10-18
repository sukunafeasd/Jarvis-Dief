"""Fixacao mecanica do ambiente Windows testado, com hashes do PyPI."""
import argparse
import importlib.metadata
import json
from pathlib import Path
import re
import urllib.request
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    rows=['# DIEF JARVIS - ambiente Windows x64 validado. Arquivo gerado.']
    packages=sorted((d.metadata['Name'],d.version) for d in importlib.metadata.distributions())
    def resolve(package):
        name,number=package
        if not re.fullmatch(r'[A-Za-z0-9._-]+',name+number):raise ValueError('Identidade de pacote invalida.')
        url=f'https://pypi.org/pypi/{name}/{number}/json'
        with urllib.request.urlopen(url,timeout=30) as response:value=json.load(response)
        hashes=sorted({entry['digests']['sha256'] for entry in value['urls'] if not entry.get('yanked')})
        if not hashes or any(not re.fullmatch(r'[a-f0-9]{64}',h) for h in hashes):raise ValueError('Pacote sem hashes publicados: '+name)
        lines=[name+'=='+number+' '+chr(92)]
        for i,digest in enumerate(hashes):lines.append('    --hash=sha256:'+digest+(' '+chr(92) if i+1<len(hashes) else ''))
        return lines
    with ThreadPoolExecutor(max_workers=6) as pool:
        for lines in pool.map(resolve,packages):rows.extend(lines)
    handle,temporary=tempfile.mkstemp(prefix='requirements-',suffix='.tmp',dir=args.output.resolve().parent)
    try:
        with os.fdopen(handle,'w',encoding='utf-8') as stream:stream.write('\n'.join(rows)+'\n')
        os.replace(temporary,args.output)
    finally:
        if os.path.exists(temporary):os.unlink(temporary)
    print('Pacotes fixados:',len(packages))


if __name__=='__main__':main()
