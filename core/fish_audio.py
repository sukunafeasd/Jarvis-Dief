"""Fish Audio voice with protected credentials and cancellable PCM delivery."""
import asyncio
import re
import httpx
import hashlib
import json
import time
from core import integration_tokens

VOICE_ID='82d13948027e4be69892dd3d0104e681'
ENDPOINT='https://api.fish.audio/v1/tts'
VERIFIED=None
PCM_BYTES_PER_SECOND = 48000  # PCM16, mono, 24 kHz; no effects or gain changes.
PCM_CHUNK_BYTES = 2400
MAX_SEGMENT_CHARS = 400
MIN_SEGMENT_CHARS = 80
MAX_TEXT_CHARS = 12800
MAX_AUDIO_CHUNKS = 20
MAX_STAGED_CHUNKS = 200  # Ten seconds of untouched PCM ahead of the device queue.
TEXT_IDLE_SECONDS = .35
ABBREVIATIONS = {'sr','sra','dr','dra','prof','etc'}
SOURCE_TIMEOUT_SECONDS = 15.  # Bound silent connection/read stalls per segment.
QUEUE_TIMEOUT_SECONDS = 5.
SEGMENT_TIMEOUT_SECONDS = 90.


def identity():
    return hashlib.sha256(json.dumps({'settings':settings(),'token':integration_tokens.read('fish_audio')},sort_keys=True).encode()).hexdigest()


def settings():
    from memory.config_manager import get_plugin_config
    return get_plugin_config('fish_audio')


def enabled():
    from memory.config_manager import get_plugin_enabled,load_api_keys
    try:return get_plugin_enabled('fish_audio') and load_api_keys().get('speech_provider','fish_audio')=='fish_audio' and bool(integration_tokens.read('fish_audio').get('token'))
    except Exception:return False


def selected():
    """Return whether Fish is usable as the selected speech provider.

    A fresh installation has no personal Fish credential. Treating its default
    voice id as a configured voice used to suppress Gemini audio and left the
    assistant visibly replying in complete silence.
    """
    from memory.config_manager import load_api_keys
    try:
        provider=load_api_keys().get('speech_provider','fish_audio')
        return provider=='fish_audio' and bool(integration_tokens.read('fish_audio').get('token'))
    except Exception:
        return False


def status():
    try:configured=bool(integration_tokens.read('fish_audio').get('token'));verified=configured and VERIFIED==identity()
    except Exception:configured=False;verified=False
    return {'ok':True,'configured':configured,
            'connected':verified,'verified':verified,'voice_id':settings().get('voice_id') or VOICE_ID,
            'account_required':True,'message':'Voz Fish Audio; a chave fica protegida neste computador.'}


async def pcm(text):
    from core.speech_text import speech_text
    text=speech_text(text)
    if not text.strip() or len(text)>1800:
        raise ValueError('Texto Fish vazio ou acima do limite; segmente antes da sintese.')
    token=integration_tokens.read('fish_audio').get('token')
    if not token:raise ValueError('Configure a chave Fish Audio em Conexoes.')
    config=settings()
    voice=config.get('voice_id') or VOICE_ID
    if not re.fullmatch(r'[a-fA-F0-9]{32}',voice):raise ValueError('ID de voz Fish Audio invalido.')
    body={'text':text,'reference_id':voice,'format':'pcm','sample_rate':24000,
          'latency':'normal','chunk_length':300,'normalize':False}
    async with httpx.AsyncClient(timeout=httpx.Timeout(SOURCE_TIMEOUT_SECONDS,connect=10),follow_redirects=False) as client:
        async with client.stream('POST',ENDPOINT,headers={'Authorization':'Bearer '+token,'model':config.get('model') or 's2.1-pro-free'},json=body) as response:
            if response.status_code!=200:
                raise ValueError('Fish Audio recusou a sintese (HTTP '+str(response.status_code)+'). Confira chave, saldo e acesso a voz.')
            content_type=response.headers.get('content-type','').lower()
            if any(kind in content_type for kind in ('json','text/','mpeg','wav','ogg')):
                raise ValueError('Fish Audio retornou formato diferente de PCM.')
            buffer=bytearray();total=0;checked=False
            async for data in response.aiter_bytes():
                buffer.extend(data);total+=len(data)
                if total>12*1024*1024:raise ValueError('Audio Fish acima do limite.')
                if not checked and len(buffer)>=12:
                    if buffer.startswith((b'RIFF',b'ID3',b'OggS',b'fLaC')):
                        raise ValueError('Fish Audio retornou um container em vez de PCM.')
                    checked=True
                while len(buffer)>=PCM_CHUNK_BYTES:
                    yield bytes(buffer[:PCM_CHUNK_BYTES]);del buffer[:PCM_CHUNK_BYTES]
            if len(buffer)%2:raise ValueError('PCM incompleto retornado pelo provedor.')
            if not checked and buffer.startswith((b'RIFF',b'ID3',b'OggS',b'fLaC')):
                raise ValueError('Fish Audio retornou um container em vez de PCM.')
            if buffer:yield bytes(buffer)
            if not total:raise ValueError('Fish Audio retornou audio vazio.')


def verify(values=None):
    global VERIFIED
    async def test():
        count=0
        async for data in pcm('Bem-vindo, senhor.'):
            count+=len(data)
        return count
    count=asyncio.run(test())
    if count:VERIFIED=identity()
    return bool(count),'Voz respondeu com PCM de 24 kHz. Chave protegida neste PC.'


class FishVoiceSession:
    def __init__(self,owner):
        self.owner=owner;self.buffer='';self.queue=asyncio.Queue(maxsize=32)
        self.task=None;self.closed=False;self.cursor=0.;self.epoch=owner._response_epoch
        self.loop=asyncio.get_running_loop()
        self._idle=None;self._flush=False;self._failed=False
        self._queued_chars=0;self._generation=0;self._retired=set()
        self._wake=asyncio.Event();self._streaming=False
        self._started_text=False

    @property
    def pending(self):
        return bool(self.buffer or not self.queue.empty() or self.task and not self.task.done())

    @property
    def synthesizing(self):
        return bool(not self.queue.empty() or self.task and not self.task.done())

    def feed(self,text,flush=False,incremental=False):
        if self.closed or self.owner._manual_rest:return
        if not self.pending:self._started_text=False
        if self.epoch!=self.owner._response_epoch:
            self._clear(self.owner._response_epoch)
        if self._failed:
            # Stream fragments belong to the failed response. Only a new literal
            # or the receiver's explicit response boundary permits recovery.
            if flush and text.strip() and not self.pending:self.reset_failure()
            else:return
        if self._queued_chars+len(self.buffer)+len(text)>MAX_TEXT_CHARS:
            self._clear(self.epoch)
            self._failed=True
            self.owner.ui.write_log('SYS: Limite da fila Fish atingido; fala encerrada. Resposta disponivel na conversa.')
            return
        self._streaming=incremental
        self.buffer=self.buffer+text if incremental else (self.buffer+' '+text).strip()
        self._flush=self._flush or flush
        self._fill_queue()
        self._start_worker()
        if self._idle:self._idle.cancel();self._idle=None
        if self.buffer and not self._flush:
            self._idle=self.loop.call_later(TEXT_IDLE_SECONDS,self._idle_flush,self.epoch,self._generation)

    def _segment_end(self):
        limit=min(MAX_SEGMENT_CHARS,len(self.buffer))
        ends=[]
        for match in re.finditer(r'[.!?]+(?:["\')\]]*)(?=\s|$)',self.buffer):
            if match.end()>limit:break
            prefix=self.buffer[:match.start()]
            word=prefix.rsplit(' ',1)[-1].lower()
            if not self._flush and match.end()==len(self.buffer) and word[-1:].isdigit() and match.group()=='.':
                continue
            if match.group().startswith('.') and (word in ABBREVIATIONS or len(word)==1):
                continue
            ends.append(match.end())
        suitable=[end for end in ends if end>=MIN_SEGMENT_CHARS]
        if self._streaming and not self._flush and not self._started_text:
            opening=next((end for end in ends if end>=12),None)
            if opening is not None:return opening
        if suitable:return suitable[-1]
        if self._flush or len(self.buffer)>=MAX_SEGMENT_CHARS:
            if ends:return ends[-1]
            if limit==len(self.buffer) and (self._flush or not self._streaming):return limit
            boundary=self.buffer.rfind(' ',0,limit+1)
            return boundary if boundary>0 else (0 if self._streaming and not self._flush and limit==len(self.buffer) else limit)
        return 0

    def _open_terminal(self):
        match=re.search(r'(?:^|\s)([^\s]+)\.\s*$',self.buffer)
        if not match:return False
        word=match.group(1).lower()
        return word[-1:].isdigit() or word in ABBREVIATIONS or len(word)==1

    def _fill_queue(self):
        while self.buffer and not self.queue.full():
            end=self._segment_end()
            if not end:break
            sentence=self.buffer[:end].strip()
            self.buffer=self.buffer[end:]
            if not sentence:continue
            self._started_text=True
            self.queue.put_nowait((self.epoch,sentence))
            self._wake.set()
            self._queued_chars+=len(sentence)
        if not self.buffer:self._flush=False

    def _start_worker(self):
        if not self.closed and not self.queue.empty() and (self.task is None or self.task.done()):
            self.task=asyncio.create_task(self._work())

    def _idle_flush(self,epoch,generation):
        if self.closed or epoch!=self.owner._response_epoch or generation!=self._generation:return
        self._idle=None
        if self._streaming and (not re.search(r'[.!?]["\')\]]*\s*$',self.buffer) or self._open_terminal()):
            return
        self._flush=True
        self._fill_queue();self._start_worker()

    def _clear(self,epoch):
        self._generation+=1
        self.buffer='';self.cursor=0.;self.epoch=epoch;self._flush=False;self._failed=False
        self._streaming=False;self._started_text=False;self._wake.set()
        if self._idle:self._idle.cancel();self._idle=None
        while not self.queue.empty():self.queue.get_nowait();self.queue.task_done()
        self._queued_chars=0
        if self.task and not self.task.done():
            self.task.cancel();self._retired.add(self.task)
            self.task.add_done_callback(self._retired.discard)
        self.task=None

    def begin_turn(self):
        """Parent calls at a new response boundary, after prior audio has drained."""
        if self.pending:raise RuntimeError('A fala anterior ainda esta pendente.')
        self._clear(self.owner._response_epoch)

    def reset_failure(self):
        """Allow a new server response without rebasing the presentation clock."""
        if not self.closed:
            self._failed=False

    def cancel(self):
        epoch=self.owner._response_epoch
        generation=self._generation
        def clear():
            # A delayed cross-thread cancellation must not erase a newer reply.
            if generation==self._generation:
                self._clear(epoch)
        try:same_loop=asyncio.get_running_loop() is self.loop
        except RuntimeError:same_loop=False
        if same_loop:clear()
        else:self.loop.call_soon_threadsafe(clear)

    async def _deliver(self,epoch,text,source,enqueue=None):
        started=time.monotonic();first_audio=None
        generation=self._generation
        first=True;anchor=self.cursor;received=False;buffer=bytearray();total=0
        remaining=SEGMENT_TIMEOUT_SECONDS
        send=enqueue or self._enqueue
        iterator=source.__aiter__()
        try:
            while self._active(epoch) and generation==self._generation:
                if remaining<=0:raise TimeoutError('Sintese Fish excedeu o tempo limite.')
                started=self.loop.time()
                try:data=await asyncio.wait_for(anext(iterator),min(SOURCE_TIMEOUT_SECONDS,remaining))
                except StopAsyncIteration:break
                remaining-=self.loop.time()-started
                if not self._active(epoch) or generation!=self._generation:return
                total+=len(data)
                if total>12*1024*1024:raise ValueError('PCM acima do limite.')
                buffer.extend(data)
                while len(buffer)>=PCM_CHUNK_BYTES:
                    if not self._active(epoch) or generation!=self._generation:return
                    if not await send(epoch,bytes(buffer[:PCM_CHUNK_BYTES])):return
                    if first_audio is None:first_audio=time.monotonic()-started
                    del buffer[:PCM_CHUNK_BYTES];received=True
                    if first and enqueue is None:
                        self.owner.ui.narration_text(text,at=anchor,duration=None);first=False
            if not self._active(epoch) or generation!=self._generation:return
            if len(buffer)%2:raise ValueError('PCM incompleto retornado pelo provedor.')
            if buffer:
                if not await send(epoch,bytes(buffer)):return
                received=True
                if first and enqueue is None:self.owner.ui.narration_text(text,at=anchor,duration=None)
            if not received:raise ValueError('Fish Audio retornou audio vazio.')
        finally:
            from core.runtime_metrics import record
            record('fish_pcm',started,'received' if received else 'no_audio',first_audio_seconds=first_audio)
            close=getattr(iterator,'aclose',None)
            if close:await close()

    def _active(self,epoch):
        return not self.closed and epoch==self.owner._response_epoch and not self.owner._manual_rest

    async def _enqueue(self,epoch,data):
        generation=self._generation
        deadline=self.loop.time()+QUEUE_TIMEOUT_SECONDS
        queue=self.owner.audio_in_queue
        while self._active(epoch) and generation==self._generation:
            if queue.qsize()<MAX_AUDIO_CHUNKS and not queue.full():
                queue.put_nowait(data);self.cursor+=len(data)/PCM_BYTES_PER_SECOND
                return True
            if self.loop.time()>=deadline:raise TimeoutError('Reproducao de audio nao drenou a fila.')
            await asyncio.sleep(.01)
        return False

    async def _work(self):
        generation=self._generation
        while not self.queue.empty() and not self.closed and generation==self._generation:
            staged=asyncio.Queue(maxsize=MAX_STAGED_CHUNKS)
            outstanding=0
            async def produce():
                try:
                    while generation==self._generation:
                        if self.queue.empty():
                            self._wake.clear()
                            if outstanding==0:break
                            await self._wake.wait()
                            continue
                        epoch,text=await self.queue.get()
                        self._queued_chars-=len(text);self._fill_queue()
                        first=True
                        async def stage(epoch,data):
                            nonlocal first,outstanding
                            if not self._active(epoch) or generation!=self._generation:return False
                            outstanding+=1
                            await staged.put((epoch,text,data,first))
                            first=False
                            return self._active(epoch) and generation==self._generation
                        try:
                            if self._active(epoch):await self._deliver(epoch,text,pcm(text),enqueue=stage)
                        finally:self.queue.task_done()
                except asyncio.CancelledError:raise
                except Exception as error:
                    await staged.put(error)
                await staged.put(None)
            producer=asyncio.create_task(produce())
            try:
                while True:
                    item=await staged.get()
                    if item is None:break
                    if isinstance(item,Exception):raise item
                    epoch,text,data,first=item
                    if generation!=self._generation:return
                    anchor=self.cursor
                    if not await self._enqueue(epoch,data):return
                    if first:self.owner.ui.narration_text(text,at=anchor,duration=None)
                    outstanding-=1;self._wake.set()
            except asyncio.CancelledError:raise
            except Exception as error:
                if generation==self._generation:
                    self.buffer='';self._flush=False;self._failed=True
                    if self._idle:self._idle.cancel();self._idle=None
                    while not self.queue.empty():self.queue.get_nowait();self.queue.task_done()
                    self._queued_chars=0
                    reason='tempo limite' if isinstance(error,TimeoutError) else 'provedor ou PCM'
                    self.owner.ui.write_log('SYS: Falha Fish ('+reason+'); mudando para a voz nativa desta sessao.')
                    # Rebuild with native audio for the next reply instead of
                    # leaving the assistant selected-but-silent.
                    reconnect=getattr(self.owner,'request_reconnect',None)
                    if callable(reconnect):
                        self.owner._fish_native_fallback=True
                        reconnect(keep_context=True,reason='falha temporaria da voz Fish')
                return
            finally:
                if not producer.done():producer.cancel()
                await asyncio.gather(producer,return_exceptions=True)

    async def close(self):
        self.closed=True;self.buffer=''
        if self._idle:self._idle.cancel();self._idle=None
        if self.task and not self.task.done():
            self.task.cancel();await asyncio.gather(self.task,return_exceptions=True)
        if self._retired:await asyncio.gather(*self._retired,return_exceptions=True)
        while not self.queue.empty():self.queue.get_nowait();self.queue.task_done()
        self._queued_chars=0
