"""Nomes de assuntos que o usuario pode pedir para fixar."""
import unicodedata

ALIASES={
    'clima':'weather','tempo':'weather','previsao':'weather',
    'agenda':'calendar','compromissos':'calendar','tarefas':'tasks','tarefa':'tasks',
    'noticias':'news','noticia':'news','gmail':'gmail','email':'gmail','emails':'gmail',
    'e-mail':'gmail','e-mails':'gmail','whatsapp':'whatsapp','wtts':'whatsapp',
    'sistema':'system','pc':'system','memoria':'memory','arquivos':'files','arquivo':'files',
    'busca':'search','pesquisa':'search','resultado':'search','dados':'data','resposta':'data',
}


def pin_target(value):
    name=unicodedata.normalize('NFKD',str(value or '').strip().lower())
    name=''.join(c for c in name if not unicodedata.combining(c))
    if name in ('','atual','isso','esta informacao','este conteudo'):return ''
    return ALIASES.get(name,name)
