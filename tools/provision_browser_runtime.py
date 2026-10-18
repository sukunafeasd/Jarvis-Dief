"""Install official Playwright MCP in an isolated per-user Node runtime."""
import base64
import hashlib
from io import BytesIO
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import requests


def main():
    root=Path(os.environ['LOCALAPPDATA'])/'DIEF-JARVIS/runtime/node'
    root.mkdir(parents=True,exist_ok=True)
    node=shutil.which('node')
    if not node:raise ValueError('Node.js nao encontrado; instale a distribuicao oficial.')
    shutil.copy2(node,root/'node.exe')
    package=requests.get('https://registry.npmjs.org/npm/latest',timeout=20).json()
    data=requests.get(package['dist']['tarball'],timeout=60).content
    expected=package['dist']['integrity']
    actual='sha512-'+base64.b64encode(hashlib.sha512(data).digest()).decode()
    if actual!=expected:raise ValueError('Integridade npm invalida.')
    with tarfile.open(fileobj=BytesIO(data),mode='r:gz') as archive:
        archive.extractall(root/'npm',filter='data')
    registry=requests.get('https://registry.npmjs.org/@playwright%2fmcp/latest',timeout=20).json()
    version=registry['version']
    subprocess.run([str(root/'node.exe'),str(root/'npm/package/bin/npm-cli.js'),'install','--prefix',str(root),'--ignore-scripts','--save-exact','@playwright/mcp@'+version],check=True)
    metadata={'playwright_mcp':version,'npm':package['version'],'source':'https://github.com/microsoft/playwright-mcp'}
    (root/'installed.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
    print('Runtime Playwright MCP instalado: '+version,flush=True)


if __name__=='__main__':main()
