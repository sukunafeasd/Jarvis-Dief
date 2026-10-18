"""Bounded newline JSON-RPC transport for the official Codex App Server."""
from __future__ import annotations

import asyncio
import ctypes
import json
import os
from pathlib import Path

from .windows_process import launch_windows

MAX_LINE = 1024 * 1024


class RpcError(RuntimeError):
    def __init__(self, error):
        self.code = error.get('code')
        self.message = str(error.get('message', 'App Server request failed'))
        super().__init__(self.message)


def elevated():
    if os.name == 'nt':
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    return hasattr(os, 'geteuid') and os.geteuid() == 0


def isolated_environment(home):
    # Do not inherit provider keys, Codex desktop session variables, or Python hooks.
    names = ('SystemRoot', 'WINDIR', 'COMSPEC', 'PATH', 'PATHEXT', 'TEMP', 'TMP',
             'LOCALAPPDATA', 'APPDATA', 'USERPROFILE', 'HOME', 'LANG')
    result = {key: os.environ[key] for key in names if key in os.environ}
    result['CODEX_HOME'] = str(home)
    return result


class AppServer:
    def __init__(self, executable, home, on_event, timeout=15):
        self.executable = str(executable)
        self.home = Path(home)
        self.on_event = on_event
        self.timeout = timeout
        self.process = None
        self.pending = {}
        self.serial = 0
        self.tasks = []
        self.write_lock = asyncio.Lock()
        self.closed = False

    async def start(self):
        argv = [self.executable, 'app-server', '--stdio',
            '-c', 'cli_auth_credentials_store="keyring"',
            '-c', 'sandbox_mode="workspace-write"',
            '-c', 'approval_policy="never"',
            '-c', 'windows.sandbox="unelevated"',
            '-c', 'shell_environment_policy.inherit="none"',
            '-c', 'shell_environment_policy.include_only=["PATH","SystemRoot","WINDIR","COMSPEC","PATHEXT"]']
        if os.name == 'nt':
            self.process = await launch_windows(argv, self.home, isolated_environment(self.home))
        else:
            if elevated():
                raise PermissionError('FORJA refuses a privileged Unix host')
            self.process = await asyncio.create_subprocess_exec(
                *argv, cwd=str(self.home), env=isolated_environment(self.home),
                stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE, limit=MAX_LINE)
        self.tasks = [asyncio.create_task(self._read()), asyncio.create_task(self._stderr())]
        try:
            result = await self.request('initialize', {
                'clientInfo': {'name': 'dief_forge', 'title': 'DIEF FORJA', 'version': '1.0.0'},
                'capabilities': {'experimentalApi': False}})
            await self.notify('initialized', {})
            return result
        except BaseException:
            await self.close()
            raise

    async def _send(self, message):
        payload = (json.dumps(message, ensure_ascii=True) + '\n').encode()
        if len(payload) > MAX_LINE:
            raise ValueError('Protocol request exceeds limit')
        async with self.write_lock:
            if self.closed or self.process is None or self.process.returncode is not None:
                raise ConnectionError('App Server is closed')
            self.process.stdin.write(payload)
            await asyncio.wait_for(self.process.stdin.drain(), self.timeout)

    async def request(self, method, params):
        self.serial += 1
        identifier = self.serial
        future = asyncio.get_running_loop().create_future()
        self.pending[identifier] = future
        try:
            await self._send({'id': identifier, 'method': method, 'params': params})
            return await asyncio.wait_for(future, self.timeout)
        finally:
            self.pending.pop(identifier, None)

    async def notify(self, method, params):
        await self._send({'method': method, 'params': params})

    async def _read(self):
        reason = 'App Server disconnected'
        try:
            while True:
                line = await self.process.stdout.readline()
                if not line:
                    break
                message = json.loads(line)
                if not isinstance(message, dict):
                    raise ValueError('Invalid protocol object')
                if 'method' in message:
                    if not isinstance(message['method'], str) or not isinstance(message.get('params', {}), dict):
                        raise ValueError('Invalid notification')
                    if 'id' in message:
                        # Never grant execution, permissions, or tools from an agent request.
                        await self._send({'id': message['id'], 'error': {
                            'code': -32601, 'message': 'Host tool/approval requests are not enabled'}})
                        self.on_event('forge/requestDenied', {'method': message['method']})
                    else:
                        self.on_event(message['method'], message.get('params', {}))
                elif 'id' in message:
                    if not isinstance(message['id'], (str, int)):
                        raise ValueError('Invalid response identifier')
                    future = self.pending.get(message['id'])
                    if future and not future.done():
                        if 'error' in message:
                            if not isinstance(message['error'], dict):
                                raise ValueError('Invalid error response')
                            future.set_exception(RpcError(message['error']))
                        elif 'result' in message:
                            future.set_result(message['result'])
                        else:
                            raise ValueError('Response has no result or error')
        except (ValueError, UnicodeError, OSError, RuntimeError):
            reason = 'App Server protocol failure'
        finally:
            for future in list(self.pending.values()):
                if not future.done():
                    future.set_exception(ConnectionError(reason))
            if not self.closed:
                self.on_event('forge/disconnected', {'message': reason})
                if self.process.returncode is None:
                    try:
                        self.process.terminate()
                    except ProcessLookupError:
                        pass

    async def _stderr(self):
        # Drain bounded chunks; never surface raw stderr, which may contain secrets.
        while await self.process.stderr.read(8192):
            pass

    async def close(self):
        if self.closed:
            return
        self.closed = True
        for future in list(self.pending.values()):
            if not future.done():
                future.set_exception(ConnectionError('App Server closed'))
        if self.process:
            self.process.stdin.close()
            try:
                await asyncio.wait_for(self.process.wait(), 2)
            except asyncio.TimeoutError:
                self.process.terminate()
                try:
                    await asyncio.wait_for(self.process.wait(), 2)
                except asyncio.TimeoutError:
                    self.process.kill()
                    await asyncio.wait_for(self.process.wait(), 2)
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        if self.process and hasattr(self.process, 'release'):
            await asyncio.to_thread(self.process.release)
