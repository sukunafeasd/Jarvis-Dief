"""Download reviewed instruction snapshots and licensed planetary textures."""
import hashlib
import json
from pathlib import Path
import requests
import base64
import sys

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / 'resources' / 'skills'
ASSETS = ROOT / 'core' / 'spatial' / 'assets'
SOURCES = {
    'obra/superpowers': ['brainstorming', 'writing-plans', 'systematic-debugging',
                        'verification-before-completion', 'requesting-code-review', 'test-driven-development'],
    'anthropics/skills': ['frontend-design', 'webapp-testing', 'mcp-builder', 'skill-creator'],
    'vercel-labs/agent-skills': ['web-design-guidelines'],
}
OUTPUT = {}


def save(path, data):
    if '--emit' in sys.argv:
        OUTPUT[str(path.relative_to(ROOT)).replace('\\', '/')] = data.decode('utf-8')
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


def progress(message):
    print(message, file=sys.stderr, flush=True)


def fetch(url):
    response = requests.get(url, timeout=(10, 60))
    response.raise_for_status()
    if len(response.content) > 12 * 1024 * 1024:
        raise ValueError('Download acima do limite.')
    return response.content


def main():
    manifest = []
    for repo, names in ({} if '--asset' in sys.argv else SOURCES).items():
        info = json.loads(fetch('https://api.github.com/repos/' + repo))
        branch = info['default_branch']
        revision = json.loads(fetch(f'https://api.github.com/repos/{repo}/commits/{branch}'))['sha']
        base = f'https://raw.githubusercontent.com/{repo}/{revision}/'
        for name in names:
            folder = SKILLS / (repo.split('/')[0] + '--' + name)
            data = fetch(base + f'skills/{name}/SKILL.md').decode('utf-8').replace('\r\n','\n').rstrip('\n').encode()+b'\n'
            license_data = None
            for relative in (f'skills/{name}/LICENSE.txt', 'LICENSE', 'LICENSE.txt', 'LICENSE.md'):
                try:
                    license_data = fetch(base + relative)
                    break
                except requests.HTTPError:
                    continue
            if license_data is None:
                progress('Snapshot nao empacotado sem licenca: ' + repo + '/' + name)
                continue
            save(folder / 'SKILL.md', data)
            save(folder / 'LICENSE.txt', license_data)
            manifest.append({'id': folder.name, 'name': name, 'origin': repo,
                             'revision': revision, 'source': f'https://github.com/{repo}/tree/{revision}/skills/{name}',
                             'path': folder.name + '/SKILL.md', 'sha256': hashlib.sha256(data).hexdigest(),
                             'enabled': True, 'scripts_allowed': False})
            progress('Skill: ' + folder.name)
    # Official Notion workflows are instruction-only snapshots, not account access.
    repo = 'openai/plugins'
    revision = json.loads(fetch(f'https://api.github.com/repos/{repo}/commits/main'))['sha'] if '--asset' not in sys.argv else ''
    tree = json.loads(fetch(f'https://api.github.com/repos/{repo}/git/trees/{revision}?recursive=1')) if revision else {}
    for item in tree.get('tree', []):
        path = item['path']
        if not path.startswith('plugins/notion/skills/') or not path.endswith('/SKILL.md'):
            continue
        name = path.split('/')[-2]
        folder = SKILLS / ('openai--' + name)
        base = f'https://raw.githubusercontent.com/{repo}/{revision}/'
        data = fetch(base + path).decode('utf-8').replace('\r\n','\n').rstrip('\n').encode()+b'\n'
        # Preserve the license alongside the snapshot, never infer unrestricted rights.
        license_data = None
        for relative in (path.rsplit('/', 1)[0] + '/LICENSE.txt', 'plugins/notion/LICENSE.txt', 'plugins/notion/LICENSE'):
            try:
                license_data = fetch(base + relative)
                break
            except requests.HTTPError:
                continue
        if license_data is None:
            progress('Workflow nao empacotado sem licenca: ' + name)
            continue
        save(folder / 'SKILL.md', data)
        save(folder / 'LICENSE.txt', license_data)
        manifest.append({'id': folder.name, 'name': name, 'origin': repo, 'revision': revision,
                         'source': f'https://github.com/{repo}/blob/{revision}/{path}',
                         'path': folder.name + '/SKILL.md', 'sha256': hashlib.sha256(data).hexdigest(),
                         'enabled': True, 'scripts_allowed': False})
    if '--asset' not in sys.argv:
        save(SKILLS / 'manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2).encode())
    credits = []
    names = () if '--skills-only' in sys.argv else (sys.argv[sys.argv.index('--asset') + 1],) if '--asset' in sys.argv else ('mercury', 'venus_atmosphere', 'mars', 'jupiter', 'saturn', 'uranus', 'neptune', 'sun', 'earth_clouds')
    for name in names:
        url = f'https://www.solarsystemscope.com/textures/download/2k_{name}.jpg'
        data = fetch(url)
        if '--emit' in sys.argv:
            from PIL import Image
            from io import BytesIO
            image = Image.open(BytesIO(data));image.thumbnail((1024, 512))
            stream = BytesIO();image.convert('RGB').save(stream, format='JPEG', quality=80)
            data = stream.getvalue()
            save(ASSETS / (name + '-sss.json'), json.dumps({'image': 'data:image/jpeg;base64,' + base64.b64encode(data).decode()}).encode())
        else:
            (ASSETS / (name + '-sss.jpg')).write_bytes(data)
        credits.append({'file': name + '-sss.jpg', 'url': url, 'sha256': hashlib.sha256(data).hexdigest()})
        progress('Textura: ' + name)
    if '--asset' not in sys.argv and '--skills-only' not in sys.argv:
        save(ASSETS / 'solar-textures.json', json.dumps({'author': 'Solar System Scope / INOVE',
        'license': 'CC BY 4.0', 'license_url': 'https://creativecommons.org/licenses/by/4.0/',
        'source': 'https://www.solarsystemscope.com/textures/', 'changes': 'Redimensionamento em GPU; iluminacao artistica.',
            'files': credits}, indent=2).encode())
    if '--emit' in sys.argv:
        print('BUNDLE_JSON:' + json.dumps(OUTPUT, ensure_ascii=True), flush=True)


if __name__ == '__main__':
    main()
