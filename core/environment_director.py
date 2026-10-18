"""Direcao semantica do observatorio, independente do renderizador e da IA."""
import time
import unicodedata
import math
from collections import deque


MODES = ('assistant', 'analysis', 'execution', 'focus', 'exploration')
PLANETS = ('sun', 'mercury', 'venus', 'earth', 'mars', 'jupiter', 'saturn', 'uranus', 'neptune', 'moon')
ALIASES = dict(zip(('sol', 'mercurio', 'venus', 'terra', 'marte', 'jupiter', 'saturno', 'urano', 'netuno', 'lua'), PLANETS))
MODE_ALIASES = {'normal': 'assistant', 'assistente': 'assistant', 'analise': 'analysis',
                'execucao': 'execution', 'foco': 'focus', 'exploracao': 'exploration'}


def normalized(value):
    return ''.join(c for c in unicodedata.normalize('NFKD', str(value).lower().strip())
                   if not unicodedata.combining(c))


class EnvironmentDirector:
    def __init__(self, clock=None):
        self.clock = clock or (lambda: time.time() * 1000)
        self.started = False
        self.entrance = None
        self.override = None
        self.planet = None
        self.serial = 0
        self.cue = {'serial': 0, 'kind': 'settle', 'at': 0}
        self.operation = None
        self.operation_name = None
        self._operations = {}
        self._operation_key = None
        self._cancelled_operations = deque(maxlen=64)
        self.media = None
        self.resolved_mode = 'assistant'

    def media_update(self, playback):
        if not isinstance(playback, dict):
            self.media = None
            return
        item = playback.get('item') or {}
        if not isinstance(item,dict):
            self.media=None
            return
        try:
            duration = max(0, int(item.get('duration_ms') or 0))
            progress = max(0, min(duration, int(playback.get('progress_ms') or 0)))
        except (TypeError, ValueError, OverflowError):
            self.media = None
            return
        self.media = {'playing': playback.get('is_playing') is True, 'progress': progress,
                      'duration': duration, 'at': self.clock(), 'title': str(item.get('name') or '')[:160]}

    def start(self, reduced=False, delay=0):
        if self.started:
            return
        self.started = True
        self.entrance = {'at': self.clock() + (0 if reduced else delay), 'duration': 0 if reduced else 4300, 'cancelAt': None}

    def interrupt(self):
        if self.entrance and self.entrance['cancelAt'] is None:
            self.entrance['cancelAt'] = self.clock()
        self.operation = None
        self.operation_name = None
        self._cancelled_operations.extend(self._operations)
        self._operations.clear()
        self._operation_key=None
        self.emit('settle')

    def emit(self, kind):
        self.serial += 1
        self.cue = {'serial': self.serial, 'kind': kind, 'at': self.clock()}

    def command(self, value):
        value = normalized(value)
        if value in ('auto', 'voltar', 'volta', 'normal', 'assistant', 'assistente'):
            self.override = None
            self.planet = None
        elif value in MODE_ALIASES or value in MODES:
            self.override = MODE_ALIASES.get(value, value)
            self.planet = None
        elif value in ALIASES or value in PLANETS:
            self.planet = ALIASES.get(value, value)
            self.override = 'exploration'
        else:
            raise ValueError('Escolha normal, foco, analise, execucao, exploracao ou um planeta do sistema solar.')
        if self.entrance and self.entrance['cancelAt'] is None:
            self.entrance['cancelAt']=self.clock()
        self.emit('attention')

    def operation_event(self, state, name=None):
        if state not in ('running','failed','uncertain','pending','completed','success','done','finished','cancelled'):return False
        key=str(name) if name else self._operation_key or ''
        if key in self._cancelled_operations and state not in ('running','pending','cancelled'):return False
        previous=self._operation_key
        if state in ('running','pending'):
            while key in self._cancelled_operations:self._cancelled_operations.remove(key)
            self._operations.pop(key,None)
            self._operations[key]=state
            self._operation_key=key
        else:
            self._operations.pop(key,None)
            if state=='cancelled':self._cancelled_operations.append(key)
            if key==previous:self._operation_key=next(reversed(self._operations),None)
        focused=state in ('running','pending') or key==previous or previous is None
        if self._operation_key in self._operations:
            self.operation=self._operations[self._operation_key]
            self.operation_name=self._operation_key.partition(':')[0] or None
        elif focused:
            self.operation=state if state in ('failed','uncertain') else None
            self.operation_name=str(name).partition(':')[0] if name and self.operation else None
        if not focused:return False
        self.emit('analysis' if state == 'running' else 'warning' if state in ('failed', 'uncertain')
                  else 'attention' if state == 'pending' else 'resolved' if state in ('completed', 'success', 'done','finished') else 'settle')
        return True

    def payload(self, *, phase='idle', domain=None, visible=True, reduced=False, level=0,
                resting=False, reading=False, settings=False):
        # Reading always wins over ambient exploration; the requested mode is retained for return.
        mode = self.override or ('execution' if self.operation == 'running' or phase == 'executing'
                                 else 'assistant')
        if settings or (not self.override and (reading or domain in ('gmail', 'whatsapp', 'news', 'status'))):
            mode = 'focus'
        self.resolved_mode=mode
        try:
            level = float(level) if not isinstance(level,bool) else 0.
            level = max(0., min(1., level)) if math.isfinite(level) else 0.
        except (ValueError, TypeError):
            level = 0.
        return {'mode': mode, 'planet': self.planet if mode == 'exploration' else None,
                'phase': phase, 'domain': domain, 'visible': bool(visible), 'level': level,
                'resting': bool(resting), 'motion': 'reduced' if reduced else 'full',
                'entrance': dict(self.entrance) if self.entrance else None,
                'cue': dict(self.cue), 'operation': self.operation, 'operationName': self.operation_name,
                'media': dict(self.media) if self.media and self.clock()-self.media['at'] < 30000 else None}

    def snapshot(self):
        return {'requested_mode': self.override or 'auto', 'resolved_mode':self.resolved_mode, 'planet': self.planet,
                'modes': list(MODES), 'planets': list(ALIASES), 'artistic_orbits': True,
                'entrance_started': self.started, 'operation': self.operation}
