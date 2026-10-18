"""Explicit short live voice check; no microphone, private text or model prompts."""
import asyncio,json,sys,threading,time,tempfile,wave,hashlib
from pathlib import Path
from unittest.mock import Mock
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))

async def sample():
    from core import fish_audio as fish
    from types import SimpleNamespace
    from unittest.mock import patch
    phrase='Bem-vindo, senhor. Estou verificando a continuidade da voz.'
    started=time.monotonic();first=None;raw=bytearray();gaps=[];previous=None
    async for data in fish.pcm(phrase):
        now=time.monotonic()
        if first is None:first=now-started
        if previous is not None:gaps.append(now-previous)
        previous=now;raw.extend(data)
    owner=SimpleNamespace(_manual_rest=False,_response_epoch=0,ui=Mock(),audio_in_queue=asyncio.Queue())
    voice=fish.FishVoiceSession(owner);delivered=bytearray()
    async def replay(text):
        for offset in range(0,len(raw),1703):yield bytes(raw[offset:offset+1703])
    try:
        with patch.object(fish,'pcm',replay):
            voice.feed(phrase,flush=True)
            while voice.pending or not owner.audio_in_queue.empty():
                try:
                    data=await asyncio.wait_for(owner.audio_in_queue.get(),.1)
                    delivered.extend(data)
                    await asyncio.sleep(len(data)/48000)
                except asyncio.TimeoutError:pass
        target=Path(tempfile.mkdtemp(prefix='dief-fish-sample-'))/'fish-original.wav'
        with wave.open(str(target),'wb') as audio:
            audio.setnchannels(1);audio.setsampwidth(2);audio.setframerate(24000);audio.writeframes(raw)
        return {'ok':bytes(delivered)==bytes(raw) and not voice._failed,'bit_exact':bytes(delivered)==bytes(raw),
                'seconds':round(len(raw)/48000,2),'first_pcm_seconds':round(first,2),
                'max_provider_gap_seconds':round(max(gaps,default=0),3),
                'sha256':hashlib.sha256(raw).hexdigest(),'sample':str(target)}
    finally:await voice.close()

async def check(play=False):
    from core.fish_audio import FishVoiceSession,enabled
    if not enabled():return {'ok':False,'error':'Fish nao configurado.'}
    from main import JarvisLive
    owner=JarvisLive.__new__(JarvisLive)
    owner._manual_rest=False;owner._interrupted=False;owner._response_epoch=0
    owner.audio_in_queue=asyncio.Queue();owner._is_speaking=False;owner._speaking_lock=threading.Lock()
    owner._out_latency=.1;owner._tail_until=0.;owner._out_level=0.;owner._play_cursor=0.;owner._played_audio_seconds=0.
    owner._turn_done_event=asyncio.Event();owner._turn_done_event.set()
    owner.ui=Mock();owner.ui.muted=False;owner._visemes=Mock();owner._visemes.frames.side_effect=lambda frames,hop:frames
    owner._echo=Mock();owner._stop_keyword=None
    voice=FishVoiceSession(owner);owner._fish_voice=voice
    audio=asyncio.create_task(owner._play_audio()) if play else None
    started=time.monotonic();total=0;first=None
    voice.feed('Bem-vindo, senhor. Estou verificando a continuidade da voz. Esta e uma frase curta de teste, sem alterar seus projetos ou suas conexoes.',flush=True)
    try:
        while voice.pending or not owner.audio_in_queue.empty() or getattr(owner,'_audio_batch_pending',False) or owner._is_speaking:
            if time.monotonic()-started>90:raise TimeoutError('Voice check exceeded deadline')
            if not play:
                try:
                    data=await asyncio.wait_for(owner.audio_in_queue.get(),.1)
                    total+=len(data)
                    if first is None:first=time.monotonic()-started
                except asyncio.TimeoutError:pass
            else:await asyncio.sleep(.05)
        failed=voice._failed
        seconds=owner._played_audio_seconds if play else total/48000
        return {'ok':not failed and seconds>0,'played':play,'audio_seconds':round(seconds,2),'first_pcm_seconds':round(first,2) if first is not None else None,'elapsed_seconds':round(time.monotonic()-started,2),'voice_failures':[str(call.args[0]) for call in owner.ui.write_log.call_args_list]}
    finally:
        await voice.close()
        if audio:
            audio.cancel();await asyncio.gather(audio,return_exceptions=True)

if __name__=='__main__':
    try:print(json.dumps(asyncio.run(sample() if '--sample' in sys.argv else check('--play' in sys.argv)),ensure_ascii=False))
    except Exception as error:print(json.dumps({'ok':False,'error_type':type(error).__name__}))
