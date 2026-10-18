"""Backup allowlisted; tokens e sessoes nunca sao incluidos."""
import hashlib
import json
import sqlite3
import zipfile
from contextlib import closing
from pathlib import Path
from core.office_resources import write_new
from core.resource_jobs import request

ROOT=Path(__file__).resolve().parents[1]
FILES=('memory/long_term.json','memory/personality.json','memory/conversations.sqlite3','memory/organizer.sqlite3','memory/resources.sqlite3','preferences.json')
PROFILE_KEYS=('user_name','assistant_name','city','news_interests','news_count','morning_brief_enabled','hud_style','ui_color','reduce_motion','presentation_hold','voice_name')


def create(path):
    def save(target):
        import tempfile
        with tempfile.TemporaryDirectory() as folder,zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as archive:
            manifest={}
            for name in FILES:
                if name=='preferences.json':
                    from memory.config_manager import CONFIG_FILE
                    settings=json.loads(CONFIG_FILE.read_text(encoding='utf-8')) if CONFIG_FILE.is_file() else {}
                    if not isinstance(settings,dict):raise ValueError('Preferencias invalidas; nao gerei backup incompleto.')
                    data=json.dumps({key:settings[key] for key in PROFILE_KEYS if key in settings},ensure_ascii=False).encode('utf-8')
                    archive.writestr(name,data);manifest[name]=hashlib.sha256(data).hexdigest();continue
                if name=='memory/long_term.json':
                    from memory.memory_manager import MEMORY_PATH
                    source=MEMORY_PATH
                elif name=='memory/personality.json':
                    from core.personality import path as personality_path
                    source=personality_path()
                elif name=='memory/conversations.sqlite3':
                    from core.conversation_memory import path as conversation_path
                    source=conversation_path()
                else:source=ROOT/name
                if not source.is_file():continue
                if source.stat().st_size>50*1024*1024:raise ValueError('Backup acima do limite por arquivo.')
                if source.suffix=='.sqlite3':
                    snapshot=Path(folder)/source.name
                    with closing(sqlite3.connect(source.resolve().as_uri()+'?mode=ro',uri=True)) as original,closing(sqlite3.connect(snapshot)) as destination:
                        original.backup(destination)
                    data=snapshot.read_bytes()
                else:data=source.read_bytes();json.loads(data)
                archive.writestr(name,data);manifest[name]=hashlib.sha256(data).hexdigest()
            archive.writestr('manifest.json',json.dumps({'format':1,'files':manifest}))
    if Path(path).suffix.lower()!='.zip':raise ValueError('Destino deve ser um ZIP novo.')
    return write_new(path,save)


def inspect(path):
    path=Path(path).expanduser().resolve()
    if not path.is_file() or path.stat().st_size>100*1024*1024:raise ValueError('Backup ausente ou acima do limite.')
    with zipfile.ZipFile(path) as archive:
        names=archive.namelist()
        if len(names)!=len(set(names)) or set(names)-set(FILES)-{'manifest.json'} or 'manifest.json' not in names:
            raise ValueError('Backup contem caminhos nao autorizados ou duplicados.')
        if sum(item.file_size for item in archive.infolist())>150*1024*1024:raise ValueError('Backup descompactado acima do limite.')
        manifest=json.loads(archive.read('manifest.json'))
        if manifest.get('format')!=1 or set(manifest.get('files',{}))!=set(names)-{'manifest.json'}:raise ValueError('Manifesto invalido.')
        for name,digest in manifest['files'].items():
            if hashlib.sha256(archive.read(name)).hexdigest()!=digest:raise ValueError('Integridade do backup nao confirmada.')
    return {'ok':True,'files':list(manifest['files']),'credentials_included':False,'hash':hashlib.sha256(path.read_bytes()).hexdigest()}


def restore_to_folder(path,destination):
    # Stage a recovery rather than corrupting databases in use by the running app.
    verified=inspect(path);folder=Path(destination).expanduser().resolve()
    if folder.exists():raise ValueError('Escolha uma pasta NOVA para recuperar os dados; nao substituo bancos em uso.')
    folder.mkdir(parents=True,exist_ok=False)
    with zipfile.ZipFile(path) as archive:
        for name in verified['files']:
            target=folder/name;target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(archive.read(name))
    return {'ok':True,'staged':True,'path':str(folder),'live_data_replaced':False,'note':'Dados recuperados em pasta separada; o Jarvis em execucao nao teve sua memoria substituida.'}


def run(p):
    action=p.get('action','status')
    if action=='status':return {'available':True,'includes':list(FILES),'credentials_included':False,'restoration':'pasta separada; nao altera bancos em uso'}
    if action=='inspect':return inspect(p.get('path',''))
    if action=='create':return request('Salvar backup local','Memoria e registros; sem credenciais.',lambda:create(p.get('path','')))
    if action=='restore':
        verified=inspect(p.get('path',''));destination=Path(p.get('destination','')).expanduser().resolve()
        if not p.get('destination') or destination.exists():raise ValueError('Informe uma pasta nova para recuperacao.')
        def restore():
            if inspect(p['path'])['hash']!=verified['hash']:raise ValueError('Backup mudou depois da confirmacao.')
            return restore_to_folder(p['path'],destination)
        return request('Recuperar backup em pasta separada',str(destination),restore)
    raise ValueError('Acao invalida.')
