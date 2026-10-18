"""Start only signed OpenAI Codex with a verified standard-user token and job.

No shell/broker receives generated commands. The child starts suspended; token
verification and kill-on-close containment happen before its first instruction.
"""
from __future__ import annotations

import asyncio
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import subprocess
import threading

SPAWN_LOCK = threading.Lock()


def verify_official_executable(executable):
    path = Path(executable).resolve(strict=True)
    if path.name.lower() != 'codex.exe':
        raise PermissionError('Only the official codex.exe may be launched')
    # Static script, explicit executable path in an environment field, no shell interpolation.
    shell = Path(os.environ['SystemRoot']) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
    script = ('$s=Get-AuthenticodeSignature -LiteralPath $env:FORGE_VERIFY_EXE; '
              '@{status=[string]$s.Status;subject=[string]$s.SignerCertificate.Subject}|ConvertTo-Json -Compress')
    env = {k: os.environ[k] for k in ('SystemRoot', 'WINDIR', 'TEMP', 'TMP') if k in os.environ}
    env['FORGE_VERIFY_EXE'] = str(path)
    result = subprocess.run([str(shell), '-NoProfile', '-NonInteractive', '-Command', script],
                            env=env, capture_output=True, timeout=20, creationflags=0x08000000)
    record = json.loads(result.stdout.decode('utf-8-sig'))
    if result.returncode or record.get('status') != 'Valid' or not record.get('subject', '').startswith('CN="OpenAI OpCo, LLC"'):
        raise PermissionError('Codex requires a valid OpenAI Authenticode signature')
    return path


def standard_token():
    import win32api
    import win32security as security
    current = security.OpenProcessToken(win32api.GetCurrentProcess(), security.TOKEN_QUERY | security.TOKEN_DUPLICATE)
    linked = None
    try:
        original_sid = security.GetTokenInformation(current, security.TokenUser)[0]
        is_admin = bool(security.GetTokenInformation(current, security.TokenElevation))
        if is_admin:
            try:
                linked = security.GetTokenInformation(current, security.TokenLinkedToken)
            except Exception as error:
                raise PermissionError('Elevated host has no filtered linked user token') from error
        source = linked if linked is not None else current
        verify_token(source, original_sid)
        try:
            duplicate = security.DuplicateTokenEx(source, security.SecurityImpersonation,
                                                 security.TOKEN_ALL_ACCESS, security.TokenPrimary, None)
        except Exception as error:
            # Some UAC linked tokens are identification-only and cannot become primary.
            if not is_admin or getattr(error,'winerror',None)!=1346:raise
            duplicate = shell_standard_token(original_sid,security.GetTokenInformation(current,security.TokenSessionId))
        return duplicate, original_sid, is_admin
    finally:
        if linked is not None:
            linked.Close()
        current.Close()


def shell_standard_token(expected_sid,expected_session):
    import win32api
    import win32security as security
    user=ctypes.WinDLL('user32',use_last_error=True)
    user.GetShellWindow.restype=wintypes.HWND
    user.GetWindowThreadProcessId.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.DWORD)]
    window=user.GetShellWindow();pid=wintypes.DWORD()
    if not window or not user.GetWindowThreadProcessId(window,ctypes.byref(pid)):
        raise PermissionError('No interactive Windows shell is available')
    process=win32api.OpenProcess(0x1000,False,pid.value)
    token=None
    try:
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        query=kernel.QueryFullProcessImageNameW
        query.argtypes=[wintypes.HANDLE,wintypes.DWORD,wintypes.LPWSTR,ctypes.POINTER(wintypes.DWORD)]
        path=ctypes.create_unicode_buffer(32768);size=wintypes.DWORD(len(path))
        if not query(int(process),0,path,ctypes.byref(size)):
            raise ctypes.WinError(ctypes.get_last_error())
        if Path(path.value).resolve()!= (Path(os.environ['SystemRoot'])/'explorer.exe').resolve():
            raise PermissionError('The interactive shell is not Windows Explorer')
        token=security.OpenProcessToken(process,security.TOKEN_QUERY|security.TOKEN_DUPLICATE)
        verify_token(token,expected_sid)
        if security.GetTokenInformation(token,security.TokenSessionId)!=expected_session:
            raise PermissionError('Windows shell belongs to a different session')
        return security.DuplicateTokenEx(token,security.SecurityImpersonation,
                                         security.TOKEN_ALL_ACCESS,security.TokenPrimary,None)
    finally:
        if token is not None:token.Close()
        process.Close()


def verify_token(token, expected_sid):
    import win32security as security
    if security.GetTokenInformation(token, security.TokenElevation):
        raise PermissionError('Refusing an elevated Codex token')
    if security.GetTokenInformation(token, security.TokenUser)[0] != expected_sid:
        raise PermissionError('Codex token belongs to a different user')
    integrity = security.GetTokenInformation(token, security.TokenIntegrityLevel)
    if isinstance(integrity, tuple):
        integrity = integrity[0]
    if integrity.GetSubAuthority(integrity.GetSubAuthorityCount() - 1) > 0x2000:
        raise PermissionError('Codex integrity must be medium or lower')


class Startup(ctypes.Structure):
    _fields_ = [('cb', wintypes.DWORD), ('reserved', wintypes.LPWSTR), ('desktop', wintypes.LPWSTR),
                ('title', wintypes.LPWSTR), ('x', wintypes.DWORD), ('y', wintypes.DWORD),
                ('xsize', wintypes.DWORD), ('ysize', wintypes.DWORD), ('xchars', wintypes.DWORD),
                ('ychars', wintypes.DWORD), ('fill', wintypes.DWORD), ('flags', wintypes.DWORD),
                ('show', wintypes.WORD), ('reserved2size', wintypes.WORD), ('reserved2', ctypes.c_void_p),
                ('stdin', wintypes.HANDLE), ('stdout', wintypes.HANDLE), ('stderr', wintypes.HANDLE)]


class StartupEx(ctypes.Structure):
    _fields_ = [('startup', Startup), ('attributes', ctypes.c_void_p)]


class ProcessInfo(ctypes.Structure):
    _fields_ = [('process', wintypes.HANDLE), ('thread', wintypes.HANDLE),
                ('pid', wintypes.DWORD), ('tid', wintypes.DWORD)]


class PipeWriter:
    def __init__(self, fd):
        self.fd = fd
        self.buffer = b''
        self.closed = False

    def write(self, data):
        if self.closed:
            raise BrokenPipeError('Codex stdin is closed')
        self.buffer += data

    async def drain(self):
        data, self.buffer = self.buffer, b''
        def write():
            view = memoryview(data)
            while view:
                count = os.write(self.fd, view)
                view = view[count:]
        await asyncio.to_thread(write)

    def close(self):
        if not self.closed:
            self.closed = True
            os.close(self.fd)


class WindowsProcess:
    def __init__(self, process, job, pid, fds, loop, host_elevated):
        self.handle, self.job, self.pid = process, job, pid
        self.returncode = None
        self.stdin = PipeWriter(fds[0])
        self.stdout = asyncio.StreamReader(limit=1024 * 1024, loop=loop)
        self.stderr = asyncio.StreamReader(limit=1024 * 1024, loop=loop)
        self.exit = loop.create_future()
        self.security = {'child_elevated': False, 'integrity': 'medium_or_lower',
                         'host_elevated': host_elevated, 'job_kill_on_close': True}
        self.pumps = []
        for fd, reader in ((fds[1], self.stdout), (fds[2], self.stderr)):
            def pump(fd=fd, reader=reader):
                try:
                    while True:
                        chunk = os.read(fd, 8192)
                        if not chunk:
                            break
                        # At most one delivery per iteration; apply StreamReader backpressure.
                        delivered = threading.Event()
                        def feed(data=chunk):
                            reader.feed_data(data)
                            delivered.set()
                        loop.call_soon_threadsafe(feed)
                        if not delivered.wait(3):
                            break
                        while len(reader._buffer) > 1024 * 1024 and self.returncode is None:
                            threading.Event().wait(.01)
                except OSError:
                    pass
                finally:
                    os.close(fd)
                    loop.call_soon_threadsafe(reader.feed_eof)
            thread = threading.Thread(target=pump, name='ForgePipe', daemon=True)
            thread.start()
            self.pumps.append(thread)
        def watch():
            import win32event
            import win32process
            win32event.WaitForSingleObject(self.handle, -1)
            self.returncode = win32process.GetExitCodeProcess(self.handle)
            def done():
                if not self.exit.done():
                    self.exit.set_result(self.returncode)
            loop.call_soon_threadsafe(done)
        self.watcher = threading.Thread(target=watch, name='ForgeProcess', daemon=True)
        self.watcher.start()

    async def wait(self):
        return await asyncio.shield(self.exit)

    def terminate(self):
        import win32job
        win32job.TerminateJobObject(self.job, 1)

    kill = terminate

    def release(self):
        # Closing the job also kills lingering descendants after normal server exit.
        self.job.Close()
        for thread in (*self.pumps, self.watcher):
            thread.join(timeout=2)
        self.handle.Close()


def _spawn_inner(argv, cwd, env, loop):
    import msvcrt
    import win32api
    import win32job
    import win32security
    from .files import check_chain
    path = verify_official_executable(check_chain(argv[0]))
    token, sid, host_admin = standard_token()
    fds = []
    job = process_handle = None
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    advapi = ctypes.WinDLL('advapi32', use_last_error=True)
    init = kernel.InitializeProcThreadAttributeList
    init.argtypes = [ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(ctypes.c_size_t)]
    update = kernel.UpdateProcThreadAttribute
    update.argtypes = [ctypes.c_void_p, wintypes.DWORD, ctypes.c_size_t, ctypes.c_void_p,
                       ctypes.c_size_t, ctypes.c_void_p, ctypes.c_void_p]
    kernel.DeleteProcThreadAttributeList.argtypes = [ctypes.c_void_p]
    create = advapi.CreateProcessAsUserW
    create.argtypes = [wintypes.HANDLE, wintypes.LPCWSTR, wintypes.LPWSTR, ctypes.c_void_p,
                       ctypes.c_void_p, wintypes.BOOL, wintypes.DWORD, ctypes.c_void_p,
                       wintypes.LPCWSTR, ctypes.POINTER(StartupEx), ctypes.POINTER(ProcessInfo)]
    create_current = kernel.CreateProcessW
    create_current.argtypes = create.argtypes[1:]
    with_token = advapi.CreateProcessWithTokenW
    with_token.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPWSTR,
                           wintypes.DWORD, ctypes.c_void_p, wintypes.LPCWSTR,
                           ctypes.POINTER(StartupEx), ctypes.POINTER(ProcessInfo)]
    attributes = None
    info = ProcessInfo()
    try:
        stdin_read, stdin_write = os.pipe()
        stdout_read, stdout_write = os.pipe()
        stderr_read, stderr_write = os.pipe()
        fds = [stdin_read, stdin_write, stdout_read, stdout_write, stderr_read, stderr_write]
        size = ctypes.c_size_t()
        init(None, 1, 0, ctypes.byref(size))
        attributes = ctypes.create_string_buffer(size.value)
        if not init(attributes, 1, 0, ctypes.byref(size)):
            raise ctypes.WinError(ctypes.get_last_error())
        handles = (wintypes.HANDLE * 3)(*[msvcrt.get_osfhandle(fd) for fd in (stdin_read, stdout_write, stderr_write)])
        if not update(attributes, 0, 0x20002, handles, ctypes.sizeof(handles), None, None):
            raise ctypes.WinError(ctypes.get_last_error())
        startup = StartupEx()
        startup.startup.cb = ctypes.sizeof(startup)
        startup.startup.flags = 0x100
        startup.startup.stdin, startup.startup.stdout, startup.startup.stderr = handles
        startup.attributes = ctypes.cast(attributes, ctypes.c_void_p)
        environment = ctypes.create_unicode_buffer('\0'.join(k + '=' + v for k, v in sorted(env.items())) + '\0\0')
        flags = 0x08000000 | 0x400 | 0x4 | 0x80000  # hidden, Unicode, suspended, extended startup
        command = ctypes.create_unicode_buffer(subprocess.list2cmdline([str(path), *argv[1:]]))
        with SPAWN_LOCK:
            for fd in (stdin_read, stdout_write, stderr_write):
                os.set_inheritable(fd, True)
            try:
                if host_admin:
                    success = create(int(token), str(path), command, None, None, True, flags,
                                     environment, str(cwd), ctypes.byref(startup), ctypes.byref(info))
                else:
                    success = create_current(str(path), command, None, None, True, flags,
                                             environment, str(cwd), ctypes.byref(startup), ctypes.byref(info))
                if not success and ctypes.get_last_error() == 1314:
                    command = ctypes.create_unicode_buffer(subprocess.list2cmdline([str(path), *argv[1:]]))
                    success = with_token(int(token), 0, str(path), command, flags, environment,
                                         str(cwd), ctypes.byref(startup), ctypes.byref(info))
                if not success:
                    raise ctypes.WinError(ctypes.get_last_error())
            finally:
                for fd in (stdin_read, stdout_write, stderr_write):
                    os.set_inheritable(fd, False)
        process_handle = win32api.OpenProcess(0x1FFFFF, False, info.pid)
        child_token = win32security.OpenProcessToken(process_handle, win32security.TOKEN_QUERY)
        try:
            verify_token(child_token, sid)
        finally:
            child_token.Close()
        job = win32job.CreateJobObject(None, '')
        settings = win32job.QueryInformationJobObject(job, win32job.JobObjectExtendedLimitInformation)
        settings['BasicLimitInformation']['LimitFlags'] |= win32job.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        win32job.SetInformationJobObject(job, win32job.JobObjectExtendedLimitInformation, settings)
        win32job.AssignProcessToJobObject(job, process_handle)
        for fd in (stdin_read, stdout_write, stderr_write):
            os.close(fd)
            fds.remove(fd)
        kernel.ResumeThread.argtypes = [wintypes.HANDLE]
        if kernel.ResumeThread(info.thread) == 0xFFFFFFFF:
            raise ctypes.WinError(ctypes.get_last_error())
        result = WindowsProcess(process_handle, job, info.pid, (stdin_write, stdout_read, stderr_read), loop, host_admin)
        process_handle = job = None
        fds.clear()
        return result
    except BaseException:
        if info.process:
            kernel.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
            kernel.TerminateProcess(info.process, 1)
        raise
    finally:
        token.Close()
        if attributes is not None:
            kernel.DeleteProcThreadAttributeList(attributes)
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        for handle in (info.process, info.thread):
            if handle:
                kernel.CloseHandle(handle)
        for fd in fds:
            os.close(fd)
        if job is not None:
            job.Close()
        if process_handle is not None:
            process_handle.Close()


async def launch_windows(argv, cwd, env):
    task = asyncio.create_task(asyncio.to_thread(_spawn, argv, cwd, env, asyncio.get_running_loop()))
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        process = await task
        process.terminate()
        process.stdin.close()
        await process.wait()
        await asyncio.to_thread(process.release)
        raise
    except Exception as error:
        raise PermissionError('Verified standard-user Codex launch failed: ' + type(error).__name__) from error


def _spawn(argv, cwd, env, loop):
    from .files import pinned
    with pinned(argv[0]):
        return _spawn_inner(argv, cwd, env, loop)
