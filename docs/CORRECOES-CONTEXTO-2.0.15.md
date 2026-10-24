# Rodada local 2.0.15

Sem publicacao no GitHub. Sem alteracao de visual, contas ou memorias.

- O monitor de resposta so considera progresso audio, texto de resposta,
  chamadas reais de ferramentas e conclusao. Pacotes vazios e pensamentos
  internos nao renovam indefinidamente o prazo de recuperacao de silencio.
- Uma nova fala nao apaga a protecao contra duplicar um envio pendente ou
  incerto. Envios confirmados podem ser solicitados novamente em outro pedido.
- O limite de 20 envios por pedido e separado do historico incerto, limitado
  a 128 entradas. Ao saturar, exige verificacao dos pendentes, sem descarta-los.
- Revisao independente encontrou o problema do limite acumulado; corrigido
  com testes de regressao para saturacao e reconciliacao.

Validacao: 90 testes aprovados, cobrindo progresso, voz/noticias, contexto,
entrega de comandos, conversa, condicionais, referencias, linguagem natural,
estilo de fala e acompanhamento de operacoes.
Nao comprova latencia da API, qualidade de microfone ou sucesso em todos os
aplicativos reais. Logs disponiveis estavam antigos; nao foram tratados como
evidencia da sessao atual. A instalacao deve ser verificada separadamente.
