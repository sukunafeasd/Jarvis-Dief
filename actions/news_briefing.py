"""The same illustrated news package used by startup briefings."""
from actions.web_search import fetch_news_package

def news_briefing(parameters,player=None):
    package=fetch_news_package(str(parameters.get('topic','')).strip())
    if player:
        player.show_manifestation(package['model'])
    return package['text']+'\n\nApresente as notícias em português, uma por vez, citando primeira/segunda/terceira. As imagens e os resumos aparecem no holograma principal durante sua fala.'

TOOL={'name':'news_briefing','description':'Use SEMPRE para pedidos de notícias, manchetes, atualização de notícias ou resumo informativo. Busca fotos reais e projeta cada matéria no holograma principal, como no resumo inicial. Não abra navegador. Sem assunto, usa os interesses do perfil.',
      'parameters':{'type':'OBJECT','properties':{'topic':{'type':'STRING','description':'Assunto solicitado. Vazio usa preferências salvas.'}}},'handler':news_briefing}
