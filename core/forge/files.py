"""Project-only file access, immutable revisions, and collision-free exports."""
from __future__ import annotations

from contextlib import contextmanager
import ctypes
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import uuid

from core.local_data import atomic_write

MAX_FILE = 8 * 1024 * 1024
MAX_TOTAL = 64 * 1024 * 1024
MAX_FILES = 2000
SKIP = {'.git', '.codex', '.venv', 'node_modules', '__pycache__'}
EXTENSIONS = {'.html', '.css', '.js', '.mjs', '.cjs', '.ts', '.tsx', '.jsx', '.json',
              '.md', '.txt', '.py', '.toml', '.yaml', '.yml', '.png', '.jpg', '.jpeg',
              '.webp', '.svg', '.gif', '.ico', '.glb', '.gltf', '.obj', '.mtl', '.wasm',
              '.woff', '.woff2', '.mp3', '.wav', '.mp4'}


def relative(value):
    if not isinstance(value, str) or not value or '\\' in value or ':' in value or '\x00' in value:
        raise ValueError('Invalid relative file path')
    path = PurePosixPath(value)
    if path.is_absolute() or any(p in ('', '.', '..') for p in value.split('/')):
        raise ValueError('Invalid relative file path')
    for part in path.parts:
        if part.endswith((' ', '.')) or re.match(r'(?i)^(con|prn|aux|nul|com[0-9]|lpt[0-9])(?:\.|$)', part):
            raise ValueError('Reserved file path')
    return path


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch('[0-9a-f]{32}', value):
        raise ValueError('Invalid project/revision identifier')
    return value


def check_chain(path):
    path = Path(os.path.abspath(path))
    for part in reversed((path, *path.parents)):
        if part.exists() or part.is_symlink():
            info = part.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
                raise ValueError('Links and reparse points are forbidden')
    return path


@contextmanager
def pinned(path):
    """Pin existing Windows ancestors against rename/reparse replacement."""
    path = check_chain(path)
    handles = []
    if os.name == 'nt':
        from ctypes import wintypes
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        create = kernel.CreateFileW
        create.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                           wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        create.restype = wintypes.HANDLE
        close = kernel.CloseHandle
        close.argtypes = [wintypes.HANDLE]
        class Information(ctypes.Structure):
            _fields_ = [('attributes', wintypes.DWORD), ('creation', wintypes.FILETIME),
                        ('access', wintypes.FILETIME), ('write', wintypes.FILETIME),
                        ('volume', wintypes.DWORD), ('size_high', wintypes.DWORD),
                        ('size_low', wintypes.DWORD), ('links', wintypes.DWORD),
                        ('index_high', wintypes.DWORD), ('index_low', wintypes.DWORD)]
        kernel.GetFileInformationByHandle.argtypes = [wintypes.HANDLE, ctypes.POINTER(Information)]
        kernel.GetFinalPathNameByHandleW.argtypes = [wintypes.HANDLE, wintypes.LPWSTR,
                                                   wintypes.DWORD, wintypes.DWORD]
        try:
            for part in reversed((path, *path.parents)):
                if not part.exists():
                    continue
                # READ_ATTRIBUTES alone does not enforce Windows sharing on rename.
                handle = create(str(part), 0x81, 3 if part.is_dir() else 1, None, 3, 0x02200000, None)
                if handle == ctypes.c_void_p(-1).value:
                    raise OSError(ctypes.get_last_error(), 'Cannot pin file path')
                handles.append(handle)
                info = Information()
                if not kernel.GetFileInformationByHandle(handle, ctypes.byref(info)):
                    raise OSError(ctypes.get_last_error(), 'Cannot verify file path')
                if info.attributes & 0x400 or (not info.attributes & 0x10 and info.links != 1):
                    raise ValueError('Reparse points and hard links are forbidden')
                buffer = ctypes.create_unicode_buffer(32768)
                count = kernel.GetFinalPathNameByHandleW(handle, buffer, len(buffer), 0)
                actual = buffer.value
                if actual.startswith('\\\\?\\UNC\\'):
                    actual = '\\\\' + actual[8:]
                elif actual.startswith('\\\\?\\'):
                    actual = actual[4:]
                if not count or count >= len(buffer) or os.path.normcase(actual) != os.path.normcase(str(part)):
                    raise ValueError('File path was redirected')
            check_chain(path)
            yield path
        finally:
            for handle in reversed(handles):
                close(handle)
    else:
        yield path


def allowed(path):
    name = path.name.lower()
    return (path.suffix.lower() in EXTENSIONS and not name.startswith('.')
            and not any(word in name for word in ('token', 'credential', 'secret', 'api_key', 'auth.json')))


def read_file(root, name):
    target = Path(root).joinpath(*relative(name).parts)
    with pinned(target):
        if not target.is_file() or not allowed(target):
            raise ValueError('File is not a preview/export asset')
        with target.open('rb') as stream:
            info = os.fstat(stream.fileno())
            if info.st_nlink != 1:
                raise ValueError('Hard-linked files are forbidden')
            data = stream.read(MAX_FILE + 1)
        if len(data) > MAX_FILE:
            raise ValueError('File exceeds limit')
        return data


def inventory(root):
    result = {}
    total = 0
    with pinned(root):
        for directory, dirs, names in os.walk(root, followlinks=False):
            for child in dirs:
                check_chain(Path(directory) / child)
            dirs[:] = [d for d in dirs if d.lower() not in SKIP and not d.startswith('.')]
            for name in sorted(names):
                target = Path(directory) / name
                check_chain(target)
                if not allowed(target):
                    continue
                key = target.relative_to(root).as_posix()
                data = read_file(root, key)
                total += len(data)
                if len(result) >= MAX_FILES or total > MAX_TOTAL:
                    raise ValueError('Project exceeds revision/export limits')
                result[key] = data
    return result


def hashes(files):
    return {name: hashlib.sha256(data).hexdigest() for name, data in files.items()}


class ProjectStore:
    def __init__(self, root, export_roots=()):
        self.root = check_chain(root)
        self.export_roots = tuple(check_chain(p) for p in export_roots)
        self.root.mkdir(parents=True, exist_ok=True)
        for folder in ('projects', 'library'):
            (self.root / folder).mkdir(exist_ok=True)

    def base(self, project_id):
        return check_chain(self.root / 'projects' / identifier(project_id))

    def load(self, project_id):
        with pinned(self.base(project_id) / 'manifest.json') as path:
            data = json.loads(path.read_text('utf-8'))
        if data['id'] != project_id:
            raise ValueError('Manifest identity mismatch')
        return data

    def write(self, manifest):
        with pinned(self.base(manifest['id'])) as base:
            atomic_write(base / 'manifest.json', json.dumps(manifest, ensure_ascii=True).encode())

    def create(self, name):
        if not isinstance(name, str) or not name.strip() or len(name) > 200:
            raise ValueError('Invalid project name')
        project_id = uuid.uuid4().hex
        base = self.base(project_id)
        base.mkdir()
        (base / 'workspace').mkdir()
        (base / 'revisions').mkdir()
        manifest = {'id': project_id, 'name': name, 'thread_id': None, 'revisions': [],
                    'revision': None, 'entrypoint': None, 'stable_revision': None,
                    'state': 'idle', 'validation': None, 'redo_stack': []}
        self.write(manifest)
        self.checkpoint(manifest)
        return manifest

    def workspace(self, manifest):
        return check_chain(self.base(manifest['id']) / 'workspace')

    def revision_path(self, manifest, revision):
        return check_chain(self.base(manifest['id']) / 'revisions' / identifier(revision))

    def checkpoint(self, manifest):
        files = inventory(self.workspace(manifest))
        digest = hashes(files)
        if manifest['revision']:
            last = next(r for r in manifest['revisions'] if r['id'] == manifest['revision'])
            if last['files'] == digest:
                return last
        revision_id = uuid.uuid4().hex
        path = self.revision_path(manifest, revision_id)
        path.mkdir()
        self._write_files(path, files)
        record = {'id': revision_id, 'files': digest, 'parent': manifest['revision']}
        manifest['revisions'].append(record)
        manifest['revision'] = revision_id
        manifest['redo_stack'] = []
        self.write(manifest)
        return record

    @staticmethod
    def _write_files(root, files):
        root.mkdir(parents=True, exist_ok=True)
        with pinned(root):
            for name, data in files.items():
                target = root.joinpath(*relative(name).parts)
                with pinned(target.parent):
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with pinned(target.parent):
                        check_chain(target)
                        atomic_write(target, data)

    def verified_revision(self, manifest, revision):
        record = next(r for r in manifest['revisions'] if r['id'] == revision)
        files = inventory(self.revision_path(manifest, revision))
        if hashes(files) != record['files']:
            raise ValueError('Revision integrity failed')
        return files

    def undo(self, manifest):
        index = next(i for i, r in enumerate(manifest['revisions']) if r['id'] == manifest['revision'])
        current = manifest['revisions'][index]
        previous_id = current.get('parent', manifest['revisions'][index - 1]['id'] if index else None)
        if not previous_id:
            raise ValueError('No previous revision')
        workspace = self.workspace(manifest)
        if hashes(inventory(workspace)) != current['files']:
            raise ValueError('Unsaved edits conflict with undo; save a revision first')
        previous = next(r for r in manifest['revisions'] if r['id'] == previous_id)
        files = self.verified_revision(manifest, previous['id'])
        # Replace only tracked assets. Untracked or excluded user files survive.
        with pinned(workspace):
            self._write_files(workspace, files)
            for name in set(current['files']) - set(files):
                path = workspace.joinpath(*relative(name).parts)
                with pinned(path.parent):
                    check_chain(path)
                    path.unlink()
        manifest['revision'] = previous['id']
        manifest.setdefault('redo_stack', []).append(current['id'])
        manifest['stable_revision'] = None
        manifest['validation'] = None
        self.write(manifest)
        return previous

    def redo(self, manifest):
        stack = manifest.get('redo_stack', [])
        if not stack:
            raise ValueError('No revision to redo')
        current = next(r for r in manifest['revisions'] if r['id'] == manifest['revision'])
        target = next(r for r in manifest['revisions'] if r['id'] == stack[-1])
        workspace = self.workspace(manifest)
        if hashes(inventory(workspace)) != current['files']:
            raise ValueError('Unsaved edits conflict with redo')
        files = self.verified_revision(manifest, target['id'])
        with pinned(workspace):
            self._write_files(workspace, files)
            for name in set(current['files']) - set(files):
                path = workspace.joinpath(*relative(name).parts)
                with pinned(path.parent):
                    check_chain(path)
                    path.unlink()
        stack.pop()
        manifest['revision'] = target['id']
        manifest['stable_revision'] = None
        manifest['validation'] = None
        self.write(manifest)
        return target

    def export(self, manifest, destination):
        path = Path(destination)
        if not path.is_absolute():
            raise ValueError('Export destination must be absolute')
        path = check_chain(path)
        if not any(path != root and path.is_relative_to(root) for root in self.export_roots):
            raise ValueError('Destination is outside host-approved export roots')
        if path.is_relative_to(self.root) or self.root.is_relative_to(path):
            raise ValueError('Cannot export over FORJA data')
        files = self.verified_revision(manifest, manifest['revision'])
        with pinned(path.parent):
            if not path.parent.is_dir():
                raise ValueError('Export parent must exist')
            path.mkdir(exist_ok=False)
            try:
                self._write_files(path, files)
            except BaseException:
                # Retain a partial export rather than remove any concurrently added files.
                raise
        return {'destination': str(path), 'files': hashes(files), 'revision': manifest['revision']}

    def register(self, manifest, name):
        if not isinstance(name, str) or not name.strip() or len(name) > 200:
            raise ValueError('Invalid artifact name')
        if manifest['stable_revision'] != manifest['revision']:
            raise ValueError('Renderer validation is required before library registration')
        files = self.verified_revision(manifest, manifest['revision'])
        artifact_id = uuid.uuid4().hex
        path = check_chain(self.root / 'library' / artifact_id)
        path.mkdir()
        self._write_files(path / 'files', files)
        record = {'id': artifact_id, 'name': name, 'project_id': manifest['id'],
                  'version': manifest['revision'], 'type': 'web',
                  'entrypoint': manifest['entrypoint'], 'files': hashes(files),
                  'capabilities': ['isolated-web-preview'], 'dependencies': [],
                  'parameters': {}, 'framing': None, 'thumbnail': None,
                  'validation': manifest['validation']}
        atomic_write(path / 'artifact.json', json.dumps(record).encode())
        return record

    def catalog(self):
        result = []
        with pinned(self.root / 'library') as root:
            for path in root.iterdir():
                with pinned(path / 'artifact.json') as record:
                    result.append(json.loads(record.read_text('utf-8')))
        return result

    def artifact(self, artifact_id):
        base = check_chain(self.root / 'library' / identifier(artifact_id))
        with pinned(base / 'artifact.json') as path:
            record = json.loads(path.read_text('utf-8'))
        if record['id'] != artifact_id or not record.get('validation'):
            raise ValueError('Artifact identity/validation is missing')
        root = base / 'files'
        files = inventory(root)
        if hashes(files) != record['files']:
            raise ValueError('Registered artifact integrity failed')
        relative(record['entrypoint'])
        if record['entrypoint'] not in files:
            raise ValueError('Artifact entrypoint is missing')
        return record, root
