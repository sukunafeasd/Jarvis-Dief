"""Local command recognition. Acoustic activity alone never stops playback."""
import json
import queue
import re
import threading
from pathlib import Path

MODEL_NAME = 'vosk-model-small-pt-0.3'
MODEL_DIR = Path(__file__).resolve().parents[1] / 'memory' / 'speech_models' / MODEL_NAME
MODEL_URL = 'https://alphacephei.com/vosk/models/' + MODEL_NAME + '.zip'


def is_stop_command(text):
    words = re.findall(r'[a-z]+', str(text).lower())
    # "Para amanha" is an ordinary sentence, not an imperative.
    return words in (['para'], ['jarvis', 'para'], ['para', 'jarvis'],
                     ['para', 'por', 'favor'], ['jarvis', 'para', 'por', 'favor'])


def prepare_model():
    if (MODEL_DIR / 'final.mdl').is_file():
        return MODEL_DIR
    import tempfile
    import time
    import zipfile
    import requests
    MODEL_DIR.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=MODEL_DIR.parent) as folder:
        archive = Path(folder) / 'model.zip'
        with requests.get(MODEL_URL, stream=True, timeout=(5, 20)) as response:
            response.raise_for_status()
            size = 0
            deadline = time.monotonic() + 120
            with archive.open('wb') as output:
                for chunk in response.iter_content(128 * 1024):
                    size += len(chunk)
                    if size > 50 * 1024 * 1024 or time.monotonic() > deadline:
                        raise ValueError('Modelo de voz excedeu o limite')
                    output.write(chunk)
        with zipfile.ZipFile(archive) as source:
            entries = source.infolist()
            if len(entries) > 500 or sum(e.file_size for e in entries) > 200 * 1024 * 1024:
                raise ValueError('Arquivo de modelo invalido')
            root = Path(folder).resolve()
            for entry in entries:
                destination = (root / entry.filename).resolve()
                if not destination.is_relative_to(root) or not entry.filename.startswith(MODEL_NAME + '/'):
                    raise ValueError('Caminho de modelo invalido')
            source.extractall(root)
        candidate = Path(folder) / MODEL_NAME
        if not (candidate / 'final.mdl').is_file():
            raise ValueError('Modelo incompleto')
        try:
            candidate.rename(MODEL_DIR)
        except FileExistsError:
            if not (MODEL_DIR / 'final.mdl').is_file():
                raise
    return MODEL_DIR


class StopKeywordListener:
    def __init__(self, callback, logger):
        self.callback = callback
        self.logger = logger
        self.pending = queue.Queue(maxsize=32)
        self.closed = threading.Event()
        self.generation = 0
        self.ready = False
        self.thread = threading.Thread(target=self._run, daemon=True, name='jarvis-stop-word')

    def start(self):
        self.thread.start()

    def reset(self):
        self.generation += 1

    def feed(self, pcm, distinct=True):
        if not self.ready or self.closed.is_set():
            return
        # Silence ends a phrase without admitting the assistant's own echo.
        item = (self.generation, pcm if distinct else bytes(len(pcm)))
        try:
            self.pending.put_nowait(item)
        except queue.Full:
            self.reset()

    def stop(self):
        self.closed.set()
        self.reset()

    def _run(self):
        try:
            from vosk import Model, KaldiRecognizer, SetLogLevel
            SetLogLevel(-1)
            self.logger('SYS: Preparando reconhecimento local de "para".')
            model = Model(str(prepare_model()))
            recognizer = KaldiRecognizer(model, 16000)
            recognizer.SetWords(True)
            current = self.generation
            self.ready = True
            self.logger('SYS: Interrupcao por voz pronta. Diga "para" ou "Jarvis, para".')
            while not self.closed.is_set():
                try:
                    generation, pcm = self.pending.get(timeout=.2)
                except queue.Empty:
                    continue
                if generation != self.generation:
                    continue
                if generation != current:
                    recognizer.Reset()
                    current = generation
                if recognizer.AcceptWaveform(pcm):
                    result = json.loads(recognizer.Result())
                    words = result.get('result', [])
                    if (generation == self.generation and is_stop_command(result.get('text', ''))
                            and words and min(w.get('conf', 0) for w in words) >= .72):
                        self.callback(generation)
                        recognizer.Reset()
        except Exception as error:
            self.logger('SYS: Comando "para" indisponivel: ' + type(error).__name__ +
                        '. Ruido nao interrompera a fala; ESC continua disponivel.')
        finally:
            self.ready = False
