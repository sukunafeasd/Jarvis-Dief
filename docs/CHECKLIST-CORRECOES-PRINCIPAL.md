# Correcoes do holograma principal

- [x] Toque ativa repouso real, sem alterar o mute/F4; testes de UI e backend.
- [x] Repouso bloqueia envio do microfone e tem apagamento/retorno animado; captura e pixel-check do nucleo.
- [x] Relogio/data ficam na raiz da cena, independentes do arraste; teste de posicao.
- [x] Noticias comuns e resumo usam fetch_news_package com as mesmas imagens.
- [x] news_briefing e web_search possuem dono unico da apresentacao; nao ha sobrescrita no main.py.
- [x] Noticias sao uma projecao transparente sobre o holograma principal; renderer de noticias cria zero geometrias/nucleos.
- [x] Texto revela caracteres durante a fala, inclusive ao trocar noticia; teste real com IA/PCM capturou 30 instantes de manchete parcial.
- [x] Fim da fala continua o relogio visual sem preencher instantaneamente; teste especifico.
- [x] Chuva em tracos caindo, pulsacao de tarefas, ponteiro temporal, fluxo de sistema e movimento distinto dos demais simbolos.
- [x] 27 testes de regressao, testes visuais de oito dominios, capturas nativas e verificacao de dependencias.
- [x] Descoberta e correcao da preferencia de movimento reduzido do Windows que suprimia texto/animacoes; animacao completa e padrao, reducao e opcao explicita.

O teste real usou uma solicitacao digitada e a voz real da IA; o microfone foi
substituido por silencio no teste. Nao equivale a testar reconhecimento da fala
humana ou uma sessao longa. O aplicativo e reaberto com o microfone normal.

Fotos dependem da disponibilidade da fonte. Sincronismo usa o PCM e estimativas
dos trechos; o provedor atual nao entrega alinhamento exato por palavra.
