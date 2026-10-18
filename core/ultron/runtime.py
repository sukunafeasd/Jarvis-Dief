"""Synchronous host contract backed by one persistent asyncio worker.

The host records final user messages with strictly increasing integer serials.
Only the host supplies user_text/user_turn; neither comes from model arguments.
"""
from __future__ import annotations

import asyncio
import copy
from concurrent.futures import CancelledError, ThreadPoolExecutor
from contextlib import nullcontext
from functools import partial
import importlib.util
from pathlib import Path
import sys
import threading
import time
import uuid

from core.bounded_work import BoundedWork
from . import ultron_dialogue as dialogue


SAFE_REQUESTS = frozenset({
    'status', 'diagnostico', 'diagnóstico', 'como esta o pc', 'como está o pc',
    'o que encontrou', 'verifique o computador', 'analise o computador',
    'atualize o diagnostico', 'atualize o diagnóstico',
})


def rejected(message):
    return {'accepted': False, 'mode': 'rejected', 'speech': message}


class _DaemonExecutor(ThreadPoolExecutor):
    """Keep service/dialogue to_thread calls off non-daemon executor workers."""
    def __init__(self):
        super().__init__(max_workers=4)
        self.pool = BoundedWork(workers=4, capacity=16, name='UltronQuery')

    def submit(self, function, /, *args, **kwargs):
        return self.pool.submit(partial(function, *args, **kwargs))

    def shutdown(self, wait=True, *, cancel_futures=False):
        self.pool.close()
        super().shutdown(wait=False, cancel_futures=True)


class Runtime:
    def __init__(self):
        # Independent module globals retain the vetted service's stateful logic.
        self._module_name = __package__ + '._service_' + uuid.uuid4().hex
        spec = importlib.util.spec_from_file_location(
            self._module_name, Path(__file__).with_name('ultron_service.py'))
        self._service = importlib.util.module_from_spec(spec)
        sys.modules[self._module_name] = self._service
        try:
            spec.loader.exec_module(self._service)
        except BaseException:
            sys.modules.pop(self._module_name, None)
            raise
        self._conversation_id = uuid.uuid4().hex
        self._last_turn = -1
        self._pending_turn = None
        self._activation_offer = None
        self._snapshot_serial = 0
        self._gate = threading.RLock()
        self._pending = set()
        self._closed = False
        self._ready = threading.Event()
        self._thread = threading.Thread(target=self._worker, name='UltronRuntime', daemon=True)
        self._thread.start()
        self._ready.wait()

    def _worker(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._executor = _DaemonExecutor()
        self._loop.set_default_executor(self._executor)
        self._calls = asyncio.Lock()
        self._ready.set()
        try:
            self._loop.run_forever()
        finally:
            pending = asyncio.all_tasks(self._loop)
            for task in pending:
                task.cancel()
            self._loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            self._loop.run_until_complete(self._loop.shutdown_asyncgens())
            self._loop.run_until_complete(self._loop.shutdown_default_executor())
            self._loop.close()
            sys.modules.pop(self._module_name, None)

    async def _invoke(self, function, args):
        # Calls remain serialized, but waiting callers never hold the close gate.
        async with self._calls:
            if self._closed:raise RuntimeError('ULTRON runtime is closed.')
            return await function(*args)

    def _finished(self, future):
        with self._gate:
            self._pending.discard(future)

    def _call(self, function, *args):
        if threading.current_thread() is self._thread:
            raise RuntimeError('Synchronous ULTRON calls cannot run on its worker.')
        with self._gate:
            if self._closed:
                raise RuntimeError('ULTRON runtime is closed.')
            future = asyncio.run_coroutine_threadsafe(self._invoke(function, args), self._loop)
            self._pending.add(future)
            future.add_done_callback(self._finished)
        try:
            result=future.result()
            with self._gate:
                if self._closed:raise RuntimeError('ULTRON runtime is closed.')
            return result
        except CancelledError:
            if self._closed:
                raise RuntimeError('ULTRON runtime is closed.') from None
            raise

    def command(self, text, user_text=None, *, user_turn=None, authorization=None):
        """Return a result dict. user_turn is a host-recorded monotonic int.

        Explicit commands must match the whole current user utterance (optional
        Jarvis prefix, case/spacing/terminal punctuation normalized). Safe status
        requests can be model-generated and never affect pending confirmations.
        authorization() returns a host context manager that validates the captured
        context under its RLock. It runs on this runtime's worker and holds the
        host lock through dialogue admission/commit, never through snapshot().
        Omit it only for trusted direct calls; production tools must supply it.
        """
        return self._call(self._command, text, user_text, user_turn, authorization)

    async def _command(self, text, user_text, user_turn, authorization):
        try:
            with authorization() if authorization is not None else nullcontext():
                return await self._admitted_command(text, user_text, user_turn)
        except ValueError:
            return rejected('O contexto do usuario mudou; este comando nao foi autorizado.')

    async def _admitted_command(self, text, user_text, user_turn):
        if not isinstance(text, str) or not text.strip() or len(text) > 4096:
            return rejected('Comando ULTRON invalido.')
        clean = dialogue.intent(text)
        explicit = (isinstance(user_text, str) and bool(user_text.strip())
                    and len(user_text) <= 4096 and clean == dialogue.intent(user_text))
        if not explicit:
            if clean in SAFE_REQUESTS:
                if self._service.STATE['scan']['running']:
                    return {'accepted':True,'mode':'scan_wait',
                            'speech':'A analise ainda esta em andamento, senhor. Os dados disponiveis sao parciais; aguarde a conclusao das consultas.'}
                return {'accepted': True, 'mode': 'diagnostic',
                        'speech': 'Consulte as observacoes do snapshot ULTRON; nenhuma acao foi iniciada.'}
            return rejected('O comando deve corresponder ao texto real do usuario neste turno.')
        if type(user_turn) is not int or user_turn < 0:
            return rejected('Falta o serial do turno real registrado pelo Jarvis.')
        if user_turn <= self._last_turn:
            return rejected('Este turno ja foi consumido ou esta desatualizado.')
        self._last_turn = user_turn
        conversation = self._service.CONVERSATIONS.get(self._conversation_id, {})
        pending = conversation.get('pending')
        from core.protocol_commands import protocol_clarification,normalize,YES
        offer=self._activation_offer
        self._activation_offer=None
        activation_confirmed=bool(offer and user_turn==offer['turn']+1
            and time.monotonic()-offer['at']<=120 and normalize(user_text) in YES)
        if protocol_clarification(user_text)==('ultron','enter'):
            dialogue.discard(self._service,pending)
            conversation['pending']=None;self._pending_turn=None
            self._activation_offer={'turn':user_turn,'at':time.monotonic()}
            return {'accepted':True,'mode':'activation_question','user_turn':user_turn,
                    'speech':'Quer ativar o protocolo ULTRON, senhor? Vou iniciar somente o diagnostico, sem limpeza ou reparo.'}
        # An intervening recorded message may never have called this tool.
        # Such a gap invalidates the question rather than authorizing a later yes.
        if pending and user_turn != self._pending_turn + 1:
            dialogue.discard(self._service, pending)
            conversation['pending'] = None
            pending = None
            self._pending_turn = None
        reply_to = pending if self._pending_turn is not None and user_turn > self._pending_turn else None
        payload = self._service.Conversation(
            text='ativar protocolo ultron' if activation_confirmed else user_text,
            conversation_id=self._conversation_id, reply_to=reply_to)
        try:
            result = await dialogue.converse(self._service, payload)
        except (ValueError, OSError, KeyError, TypeError):
            result = rejected('Acao ULTRON indisponivel; revise o estado e faca um novo pedido.')
        if result.get('confirmation_id'):
            self._pending_turn = user_turn
        elif not self._service.CONVERSATIONS.get(self._conversation_id, {}).get('pending'):
            self._pending_turn = None
        result.setdefault('accepted', True)
        result['user_turn'] = user_turn
        return copy.deepcopy(result)

    def snapshot(self):
        """Detached JSON-compatible state; refreshes telemetry, vault and operations."""
        return self._call(self._snapshot)

    async def _snapshot(self):
        state = await self._service.state()
        result = copy.deepcopy(state)
        conversation = self._service.CONVERSATIONS.get(self._conversation_id, {})
        pending = self._service.PENDING.get(conversation.get('pending'))
        result['confirmation'] = ({'pending': True, 'prepared_user_turn': self._pending_turn}
                                  if pending and pending['expires'] > time.monotonic()
                                  else {'pending': False})
        result['last_user_turn'] = self._last_turn
        self._snapshot_serial += 1
        result['snapshot_serial'] = self._snapshot_serial
        return result

    async def _shutdown(self):
        tasks = [task for task in (self._service.SCAN_TASK, self._service.MONITOR_TASK) if task]
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        self._service.STATE['monitor']['enabled'] = False
        self._service.PENDING.clear()
        self._service.CONVERSATIONS.clear()

    def close(self):
        """Idempotent shutdown; Windows operations already accepted may continue."""
        if threading.current_thread() is self._thread:
            raise RuntimeError('Close ULTRON from the host thread.')
        with self._gate:
            if self._closed:
                return
            self._closed = True
            for future in list(self._pending):
                future.cancel()
            self._executor.shutdown(wait=False, cancel_futures=True)
            future = asyncio.run_coroutine_threadsafe(self._shutdown(), self._loop)
        try:
            future.result(timeout=5)
        finally:
            self._loop.call_soon_threadsafe(self._loop.stop)
            self._thread.join(timeout=5)
        if self._thread.is_alive():
            raise RuntimeError('ULTRON worker shutdown timed out.')
