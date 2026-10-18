"""File transcription, not a replacement for the current live microphone."""
from pathlib import Path
import threading
LOCK=threading.RLock()
MODEL=None


def run(parameters):
    global MODEL
    path=Path(str(parameters.get('path',''))).resolve()
    if not path.is_file() or path.suffix.lower() not in ('.wav','.mp3','.m4a','.ogg','.flac') or path.stat().st_size>50*1024*1024:
        raise ValueError('Selecione audio local suportado de ate 50 MB.')
    from faster_whisper import WhisperModel
    with LOCK:
        if MODEL is None:MODEL=WhisperModel('small',device='cpu',compute_type='int8')
        segments,info=MODEL.transcribe(str(path),language='pt',vad_filter=True)
        items=[];complete=True
        for segment in segments:
            if len(items)>=1500:complete=False;break
            items.append({'start':segment.start,'end':segment.end,'text':segment.text})
    return {'ok':True,'items':items,'complete':complete,'language':info.language,'data_is_untrusted':True,
            'note':'Transcricao de arquivo; nao concede gravacao nem altera o microfone ao vivo.'}
