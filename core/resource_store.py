"""Registros locais limitados, separados de credenciais e de sessoes externas."""
import json
import sqlite3
import unicodedata
import uuid
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATABASE = ROOT / 'memory/resources.sqlite3'
KINDS = {'contact', 'note', 'project', 'meeting', 'watch', 'knowledge'}


def normalize(value):
    return ''.join(c for c in unicodedata.normalize('NFKD', str(value).casefold()) if not unicodedata.combining(c))


def connection():
    DATABASE.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DATABASE, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute('CREATE TABLE IF NOT EXISTS records (id TEXT PRIMARY KEY, kind TEXT NOT NULL, title TEXT NOT NULL, body TEXT NOT NULL, metadata TEXT NOT NULL, updated TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)')
    db.execute('CREATE INDEX IF NOT EXISTS records_kind ON records(kind)')
    return db


def put(kind, title, body='', metadata=None, identifier=None):
    if kind not in KINDS or not str(title).strip():
        raise ValueError('Informe tipo e titulo validos.')
    if len(str(body)) > 100000 or len(str(title)) > 300:
        raise ValueError('Registro acima do limite permitido.')
    identifier = identifier or uuid.uuid4().hex
    if metadata is not None and not isinstance(metadata,dict):
        raise ValueError('Metadados precisam ser um objeto.')
    meta = json.dumps(metadata or {}, ensure_ascii=False)
    if len(meta) > 12000:
        raise ValueError('Metadados acima do limite permitido.')
    with closing(connection()) as db, db:
        # Validation and upsert must share the write reservation; otherwise a
        # concurrent insert can change the record kind after our SELECT.
        db.execute('BEGIN IMMEDIATE')
        old = db.execute('SELECT kind FROM records WHERE id=?', (identifier,)).fetchone()
        if old and old['kind'] != kind:
            raise ValueError('O identificador pertence a outro tipo de registro.')
        if not old and db.execute('SELECT COUNT(*) FROM records').fetchone()[0] >= 5000:
            raise ValueError('Limite de registros atingido; nenhum dado antigo foi removido.')
        if kind=='project':
            parent=(metadata or {}).get('parent_id');seen={identifier}
            while parent:
                if not isinstance(parent,str) or parent in seen:
                    raise ValueError('A hierarquia do projeto não pode conter ciclos.')
                seen.add(parent)
                ancestor=db.execute("SELECT metadata FROM records WHERE kind='project' AND id=?",(parent,)).fetchone()
                if ancestor is None:raise ValueError('Projeto pai não encontrado.')
                parent=json.loads(ancestor['metadata']).get('parent_id')
        db.execute('INSERT INTO records(id,kind,title,body,metadata) VALUES(?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET title=excluded.title,body=excluded.body,metadata=excluded.metadata,updated=CURRENT_TIMESTAMP', (identifier,kind,str(title).strip(),str(body),meta))
        saved=db.execute('SELECT * FROM records WHERE kind=? AND id=?',(kind,identifier)).fetchone()
    return {**dict(saved),'metadata':json.loads(saved['metadata'])}


def read(kind, identifier):
    with closing(connection()) as db:
        row = db.execute('SELECT * FROM records WHERE kind=? AND id=?', (kind,identifier)).fetchone()
    if row is None:
        raise ValueError('Registro nao encontrado. Consulte a lista antes de selecionar.')
    return {**dict(row), 'metadata': json.loads(row['metadata'])}


def search(kind, query='', offset=0, limit=20, full=False):
    if kind not in KINDS:
        raise ValueError('Tipo de registro invalido.')
    terms = normalize(query).split()
    with closing(connection()) as db:
        rows = db.execute('SELECT * FROM records WHERE kind=? ORDER BY updated DESC,id', (kind,)).fetchall()
    found=[]
    for row in rows:
        item={**dict(row), 'metadata':json.loads(row['metadata'])}
        haystack=normalize(item['title']+' '+item['body']+' '+row['metadata'])
        if all(term in haystack for term in terms):
            if not full:
                item['body']=item['body'][:500]
            found.append(item)
    offset=max(0,int(offset));limit=max(1,min(100,int(limit)))
    page=found[offset:offset+limit]
    return {'items':page,'total':len(found),'next_offset':offset+len(page) if offset+len(page)<len(found) else None,'data_is_untrusted':True}


def delete(kind, identifier):
    with closing(connection()) as db, db:
        changed=db.execute('DELETE FROM records WHERE kind=? AND id=?',(kind,identifier)).rowcount
    if not changed:
        raise ValueError('Registro nao encontrado.')
    return {'deleted':True,'id':identifier}
