"""Native ULTRON operations reused from the standalone laboratory."""
from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import math
import os
import secrets
import stat
import subprocess
import sys
import tempfile
import threading
import time
import unicodedata
import uuid
import weakref
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

import psutil
from types import SimpleNamespace

BASE = Path(__file__).resolve().parent
SELF = sys.modules[__name__]
DATA = (Path(os.environ.get('LOCALAPPDATA', str(Path.home() / 'AppData/Local'))) / 'DIEF-JARVIS' / 'ultron').absolute()
MAX_FILE = 25 * 1024 * 1024
MAX_TOTAL = 100 * 1024 * 1024
MAX_FILES = 500
TOKEN_TTL = 3600
CONFIRM_TTL = 120
POWERSHELL = Path(os.environ.get('SystemRoot', 'C:/Windows')) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
# Commands deliberately return only aggregate numbers and boolean status.
COMMANDS = {
    'defender': "$s=Get-MpComputerStatus -ErrorAction Stop; [pscustomobject]@{enabled=[bool]$s.AntivirusEnabled; realtime=[bool]$s.RealTimeProtectionEnabled; signature_age=[int]$s.AntivirusSignatureAge}|ConvertTo-Json -Compress",
    'threats': "$s=@(Get-MpThreat -ErrorAction Stop); [pscustomobject]@{count=$s.Count; active=@($s|Where-Object {$_.IsActive}).Count}|ConvertTo-Json -Compress",
    'firewall': "$s=@(Get-NetFirewallProfile -ErrorAction Stop); [pscustomobject]@{count=$s.Count; enabled=@($s|Where-Object {$_.Enabled -eq 'True'}).Count}|ConvertTo-Json -Compress",
    'services': "$s=@(Get-Service -ErrorAction Stop); [pscustomobject]@{count=$s.Count; running=@($s|Where-Object {$_.Status -eq 'Running'}).Count}|ConvertTo-Json -Compress",
    'startup': "[pscustomobject]@{count=@(Get-CimInstance Win32_StartupCommand -ErrorAction Stop).Count}|ConvertTo-Json -Compress",
    'events': "try {$s=@(Get-WinEvent -FilterHashtable @{LogName='System';Level=1;StartTime=(Get-Date).AddDays(-1)} -MaxEvents 100 -ErrorAction Stop)} catch {if ($_.FullyQualifiedErrorId.Split(',')[0] -eq 'NoMatchingEventsFound') {$s=@()} else {exit 1}}; [pscustomobject]@{count=$s.Count; capped=($s.Count -eq 100)}|ConvertTo-Json -Compress",
}
FIELDS = {
    'defender': {'enabled': bool, 'realtime': bool, 'signature_age': int},
    'threats': {'count': int, 'active': int},
    'firewall': {'count': int, 'enabled': int},
    'services': {'count': int, 'running': int},
    'startup': {'count': int}, 'events': {'count': int, 'capped': bool},
}
STAGES = ['telemetry', *COMMANDS]
CAPABILITIES = {
    'diagnostics': True, 'monitor': True, 'backup': True, 'restore': True,
    'simulations': True, 'defender_scan': os.name == 'nt', 'sfc_verifyonly': False,
    'process_termination': False, 'os_remediation': False,
    'limitations': 'Observacoes locais nao garantem ausencia de malware. Operacoes do Windows exigem escopo fixo, confirmacao e permissao real; nao ha shell ou remediacao arbitraria.',
}


def now():
    return datetime.now(timezone.utc).isoformat()


def normalized(text):
    return ' '.join(unicodedata.normalize('NFKC', text).casefold().strip().rstrip('.!?').split())


def initial_state():
    return {
        'phase': 'idle',
        'scan': {'running': False, 'progress': 0, 'stage': 'idle', 'completed': 0,
                 'total': len(STAGES), 'started_at': None, 'finished_at': None},
        'telemetry': {}, 'findings': [], 'monitor': {'enabled': False, 'events': []},
        'vault': [], 'simulations': [], 'operations': [], 'capabilities': CAPABILITIES.copy(),
    }


STATE = initial_state()
TOKEN = secrets.token_urlsafe(32)
TOKEN_EXPIRES = time.monotonic() + TOKEN_TTL
PENDING = {}
CONVERSATIONS = {}
OPERATIONS = []
ACTION_LOCK = threading.Lock()
SCAN_TASK = None
MONITOR_TASK = None
TRANSITION_LOCKS = weakref.WeakKeyDictionary()


def transition_lock():
    # Each application/test event loop owns its own lock.
    loop = asyncio.get_running_loop()
    if loop not in TRANSITION_LOCKS:
        TRANSITION_LOCKS[loop] = asyncio.Lock()
    return TRANSITION_LOCKS[loop]


def telemetry():
    errors = []
    result = {}
    probes = {
        'cpu_percent': lambda: psutil.cpu_percent(interval=None),
        'memory_percent': lambda: psutil.virtual_memory().percent,
        'disk_percent': lambda: psutil.disk_usage(Path.home().anchor).percent,
        'process_count': lambda: len(psutil.pids()),
        'connection_count': lambda: len(psutil.net_connections(kind='inet')),
    }
    for key, probe in probes.items():
        try:
            value = probe()
            result[key] = value if isinstance(value, (int, float)) and math.isfinite(value) else None
        except (OSError, psutil.Error):
            result[key] = None
            errors.append(key)
    result['unavailable'] = errors
    return result


def powershell_summary(stage):
    if stage not in COMMANDS:
        raise ValueError('Unknown fixed diagnostic')
    if os.name != 'nt':
        return None
    try:
        # File-backed output bounds memory even if a Windows provider is noisy.
        with tempfile.TemporaryFile() as output:
            subprocess.run([str(POWERSHELL), '-NoLogo', '-NoProfile', '-NonInteractive',
                            '-Command', COMMANDS[stage]], stdout=output,
                           stderr=subprocess.DEVNULL, timeout=12, check=True,
                           creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            output.seek(0)
            raw = output.read(8193)
        if len(raw) > 8192:
            return None
        parsed = json.loads(raw.decode('utf-8-sig'))
        clean = {}
        for key, kind in FIELDS[stage].items():
            value = parsed[key]
            if type(value) is not kind or (kind is int and not 0 <= value <= 100000000):
                return None
            clean[key] = value
        return clean
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError):
        return None


def finding(stage, summary):
    severity = 'info'
    if summary is None:
        detail, severity = 'Consulta indisponivel ou sem permissao.', 'warning'
    else:
        detail = json.dumps(summary, ensure_ascii=True)
        if stage == 'defender' and (not summary['enabled'] or not summary['realtime']):
            severity = 'warning'
        if stage == 'threats' and summary['active']:
            severity = 'critical'
        if stage == 'firewall' and summary['enabled'] < summary['count']:
            severity = 'warning'
        if stage == 'events' and summary['count']:
            severity = 'warning'
    return {'id': stage, 'title': stage, 'detail': detail, 'severity': severity, 'source': 'read_only'}


async def scan():
    try:
        for index, stage in enumerate(STAGES):
            STATE['scan']['stage'] = stage
            if stage == 'telemetry':
                STATE['telemetry'] = await asyncio.to_thread(telemetry)
                STATE['scan']['telemetry']=dict(STATE['telemetry'])
                for key,label,threshold in [('cpu_percent','CPU',95),('memory_percent','Memoria',90),('disk_percent','Disco',90)]:
                    value=STATE['telemetry'].get(key)
                    if value is not None and value>=threshold:
                        STATE['findings'].append({'id':'resource:'+key,'title':label+' sob pressao','detail':json.dumps({'value':value,'threshold':threshold,'resource':label}),
                            'severity':'warning','source':'read_only'})
            else:
                try:
                    summary = await asyncio.to_thread(powershell_summary, stage)
                except Exception:
                    summary = None
                STATE['findings'].append(finding(stage, summary))
            STATE['scan'].update(completed=index + 1, progress=round((index + 1) * 100 / len(STAGES), 1))
        STATE['phase'] = 'active'
        STATE['scan']['stage'] = 'complete'
    finally:
        STATE['scan'].update(running=False, finished_at=now())


def monitor_events(sample):
    events = []
    for key, threshold in [('cpu_percent', 90), ('memory_percent', 90), ('disk_percent', 90)]:
        value = sample.get(key)
        if value is not None and value >= threshold:
            events.append({'at': now(), 'kind': key, 'severity': 'warning', 'value': value, 'threshold': threshold})
    for key in sample.get('unavailable', []):
        events.append({'at': now(), 'kind': key, 'severity': 'warning', 'detail': 'Leitura indisponivel.'})
    return events


async def monitor_loop():
    try:
        while STATE['monitor']['enabled']:
            sample = await asyncio.to_thread(telemetry)
            STATE['telemetry'] = sample
            STATE['monitor']['events'] = (STATE['monitor']['events'] + monitor_events(sample))[-100:]
            await asyncio.sleep(5)
    except Exception as error:
        STATE['monitor']['error'] = type(error).__name__
    finally:
        STATE['monitor']['enabled'] = False


def linked(path):
    info = path.lstat()
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, 'st_file_attributes', 0) & 0x400)


def check_chain(path):
    for component in [path, *path.parents]:
        if linked(component):
            raise ValueError('Links e pontos de redirecionamento nao sao permitidos.')


def canonical_path(path):
    path = Path(path)
    if not path.is_absolute():
        raise ValueError('Caminho absoluto obrigatorio.')
    # Inspect lexical prefixes before collapsing '..': never resolve through a
    # junction, including one that would disappear from the normalized path.
    prefix = Path(path.anchor)
    for part in path.parts[1:]:
        try:
            if linked(prefix):
                raise ValueError('Links nao permitidos.')
        except FileNotFoundError:
            pass
        prefix = prefix / part
    try:
        if linked(prefix):
            raise ValueError('Links nao permitidos.')
    except FileNotFoundError:
        pass
    return Path(os.path.abspath(path))


def excluded(relative):
    for part in relative.parts:
        name = part.casefold()
        if (name.startswith('.env') or name.split('.')[0] in {'config', 'configs', 'configuration'} or name in {
                '.git', '.ssh', '.aws', '.azure', '.config', '.netrc', '.npmrc', '.pypirc',
                'id_rsa', 'id_ed25519', 'id_ecdsa', 'login data', 'cookies',
                'node_modules', '__pycache__'}
                or any(word in name for word in ('credential', 'secret', 'token', 'password', 'passwd', 'private', 'apikey', 'api_key'))
                or name.endswith(('.pem', '.key', '.pfx', '.p12', '.kdbx'))):
            return True
    return False


def selected_files(source):
    source = canonical_path(source)
    if not source.is_absolute() or not source.is_dir():
        raise ValueError('Selecione uma pasta absoluta existente.')
    check_chain(source)
    data = canonical_path(DATA)
    if source == Path(source.anchor) or source == data or data in source.parents or source in data.parents:
        raise ValueError('Pasta raiz ou sobreposta ao cofre nao permitida.')
    files, total, visited = [], 0, 0
    def walk(directory):
        nonlocal total, visited
        with os.scandir(directory) as entries:
            for entry in entries:
                visited += 1
                if visited > 5000:
                    raise ValueError('Limite de entradas excedido.')
                path = Path(entry.path)
                relative = path.relative_to(source)
                if excluded(relative):
                    continue
                if linked(path):
                    raise ValueError('Links nao permitidos.')
                if entry.is_dir(follow_symlinks=False):
                    if len(relative.parts) > 32:
                        raise ValueError('Profundidade excedida.')
                    walk(path)
                elif entry.is_file(follow_symlinks=False):
                    # Windows DirEntry metadata omits the hard-link count.
                    info = path.stat(follow_symlinks=False)
                    if info.st_nlink > 1:
                        raise ValueError('Hard links nao permitidos.')
                    size = info.st_size
                    total += size
                    if size > MAX_FILE or total > MAX_TOTAL or len(files) >= MAX_FILES:
                        raise ValueError('Limite de backup excedido (25 MB/arquivo, 100 MB, 500 arquivos).')
                    files.append((path, relative, size))
                else:
                    raise ValueError('Somente arquivos regulares sao permitidos.')
    walk(source)
    return files, total


class WindowsHandles:
    """No-share-write/delete handles pin every ancestor against substitution."""

    def __init__(self):
        import ctypes
        from ctypes import wintypes
        self.ctypes = ctypes
        self.api = ctypes.WinDLL('kernel32', use_last_error=True)
        self.api.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                       wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        self.api.CreateFileW.restype = wintypes.HANDLE
        self.api.CloseHandle.argtypes = [wintypes.HANDLE]
        self.api.CloseHandle.restype = wintypes.BOOL
        self.api.GetFinalPathNameByHandleW.argtypes = [wintypes.HANDLE, wintypes.LPWSTR, wintypes.DWORD, wintypes.DWORD]
        self.api.GetFinalPathNameByHandleW.restype = wintypes.DWORD

        class Information(ctypes.Structure):
            _fields_ = [('attributes', wintypes.DWORD), ('creation', wintypes.FILETIME),
                        ('access', wintypes.FILETIME), ('write', wintypes.FILETIME),
                        ('volume', wintypes.DWORD), ('size_high', wintypes.DWORD),
                        ('size_low', wintypes.DWORD), ('links', wintypes.DWORD),
                        ('index_high', wintypes.DWORD), ('index_low', wintypes.DWORD)]
        self.Information = Information
        self.api.GetFileInformationByHandle.argtypes = [wintypes.HANDLE, ctypes.POINTER(Information)]
        self.api.GetFileInformationByHandle.restype = wintypes.BOOL

    def close(self, handle):
        self.api.CloseHandle(handle)

    def verify(self, handle, path, directory):
        info = self.Information()
        if not self.api.GetFileInformationByHandle(handle, self.ctypes.byref(info)):
            raise self.ctypes.WinError(self.ctypes.get_last_error())
        if info.attributes & 0x400 or bool(info.attributes & 0x10) != directory or (not directory and info.links != 1):
            raise ValueError('Destino irregular ou redirecionado.')
        buffer = self.ctypes.create_unicode_buffer(32768)
        length = self.api.GetFinalPathNameByHandleW(handle, buffer, len(buffer), 0)
        if not length or length >= len(buffer):
            raise ValueError('Destino nao verificavel.')
        actual = buffer.value
        if actual.startswith('\\\\?\\UNC\\'):
            actual = '\\\\' + actual[8:]
        elif actual.startswith('\\\\?\\'):
            actual = actual[4:]
        if os.path.normcase(os.path.abspath(actual)) != os.path.normcase(os.path.abspath(path)):
            raise ValueError('Destino fora do caminho fixado.')

    def open(self, path, directory):
        # FILE_READ_ATTRIBUTES, or GENERIC_WRITE for a new leaf. No SHARE_DELETE
        # or SHARE_WRITE: rename/removal/reparse conversion must fail while held.
        handle = self.api.CreateFileW(str(path), 0x80 if directory else 0x40000080,
                                     1 if directory else 0, None, 3 if directory else 1,
                                     0x02200000 if directory else 0x00200080, None)
        if handle == self.ctypes.c_void_p(-1).value:
            raise self.ctypes.WinError(self.ctypes.get_last_error())
        try:
            self.verify(handle, path, directory)
            return handle
        except BaseException:
            self.close(handle)
            raise

    def write(self, handle, content):
        import msvcrt
        fd = msvcrt.open_osfhandle(handle, os.O_WRONLY | os.O_BINARY)
        # Ownership transfers to the fd. The caller must not CloseHandle again.
        with os.fdopen(fd, 'wb') as stream:
            stream.write(content)


class ConfinedWriter:
    """Pin the entire destination chain and create exclusive, verified leaves.

    Failed operations deliberately retain incomplete vault folders. Path-based
    recursive cleanup or publication renames would undo the handle protection.
    """

    def __init__(self, root):
        self.root = canonical_path(root)
        self.pins = {}
        self.windows = WindowsHandles() if os.name == 'nt' else None
        if self.windows is None and (os.name != 'posix' or not hasattr(os, 'O_NOFOLLOW')
                                     or os.open not in os.supports_dir_fd or os.mkdir not in os.supports_dir_fd):
            raise ValueError('Escrita segura indisponivel nesta plataforma.')

    def __enter__(self):
        try:
            self._pin(self.root, create=True)
            return self
        except BaseException:
            self.__exit__(None, None, None)
            raise

    def __exit__(self, *args):
        for handle in reversed(list(self.pins.values())):
            if self.windows:
                self.windows.close(handle)
            else:
                os.close(handle)
        self.pins.clear()

    def _pin(self, path, create=False, exclusive=False):
        if path in self.pins:
            if exclusive:
                raise FileExistsError(str(path))
            self._verify_pin(path)
            return self.pins[path]
        if path == Path(path.anchor):
            if self.windows:
                handle = self.windows.open(path, True)
            else:
                handle = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        else:
            parent = self._pin(path.parent, create=create)
            if create:
                try:
                    if self.windows:
                        path.mkdir()
                    else:
                        os.mkdir(path.name, mode=0o700, dir_fd=parent)
                except FileExistsError:
                    if exclusive:
                        raise
            if self.windows:
                handle = self.windows.open(path, True)
            else:
                handle = os.open(path.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
        self.pins[path] = handle
        self._verify_pin(path)
        return handle

    def _verify_pin(self, path):
        handle = self.pins[path]
        if self.windows:
            self.windows.verify(handle, path, True)
        else:
            # dirfd prevents traversal; also fail closed if the pinned entry was
            # renamed/replaced instead of publishing into a detached directory.
            opened = os.fstat(handle)
            current = os.stat(path, follow_symlinks=False)
            if not stat.S_ISDIR(current.st_mode) or (opened.st_dev, opened.st_ino) != (current.st_dev, current.st_ino):
                raise ValueError('Diretorio substituido.')

    def directory(self, relative, exclusive=False):
        relative = safe_relative(relative)
        path = self.root / Path(*relative.parts)
        self._pin(path, create=True, exclusive=exclusive)
        return path

    def write(self, relative, content):
        relative = safe_relative(relative)
        target = self.root / Path(*relative.parts)
        parent = self._pin(target.parent, create=True)
        for path in self.pins:
            self._verify_pin(path)
        if self.windows:
            handle = self.windows.open(target, False)
            try:
                for path in self.pins:
                    self._verify_pin(path)
                self.windows.verify(handle, target, False)
            except BaseException:
                self.windows.close(handle)
                raise
            self.windows.write(handle, content)
        else:
            fd = os.open(target.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                         0o600, dir_fd=parent)
            try:
                info = os.fstat(fd)
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                    raise ValueError('Arquivo de destino irregular.')
                for path in self.pins:
                    self._verify_pin(path)
                with os.fdopen(fd, 'wb', closefd=False) as stream:
                    stream.write(content)
            finally:
                os.close(fd)


def safe_relative(value):
    if not isinstance(value, str) or not value or '\\' in value or ':' in value:
        raise ValueError('Caminho invalido no manifesto.')
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {'', '.', '..'} for part in value.split('/')) or len(path.parts) > 33:
        raise ValueError('Caminho invalido no manifesto.')
    for part in path.parts:
        if any(ord(c) < 32 or c in '<>"|?*' for c in part) or part.endswith((' ', '.')):
            raise ValueError('Nome invalido.')
        if part.split('.')[0].upper() in {'CON', 'PRN', 'AUX', 'NUL', *('COM' + str(i) for i in range(10)), *('LPT' + str(i) for i in range(10))}:
            raise ValueError('Nome reservado.')
    if excluded(path):
        raise ValueError('Conteudo excluido no manifesto.')
    return path


def read_bounded(path):
    check_chain(path)
    with path.open('rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink > 1:
            raise ValueError('Arquivo irregular.')
        check_chain(path)
        if os.name == 'nt':
            # Validate the opened handle, not just the path checked before open.
            import ctypes
            import msvcrt
            from ctypes import wintypes
            final_path = ctypes.windll.kernel32.GetFinalPathNameByHandleW
            final_path.argtypes = [wintypes.HANDLE, wintypes.LPWSTR, wintypes.DWORD, wintypes.DWORD]
            final_path.restype = wintypes.DWORD
            buffer = ctypes.create_unicode_buffer(32768)
            length = final_path(msvcrt.get_osfhandle(stream.fileno()), buffer, len(buffer), 0)
            if not length or length >= len(buffer):
                raise ValueError('Nao foi possivel verificar o arquivo aberto.')
            actual = buffer.value
            if actual.startswith('\\\\?\\UNC\\'):
                actual = '\\\\' + actual[8:]
            elif actual.startswith('\\\\?\\'):
                actual = actual[4:]
            if os.path.normcase(os.path.abspath(actual)) != os.path.normcase(os.path.abspath(path)):
                raise ValueError('Arquivo redirecionado durante leitura.')
        content = stream.read(MAX_FILE + 1)
    if len(content) > MAX_FILE:
        raise ValueError('Arquivo excede limite.')
    return content


def validate_backup(backup_id, fixture_root=None):
    if not isinstance(backup_id, str) or len(backup_id) != 32 or any(c not in '0123456789abcdef' for c in backup_id):
        raise ValueError('Identificador invalido.')
    folder = (fixture_root if fixture_root is not None else DATA / 'backups') / backup_id
    manifest_path = folder / 'manifest.json'
    raw = read_bounded(manifest_path)
    if len(raw) > 256 * 1024:
        raise ValueError('Manifesto excede limite.')
    manifest = json.loads(raw)
    entries = manifest['files']
    if manifest['id'] != backup_id or not isinstance(entries, list) or len(entries) > MAX_FILES:
        raise ValueError('Manifesto invalido.')
    seen, verified, total = set(), [], 0
    for entry in entries:
        relative = safe_relative(entry['path'])
        key = str(relative).casefold()
        if key in seen or any(key.startswith(other + '/') or other.startswith(key + '/') for other in seen):
            raise ValueError('Caminhos duplicados ou conflitantes.')
        seen.add(key)
        content = read_bounded(folder / 'files' / Path(*relative.parts))
        if type(entry['size']) is not int or len(content) != entry['size'] or hashlib.sha256(content).hexdigest() != entry['sha256']:
            raise ValueError('Integridade do backup invalida.')
        total += len(content)
        if total > MAX_TOTAL:
            raise ValueError('Limite total excedido.')
        verified.append((relative, content))
    return manifest, verified


def snapshot_fingerprint(verified, manifest=None):
    entries = sorted([{'path': relative.as_posix(), 'size': len(content),
                       'sha256': hashlib.sha256(content).hexdigest()}
                      for relative, content in verified], key=lambda item: item['path'])
    snapshot = {'files': entries, 'count': len(entries), 'bytes': sum(e['size'] for e in entries),
                'manifest': manifest}
    return hashlib.sha256(json.dumps(snapshot, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()


def source_snapshot(source):
    files, _ = selected_files(source)
    verified, total = [], 0
    for path, relative, _ in files:
        safe_relative(relative.as_posix())
        content = read_bounded(path)
        total += len(content)
        if total > MAX_TOTAL:
            raise ValueError('Limite total excedido.')
        verified.append((PurePosixPath(relative.as_posix()), content))
    # Detect additions/removals during the bounded read as well.
    after, _ = selected_files(source)
    if {r.as_posix() for _, r, _ in files} != {r.as_posix() for _, r, _ in after}:
        raise ValueError('Selecao mudou durante leitura.')
    return verified, snapshot_fingerprint(verified)


def require_snapshot(actual, expected):
    if expected is not None and not secrets.compare_digest(actual, expected):
        raise ValueError('Conteudo mudou desde a aprovacao.')


def backup(source, expected=None):
    verified, fingerprint = source_snapshot(source)
    require_snapshot(fingerprint, expected)
    backup_id = uuid.uuid4().hex
    entries, total = [], 0
    with ConfinedWriter(DATA) as writer:
        # Manifest is published last; incomplete directories have no valid
        # manifest and are retained rather than cleaned via mutable path names.
        writer.directory('backups/' + backup_id, exclusive=True)
        for relative, content in verified:
            total += len(content)
            writer.write('backups/' + backup_id + '/files/' + relative.as_posix(), content)
            entries.append({'path': relative.as_posix(), 'size': len(content), 'sha256': hashlib.sha256(content).hexdigest()})
        manifest = {'id': backup_id, 'created_at': now(), 'files': entries}
        writer.write('backups/' + backup_id + '/manifest.json', json.dumps(manifest).encode('utf-8'))
        return {'id': backup_id, 'created_at': manifest['created_at'], 'file_count': len(entries), 'bytes': total}


def restore(backup_id, expected=None, destination=None):
    manifest, verified = validate_backup(backup_id)
    require_snapshot(snapshot_fingerprint(verified, manifest), expected)
    # All paths and all bytes are verified before creating the recovery folder.
    recovery_name = 'DIEF-Recuperacao-' + uuid.uuid4().hex if destination else 'recovery-' + uuid.uuid4().hex
    with ConfinedWriter(destination or DATA) as writer:
        recovery = writer.directory(recovery_name, exclusive=True)
        for relative, content in verified:
            writer.write(recovery_name + '/' + relative.as_posix(), content)
        return {'recovery_path': str(recovery), 'file_count': len(verified)}


def vault_list():
    if not DATA.exists():
        return []
    records = []
    try:
        root = DATA / 'backups'
        if not root.exists():
            return []
        check_chain(root)
        with os.scandir(root) as entries:
            for index, entry in enumerate(entries):
                if index >= 1000:
                    break
                if len(entry.name) != 32:
                    continue
                try:
                    if any(c not in '0123456789abcdef' for c in entry.name):
                        continue
                    manifest_path = root / entry.name / 'manifest.json'
                    check_chain(manifest_path)
                    with manifest_path.open('rb') as stream:
                        raw = stream.read(256 * 1024 + 1)
                    if len(raw) > 256 * 1024:
                        continue
                    manifest = json.loads(raw)
                    files = manifest['files']
                    if manifest['id'] != entry.name or not isinstance(files, list) or len(files) > MAX_FILES:
                        continue
                    total = 0
                    for file in files:
                        safe_relative(file['path'])
                        if type(file['size']) is not int or not 0 <= file['size'] <= MAX_FILE:
                            raise ValueError('Tamanho invalido.')
                        total += file['size']
                    if total > MAX_TOTAL or not isinstance(manifest['created_at'], str) or len(manifest['created_at']) > 64:
                        continue
                    records.append({'id': entry.name, 'created_at': manifest['created_at'], 'file_count': len(files), 'bytes': total})
                except (OSError, ValueError, KeyError, TypeError):
                    continue
    except (OSError, ValueError):
        return []
    return records


def simulate(scenario):
    with tempfile.TemporaryDirectory(prefix='ultron-fixture-') as temporary:
        root = Path(temporary)
        if scenario == 'service_unavailable':
            result = {'service_available': False, 'finding': finding('services', None), 'observed': 'Fixture de servico indisponivel; nenhum servico consultado ou alterado.'}
        elif scenario == 'disk_pressure':
            events = monitor_events({'cpu_percent': 1, 'memory_percent': 2, 'disk_percent': 95, 'unavailable': []})
            result = {'events': events, 'observed': 'Disco de fixture em 95%; nenhum disco preenchido ou limpo.'}
        elif scenario == 'recovery_integrity':
            backup_id = uuid.uuid4().hex
            folder = root / backup_id
            (folder / 'files').mkdir(parents=True)
            content = b'ULTRON isolated fixture'
            fixture = folder / 'files/fixture.txt'
            fixture.write_bytes(content)
            (folder / 'manifest.json').write_text(json.dumps({'id': backup_id, 'files': [
                {'path': 'fixture.txt', 'size': len(content), 'sha256': hashlib.sha256(content).hexdigest()}
            ]}), encoding='utf-8')
            validate_backup(backup_id, root)
            fixture.write_bytes(b'corrupted fixture')
            try:
                validate_backup(backup_id, root)
            except ValueError:
                result = {'mismatch_detected': True, 'restore_blocked': True}
            else:
                raise ValueError('Fixture de integridade falhou.')
        else:
            raise ValueError('Cenario desconhecido.')
    return {'id': uuid.uuid4().hex, 'at': now(), 'scenario': scenario, 'simulated': True,
            'computer_effects': False, 'result': result}


class HTTPException(ValueError):
    def __init__(self, status_code, detail):
        super().__init__(detail)
        self.status_code = status_code


Command = Simulation = Monitor = Confirm = Conversation = SimpleNamespace


class Prepare(SimpleNamespace):
    def __init__(self, action, path=None, backup_id=None, destination=None):
        super().__init__(action=action, path=path, backup_id=backup_id, destination=destination)


async def state():
    STATE['telemetry'] = await asyncio.to_thread(telemetry)
    STATE['vault'] = await asyncio.to_thread(vault_list)
    STATE['operations'] = [dict(item) for item in OPERATIONS]
    from .ultron_tools import administrator
    elevated=administrator()
    STATE['capabilities'].update(administrator=elevated,cleanup_temp=os.name=='nt',integrity_verify=elevated,sfc_verifyonly=elevated,windows_repair=elevated,os_remediation=elevated)
    return STATE


async def command(payload: Command):
    async with transition_lock():
        return await command_transition(payload)


async def command_transition(payload):
    global SCAN_TASK
    text = normalized(payload.text)
    if text == 'ativar protocolo ultron':
        if STATE['scan']['running']:
            return {'accepted': True, 'already_running': True}
        STATE['phase'] = 'scanning'
        STATE['findings'] = []
        STATE['scan'] = {'running': True, 'progress': 0, 'stage': 'queued', 'completed': 0,
                         'total': len(STAGES), 'started_at': now(), 'finished_at': None}
        SCAN_TASK = asyncio.create_task(scan())
        return {'accepted': True}
    if text == 'desativar protocolo ultron':
        was_running = STATE['scan']['running']
        STATE['monitor']['enabled'] = False
        if MONITOR_TASK and not MONITOR_TASK.done():
            MONITOR_TASK.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await MONITOR_TASK
        if SCAN_TASK and not SCAN_TASK.done():
            SCAN_TASK.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await SCAN_TASK
        STATE['phase'] = 'idle'
        STATE['scan']['running'] = False
        if was_running:
            STATE['scan'].update(stage='stopped', finished_at=now())
        return {'accepted': True}
    raise HTTPException(400, 'Comando nao reconhecido; ativacao exige a frase exata.')


async def monitor(payload: Monitor):
    async with transition_lock():
        return await monitor_transition(payload)


async def monitor_transition(payload):
    global MONITOR_TASK
    STATE['monitor']['enabled'] = payload.enabled
    if payload.enabled and (MONITOR_TASK is None or MONITOR_TASK.done()):
        STATE['monitor'].pop('error', None)
        MONITOR_TASK = asyncio.create_task(monitor_loop())
    elif not payload.enabled and MONITOR_TASK and not MONITOR_TASK.done():
        MONITOR_TASK.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await MONITOR_TASK
    return STATE['monitor']


async def simulation(payload: Simulation):
    if payload.scenario not in {'service_unavailable', 'disk_pressure', 'recovery_integrity'}:
        raise HTTPException(400, 'Cenario desconhecido.')
    record = await asyncio.to_thread(simulate, payload.scenario)
    STATE['simulations'] = (STATE['simulations'] + [record])[-50:]
    return record


def prepare_action(payload):
    with ACTION_LOCK:
        expired = [key for key, value in PENDING.items() if value['expires'] <= time.monotonic()]
        for key in expired:
            del PENDING[key]
        if len(PENDING) >= 32:
            raise ValueError('Muitas confirmacoes pendentes.')
        if payload.destination is not None and (payload.action!='restore' or payload.destination!='desktop'):
            raise ValueError('Destino nao permitido.')
        if payload.action in {'cleanup_temp','defender_update','security_max','integrity_verify','windows_repair'} and payload.path is None and payload.backup_id is None:
            from .ultron_tools import prepare as prepare_tool
            prepared=prepare_tool(SELF,payload.action)
            details,args,fingerprint=prepared['details'],prepared['args'],prepared['fingerprint']
        elif payload.action in {'defender_quick', 'defender_full'} and payload.path is None and payload.backup_id is None:
            if os.name != 'nt' or not POWERSHELL.is_file() or STATE['phase'] == 'idle':
                raise ValueError('Defender indisponivel.')
            summary = powershell_summary('defender')
            if summary is None or not summary['enabled']:
                raise ValueError('Defender indisponivel ou sem permissao.')
            if any(item['state'] in {'running', 'uncertain'} for item in OPERATIONS):
                raise ValueError('Uma varredura ja esta em andamento.')
            details = {'scan_type': 'completa' if payload.action == 'defender_full' else 'rapida',
                       'effect': 'O Microsoft Defender pode colocar ameacas em quarentena conforme suas politicas atuais. A varredura completa pode demorar e consumir recursos.',
                       'scope': 'Nenhuma protecao, exclusao ou politica do Windows sera desativada.'}
            args = None
            fingerprint = None
        elif payload.action == 'backup' and payload.path and payload.backup_id is None:
            source = canonical_path(payload.path)
            verified, fingerprint = source_snapshot(source)
            details = {'path': str(source), 'file_count': len(verified), 'bytes': sum(len(c) for _, c in verified),
                       'exclusions': 'Credenciais, .env, .git, config, tokens e links excluidos; nomes de arquivos nao detectam todos os segredos.'}
            args = source
        elif payload.action == 'restore' and payload.backup_id and payload.path is None:
            manifest, verified = validate_backup(payload.backup_id)
            fingerprint = snapshot_fingerprint(verified, manifest)
            destination=None
            if payload.destination=='desktop':
                from .ultron_tools import desktop_path
                destination=canonical_path(desktop_path());check_chain(destination)
                if not destination.is_dir():raise ValueError('Area de trabalho indisponivel.')
            details = {'backup_id': payload.backup_id, 'file_count': len(verified), 'destination': 'Nova pasta na area de trabalho; originais preservados.' if destination else 'Nova pasta recovery-* no cofre; originais preservados.'}
            args = {'backup_id':payload.backup_id,'destination':destination}
        else:
            raise ValueError('Acao indisponivel ou parametros invalidos.')
        identifier = secrets.token_urlsafe(24)
        PENDING[identifier] = {'action': payload.action, 'args': args, 'fingerprint': fingerprint,
                               'expires': time.monotonic() + CONFIRM_TTL}
        return {'id': identifier, 'title': 'Confirmar ' + payload.action, 'details': details, 'expires_in': CONFIRM_TTL}


def confirm_action(identifier):
    with ACTION_LOCK:
        pending = PENDING.pop(identifier, None)
        if not pending or pending['expires'] <= time.monotonic():
            raise ValueError('Confirmacao vencida, desconhecida ou ja utilizada.')
        if pending['action']=='cleanup_temp':
            from .ultron_tools import cleanup
            if STATE['phase']=='idle':raise ValueError('Protocolo desativado.')
            return cleanup(SELF,pending['fingerprint'])
        if pending['action'] in {'defender_update','security_max','integrity_verify','windows_repair'}:
            from .ultron_tools import launch
            return launch(SELF,pending['action'])
        if pending['action'] in {'defender_quick', 'defender_full'}:
            if os.name != 'nt' or STATE['phase'] == 'idle' or any(item['state'] in {'running', 'uncertain'} for item in OPERATIONS):
                raise ValueError('Varredura indisponivel ou em andamento.')
            record = {'id': uuid.uuid4().hex, 'action': pending['action'], 'state': 'running',
                      'started_at': now(), 'message': 'Iniciando o Microsoft Defender.'}
            OPERATIONS.append(record)
            del OPERATIONS[:-20]
            launch_defender(record)
            return {'operation_id': record['id'], 'state': 'running'}
        if pending['action'] == 'backup':
            return backup(pending['args'], pending['fingerprint'])
        args=pending['args']
        return restore(args['backup_id'],pending['fingerprint'],args['destination'])


def launch_defender(record):
    threading.Thread(target=defender_operation, args=(record,), daemon=True, name='UltronDefender').start()


def defender_operation(record):
    scan_type = 'FullScan' if record['action'] == 'defender_full' else 'QuickScan'
    command = 'Start-MpScan -ScanType ' + scan_type + ' -ErrorAction Stop'
    try:
        subprocess.run([str(POWERSHELL), '-NoLogo', '-NoProfile', '-NonInteractive', '-Command', command],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3600, check=True,
                       creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        record.update(state='completed', message='Comando de varredura concluido pelo Defender. Consulte as deteccoes; isso nao garante ausencia de malware.')
    except subprocess.TimeoutExpired:
        record.update(state='uncertain', message='Tempo de acompanhamento excedido. O Defender pode continuar a varredura; confira Seguranca do Windows antes de iniciar outra.')
    except (OSError, subprocess.SubprocessError):
        record.update(state='failed', message='O Defender nao confirmou a varredura. Confira a permissao e a Seguranca do Windows.')
    finally:
        record['finished_at'] = now()


async def action_call(function, argument):
    try:
        return await asyncio.to_thread(function, argument)
    except (ValueError, OSError, KeyError, TypeError, RecursionError):
        # Never return provider errors, file contents, or exception paths.
        raise HTTPException(400, 'Acao rejeitada: parametros, limites, permissao ou integridade invalidos.') from None


async def prepare(payload: Prepare):
    return await action_call(prepare_action, payload)


async def confirm(payload: Confirm):
    return await action_call(confirm_action, payload.id)


async def conversation(payload: Conversation):
    from .ultron_dialogue import converse
    try:return await converse(SELF,payload)
    except (ValueError,OSError,KeyError):raise HTTPException(400,'Conversa indisponivel ou parametros invalidos.') from None
