"""Per-application presence preferences; no screen contents are persisted."""
import copy
import json
import re
from datetime import datetime,timezone
from core.local_data import ROOT,LOCK,atomic_write


class SpectroStore:
    def __init__(self,path=None):self.path=path or ROOT/'spectro.json'
    def read(self):
        with LOCK:
            if not self.path.exists():return {'format':1,'allowed_apps':[],'preferences':{},'audit':[]}
            if self.path.stat().st_size>64000:raise ValueError('Preferencias do Espectro excedem o limite.')
            value=json.loads(self.path.read_text(encoding='utf-8'))
            if not isinstance(value,dict) or value.get('format')!=1 or not isinstance(value.get('preferences'),dict) or not isinstance(value.get('allowed_apps'),list):raise ValueError('Preferencias do Espectro invalidas.')
            if len(value['allowed_apps'])>64 or len(value['preferences'])>64:raise ValueError('Limite de aplicativos atingido.')
            if any(not isinstance(app,str) or not re.fullmatch(r'[\w .-]{1,120}\.exe',app) for app in value['allowed_apps']):raise ValueError('Aplicativo invalido.')
            audit=value.setdefault('audit',[])
            if type(value.get('observation_paused',False)) is not bool:raise ValueError('Preferencia de observacao invalida.')
            if not isinstance(audit,list) or len(audit)>80:raise ValueError('Historico do Espectro invalido.')
            return copy.deepcopy(value)
    def update(self,callback):
        with LOCK:
            state=self.read();callback(state)
            if len(state['preferences'])>64 or len(state['allowed_apps'])>64:raise ValueError('Limite de aplicativos atingido.')
            atomic_write(self.path,json.dumps(state,ensure_ascii=False,indent=2).encode('utf-8'))
    def allow(self,app):
        if not isinstance(app,str) or not re.fullmatch(r'[\w .-]{1,120}\.exe',app):raise ValueError('Nome de aplicativo invalido.')
        def change(state):
            if app not in state['allowed_apps']:state['allowed_apps'].append(app)
        self.update(change)
    def forget(self,app):
        def change(state):
            state['allowed_apps']=[name for name in state['allowed_apps'] if name!=app];state['preferences'].pop(app,None)
        self.update(change)
    def save(self,app,preference):
        self.update(lambda state:state['preferences'].__setitem__(app,copy.deepcopy(preference)))
    def audit(self,event,data):
        entry={'event':str(event)[:60],'at':datetime.now(timezone.utc).isoformat(timespec='seconds')}
        entry.update({key:str(value)[:120] for key,value in data.items() if key in ('app','tool','state','kind')})
        def change(state):state['audit']=(state.get('audit',[])+[entry])[-80:]
        self.update(change)
