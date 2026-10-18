"""Short spoken summaries of verified facts, without another model round trip."""
import re


def clean(value, limit=240):
    text=re.sub(r'\s+', ' ', re.sub(r'<[^>]*>', '', '' if value is None else str(value))).strip()
    if len(text)<=limit:return text
    excerpt=text[:max(0,limit-3)]
    sentences=list(re.finditer(r'[.!?](?:\s|$)',excerpt))
    if sentences and sentences[-1].end()>limit*.5:
        return excerpt[:sentences[-1].start()+1]
    boundary=excerpt.rfind(' ')
    return (excerpt[:boundary] if boundary>0 else excerpt).rstrip(' ,;:')+'...'


def chapter_text(chapter):
    facts = chapter['facts']
    kind = chapter['model'].get('kind')
    if kind == 'weather':
        parts = ['Sobre o clima' + (' em ' + clean(facts['city']) if facts.get('city') else '') + '.']
        if facts.get('temperature') is not None:
            parts.append('A temperatura consultada é de ' + clean(facts['temperature']).replace('.', ',') + ' graus.')
        if facts.get('condition'):
            parts.append(clean(facts['condition']) + '.')
        if facts.get('rain') is not None:
            parts.append('A probabilidade de chuva é de ' + clean(facts['rain']).replace('.', ',') + ' por cento.')
        return ' '.join(parts)
    if kind == 'news':
        title = clean(facts.get('title', facts.get('headline')), 260)
        summary = clean(facts.get('summary', facts.get('detail', facts.get('description'))), 480)
        text=' '.join(part for part in (title.rstrip('.!?') + '.' if title else '', summary) if part)
        return (text if text.endswith(('.','!','?')) else text+'.') if text else 'Esta notícia não possui resumo disponível.'
    labels = {'calendar': 'Na agenda consultada', 'tasks': 'Nas tarefas consultadas', 'gmail': 'Nos e-mails importantes não lidos'}
    items = facts.get('items', [])
    if not items:
        count = facts.get('count')
        if isinstance(count, (int, float)) and count > 0:
            return labels.get(kind, 'Na consulta') + ', há ' + str(count) + ' registros. Os detalhes não estão disponíveis.'
        return labels.get(kind, 'Na consulta') + ', nenhum item foi retornado.'
    parts = [labels.get(kind, 'Na consulta') + ':']
    for item in items[:3]:
        title = clean(item.get('title', item.get('summary', 'Sem título')))
        detail = clean(item.get('detail', item.get('due', '')), 120)
        parts.append(title + ('. ' + detail if detail else '') + '.')
    if len(items) > 3:
        parts.append('Há outros itens na lista exibida.')
    if kind == 'gmail':
        parts.append('Consultei os cabeçalhos; os corpos desses e-mails ainda não foram lidos.')
    return ' '.join(parts)
