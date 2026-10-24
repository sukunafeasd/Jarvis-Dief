# Voz, noticias e Espectro: 2.0.14 local

Evidencia da instalacao 2.0.13: encerramentos Gemini 1008 por GoAway ignorado,
timeouts de buscas e mensagens de cota esgotada/modelo indisponivel. Sem chaves
ou conteudo privado neste relatorio.

Correcoes:
- Recepcao de GoAway solicita reconexao com contexto; renovacao voluntaria nao
  aguarda a chamada remota de resumo da sessao. Historico permanece em memoria.
- Recuperacao nativa nao recria a sessao Fish que falhou.
- Texto para sintese Fish remove formatacao visual e verbaliza unidades comuns.
- Resumo verifica confirmacao da interface antes de cada capitulo. Interrupcao
  invalida a sequencia. Contexto completo e enviado ao modelo depois da narracao,
  evitando misturar todas as noticias no pedido do primeiro capitulo.
- Voz nativa recebe texto do capitulo para leitura, sem pedir outra composicao.
- Espectro aceita nomes naturais sem exigir a palavra icone/botao; busca termos
  observados e prefixos substanciais, recusando ambiguidades. Consulta UIA mais
  profunda e limitada a 512 controles visitados/80 retornados e 350 ms entre
  chamadas. Operacoes individuais do provedor ainda podem bloquear seu worker.

Validacao: suite focada 158 testes; tres novos cenarios de ordem/interrupcao,
todos os nove testes de test_voice_news_recovery aprovados; 40 testes adicionais
de apresentacao, DOM no navegador e comandos aprovados. Sem chamadas pagas Fish
ou Gemini, sem operacoes em aplicativos pessoais durante os testes.

Limites: confirmacao Qt comprova aceitacao do modelo pela interface, nao pixels
de cada quadro 3D. Ainda necessario ensaio humano de audio/microfone e marcacoes
em aplicativos reais. Alvos que nao aparecem na acessibilidade do Windows nao
ganham coordenadas inventadas. Cotas de API e indisponibilidade externa continuam
sendo limites reais, nao corrigiveis com mudancas de personalidade.

Nao publicar esta versao sem autorizacao do usuario.
