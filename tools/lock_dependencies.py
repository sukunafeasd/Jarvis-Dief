"""Fixacao mecanica do ambiente Windows testado, com hashes do PyPI."""
import argparse
import importlib.metadata
import json
from pathlib import Path
import re
import urllib.request


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    rows=['# DIEF JARVIS - ambiente Windows x64 validado. Arquivo gerado.']
    packages=sorted((d.metadata['Name'],d.version) for d in importlib.metadata.distributions())
    for name,number in packages:
        if not re.fullmatch(r'[A-Za-z0-9._-]+',name+number):raise ValueError('Identidade de pacote invalida.')
        url=f'https://pypi.org/pypi/{name}/{number}/json'
        with urllib.request.urlopen(url,timeout=30) as response:value=json.load(response)
        hashes=sorted({entry['digests']['sha256'] for entry in value['urls'] if not entry.get('yanked')})
        if not hashes or any(not re.fullmatch(r'[a-f0-9]{64}',h) for h in hashes):raise ValueError('Pacote sem hashes publicados: '+name)
        rows.append(name+'=='+number+' \\')
        for i,digest in enumerate(hashes):rows.append('    --hash=sha256:'+digest+(' \\' if i+1<len(hashes) else ''))
    args.output.write_text('\n'.join(rows)+'\n',encoding='utf-8')
    print('Pacotes fixados:',len(packages))


if __name__=='__main__':main()
