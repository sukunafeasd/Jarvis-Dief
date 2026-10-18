"""Local encrypted snapshots, not account credentials or live verification."""
import json
import re
from pathlib import Path
from datetime import datetime
from core.local_data import LOCK,atomic_write

KINDS={'weather','system','tasks','calendar','news','files','data','memory','search','gmail','whatsapp','photo','forge_artifact'}


class PinnedSceneStore:
    def __init__(self, folder):
        self.folder=Path(folder)
        self.path=self.folder/'pinned_scene.bin'
        self.assets=self.folder/'pin_assets'

    def load(self):
        import win32crypt
        with LOCK:
            if not self.path.exists():return []
            raw=self.path.read_bytes()
        if len(raw)>3*1024*1024:raise ValueError('Cache de previas excedeu o limite')
        value=json.loads(win32crypt.CryptUnprotectData(raw,None,None,None,0)[1])
        return self.validate(value.get('pins'))

    def validate(self, pins):
        if not isinstance(pins,list) or len(pins)>6:raise ValueError('Cache de previas invalido')
        keys=set()
        for pin in pins:
            if not isinstance(pin,dict) or not isinstance(pin.get('data'),dict):raise ValueError('Previa invalida')
            kind=pin['data'].get('kind');key=pin.get('key')
            if not isinstance(kind,str) or kind not in KINDS or not isinstance(key,str) or key in keys:raise ValueError('Tipo de previa invalido')
            if kind not in ('photo','forge_artifact') and key!=kind:raise ValueError('Identidade de previa invalida')
            if kind=='forge_artifact':
                artifact=pin['data'].get('artifact_id','')
                if not isinstance(artifact,str) or not re.fullmatch(r'[0-9a-f]{32}',artifact) or key!='forge:'+artifact:
                    raise ValueError('Identidade de artefato invalida')
            slot=pin.get('slot')
            if slot is not None and (type(slot) is not int or not 0<=slot<6):raise ValueError('Posicao invalida')
            if 'placement' in pin:
                from core.pin_layout import validate_placement
                validate_placement(pin['placement'])
            if kind=='photo':
                asset=pin.get('asset','')
                identifier=pin['data'].get('attachment_id','')
                if (not isinstance(asset,str) or not re.fullmatch(r'[a-f0-9]{16}\.png',asset)
                        or asset!=identifier+'.png' or key!='photo:'+identifier):
                    raise ValueError('Arquivo de foto invalido')
            keys.add(key)
        return pins

    def save(self, pins):
        import win32crypt
        self.validate(pins)
        raw=json.dumps({'version':1,'saved_at':datetime.now().isoformat(),'pins':pins},ensure_ascii=False).encode('utf-8')
        if len(raw)>2*1024*1024:raise ValueError('Previas grandes demais para salvar')
        encrypted=win32crypt.CryptProtectData(raw,'DIEF JARVIS previas',None,None,None,0)
        with LOCK:atomic_write(self.path,encrypted)
