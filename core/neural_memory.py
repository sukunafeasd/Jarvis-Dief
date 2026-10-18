"""Bounded, redacted visual evidence from actual retrieval results only."""
from core.conversation_memory import redact

RETRIEVAL_TOOLS = frozenset(('memory_control', 'recall_memory', 'qdrant_memory'))


def notify(player, payload):
    callback=getattr(player,'show_neural_memory',None)
    if callable(callback):
        try:callback(payload)
        except Exception:
            import logging
            logging.getLogger(__name__).warning('Neural visual delivery failed; retrieval remains available.')


def retrieval_payload(result, request_id, *, completed=False):
    if not isinstance(result, dict) or result.get('ok') is not True:
        if completed:return {'requestId':request_id,'active':True,'items':[],'depth':'quick','outcome':'unavailable'}
        return {'requestId': request_id, 'active': False, 'items': []}
    if 'query' in result:
        from core.memory_recall import select_relevant
        result=select_relevant(result,result.get('query',''),result.get('question',''))
    items = []
    seen = set()
    rows=result.get('items',[])
    if not isinstance(rows,(list,tuple)):rows=[]
    for row in rows[:20]:
        if not isinstance(row, dict):
            continue
        record = row.get('record') if isinstance(row.get('record'), dict) else row
        identifier = str(row.get('id') or (str(row.get('category', '')) + '/' + str(row.get('key', '')))).strip('/')
        detail = record.get('detail', record.get('value', ''))
        if not identifier or identifier in seen or not isinstance(detail, str) or not detail.strip():
            continue
        if identifier.startswith('conversation:'):
            from core.memory_recall import meaningful_history
            if not meaningful_history(row):continue
        seen.add(identifier)
        items.append({'id': identifier[:160], 'title': redact(str(row.get('title') or row.get('key') or 'Lembranca recuperada'))[:96],
                      'detail': redact(detail)[:400], 'at': str(row.get('at') or record.get('updated') or '')[:40],
                      'source': str(row.get('source') or result.get('source') or 'Memoria local')[:96], 'role': str(row.get('role') or '')[:20]})
        if len(items) == 3:
            break
    payload={'requestId': request_id, 'active': bool(items) or completed, 'items': items, 'depth': 'deep' if len(items) >= 3 else 'context' if len(items) == 2 else 'quick'}
    if completed and not items:
        if result.get('needs_clarification'):payload['awaitingTopic']=True
        else:payload['outcome']='empty'
    return payload
