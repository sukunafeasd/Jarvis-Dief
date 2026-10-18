"""Persistent local tasks and calendar; separate from connected provider data."""
import json
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

DATABASE = Path(__file__).resolve().parents[1] / "memory" / "organizer.sqlite3"


def organizer_action(parameters, player=None, session_memory=None):
    domain, action = parameters.get("domain", "tasks"), parameters.get("action", "list")
    if domain not in ("tasks", "calendar") or action not in ("list", "read", "create", "update", "complete", "delete"):
        return json.dumps({"ok": False, "error": "Operação inválida."})
    try:
        offset=max(0,int(parameters.get('offset',0)));limit=max(1,min(100,int(parameters.get('limit',100))))
        for field in ('date_from','date_to'):
            if parameters.get(field):datetime.fromisoformat(parameters[field])
    except (ValueError,TypeError):return json.dumps({'ok':False,'error':'Paginação ou filtro de data inválido; nenhuma alteração realizada.'},ensure_ascii=False)
    if parameters.get('selection') is not None:
        try:
            from core.reference_resolver import resolve_selection
            chosen=resolve_selection(domain,parameters['selection'],session_memory,player)
            if parameters.get('id') is not None and int(parameters['id'])!=chosen['id']:raise ValueError('ID e seleção não correspondem.')
            parameters={**parameters,'id':chosen['id']}
        except (ValueError,TypeError) as error:return json.dumps({'ok':False,'error':str(error)},ensure_ascii=False)
    DATABASE.parent.mkdir(parents=True,exist_ok=True)
    with closing(sqlite3.connect(DATABASE, timeout=5)) as db, db:
        db.row_factory = sqlite3.Row
        db.execute("CREATE TABLE IF NOT EXISTS entries (id INTEGER PRIMARY KEY, domain TEXT, title TEXT, due TEXT, priority TEXT, done INTEGER DEFAULT 0)")
        title = str(parameters.get("title", "")).strip()[:250]
        due = str(parameters.get("date", "")).strip()
        if action in ('create','update'):
            if action=='create' and (not title or (domain == "calendar" and not due)):
                return json.dumps({"ok": False, "error": "Informe título e, para agenda, data e horário."}, ensure_ascii=False)
            if due:
                try:
                    datetime.fromisoformat(due)
                    if domain=='calendar' and 'T' not in due and ' ' not in due:raise ValueError()
                except ValueError:
                    return json.dumps({"ok": False, "error": "Use data ISO: AAAA-MM-DDTHH:MM."}, ensure_ascii=False)
            priority = parameters.get("priority", "normal")
            if priority not in ("normal", "high"):
                return json.dumps({"ok": False, "error": "Prioridade inválida."}, ensure_ascii=False)
            if action=='create':
                changed_id=db.execute("INSERT INTO entries(domain,title,due,priority) VALUES (?,?,?,?)", (domain, title, due, priority)).lastrowid
            else:
                try:changed_id=int(parameters.get('id',0))
                except (ValueError,TypeError):return json.dumps({'ok':False,'error':'Identificador inválido.'},ensure_ascii=False)
                changes={}
                for key,column,value in (('title','title',title),('date','due',due),('priority','priority',priority)):
                    if key in parameters:
                        if key=='title' and not title:return json.dumps({'ok':False,'error':'O título não pode ficar vazio.'},ensure_ascii=False)
                        if key=='date' and domain=='calendar' and not due:return json.dumps({'ok':False,'error':'A agenda precisa de data e horário.'},ensure_ascii=False)
                        changes[column]=value
                if not changes:return json.dumps({'ok':False,'error':'Informe o campo que deseja alterar.'},ensure_ascii=False)
                if not db.execute('UPDATE entries SET '+','.join(column+'=?' for column in changes)+' WHERE id=? AND domain=?',(*changes.values(),changed_id,domain)).rowcount:
                    return json.dumps({'ok':False,'error':'Registro não encontrado.'},ensure_ascii=False)
        elif action in ("complete", "delete",'read'):
            try:
                entry_id = int(parameters.get("id", 0))
            except (ValueError, TypeError):
                return json.dumps({"ok": False, "error": "Identificador inválido."}, ensure_ascii=False)
            if action=='read':
                record=db.execute('SELECT * FROM entries WHERE id=? AND domain=?',(entry_id,domain)).fetchone()
                if not record:return json.dumps({'ok':False,'error':'Registro não encontrado.'},ensure_ascii=False)
                data={'kind':domain,'title':'TAREFA' if domain=='tasks' else 'COMPROMISSO','items':[dict(record)],'count':0 if record['done'] else 1,'source':'Registros locais',
                      'refresh':{'provider':'organizer','parameters':{'domain':domain,'action':'read','id':entry_id}}}
                if player:player.show_manifestation(data)
                return json.dumps({'ok':True,'action':action,'data':data},ensure_ascii=False)
            query = "UPDATE entries SET done=1 WHERE id=? AND domain=?" if action == "complete" else "DELETE FROM entries WHERE id=? AND domain=?"
            if not db.execute(query, (entry_id, domain)).rowcount:
                return json.dumps({"ok": False, "error": "Registro não encontrado."}, ensure_ascii=False)
        order = "due,id" if domain == "calendar" else "CASE priority WHEN 'high' THEN 0 ELSE 1 END, CASE WHEN due='' THEN 1 ELSE 0 END,due,id"
        conditions=['domain=?','done=0'];values=[domain]
        if parameters.get('query'):
            conditions.append("instr(lower(title),lower(?))>0");values.append(str(parameters['query'])[:250])
        for field,operator in (('date_from','>='),('date_to','<=')):
            if parameters.get(field):
                bound=parameters[field]
                if field=='date_to' and len(bound)==10:bound+='T23:59:59.999999'
                conditions.append('due'+operator+'?');values.append(bound)
        where=' AND '.join(conditions)
        items = [dict(row) for row in db.execute('SELECT * FROM entries WHERE '+where+' ORDER BY '+order+' LIMIT ? OFFSET ?',(*values,limit,offset))]
        count = db.execute('SELECT COUNT(*) FROM entries WHERE '+where,values).fetchone()[0]
    model = {"kind": domain, "title": "TAREFAS" if domain == "tasks" else "AGENDA",
             "items": items, "count": count, "source": "Agenda local" if domain == "calendar" else "Tarefas locais"}
    model['refresh']={'provider':'organizer','parameters':{'domain':domain,'action':'list',
        **{key:parameters[key] for key in ('query','date_from','date_to','offset','limit') if key in parameters}}}
    if player:
        player.show_manifestation(model)
    if session_memory:session_memory.record_collection(domain,items,offset=offset,next_offset=offset+len(items) if offset+len(items)<count else None)
    return json.dumps({"ok": True, "action": action, "screen_shown": bool(player), "data": model,
                       'complete':offset+len(items)>=count,'next_offset':offset+len(items) if offset+len(items)<count else None,
                       "instruction": "Explique os dados exibidos. São registros locais, não uma conta Google conectada."}, ensure_ascii=False)


TOOL = {"name": "organizer", "description": "Shows/manages LOCAL tasks and calendar. list supports query/date_from/date_to and pagination next_offset; read opens actual record details; update changes only explicit fields. create needs title, calendar also date/time ISO. complete/delete require an actual id or 1-based selection in last list; NEVER guess IDs, dates or success. A local stored event is not a Google Calendar event, external notification or future alarm. Use real returned data/counts and respect complete/next_offset.",
        "parameters": {"type": "OBJECT", "properties": {
            "domain": {"type": "STRING", "enum": ["tasks", "calendar"]},
            "action": {"type": "STRING", "enum": ["list", "read", "create", "update", "complete", "delete"]},
            "title": {"type": "STRING"}, "date": {"type": "STRING", "description": "Data local ISO AAAA-MM-DDTHH:MM"},
            "id": {"type": "INTEGER"},'selection':{'type':'INTEGER','description':'1-based record in the last consulted page, instead of inventing an ID.'},
            'query':{'type':'STRING'},'offset':{'type':'INTEGER'},'limit':{'type':'INTEGER'},'date_from':{'type':'STRING'},'date_to':{'type':'STRING'},
            "priority": {"type": "STRING", "enum": ["normal", "high"]}},
            "required": ["domain", "action"]}, "handler": organizer_action}
