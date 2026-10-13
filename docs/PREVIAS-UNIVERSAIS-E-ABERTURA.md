# Previas universais e abertura

## Checklist da rodada

- [x] Preservar projecoes sem card para respostas normais.
- [x] Fixar dados consultados de clima, tarefas, agenda, Gmail, WhatsApp,
      noticias, sistema, memoria, busca, arquivos e respostas textuais.
- [x] Resolver nomes em portugues e recuperar o assunto do historico.
- [x] Preservar o caminho existente de fotos e composicoes visuais.
- [x] Usar simbolos compactos proprios, diferentes dos objetos principais.
- [x] Chuva/neve, segmentos, calendario, envelope, baloes, arcos reais de
      telemetria, folhas editoriais, rede, radar, arquivos e barras.
- [x] Movimento especifico, base emissiva, texto frontal e material
      grafite solido com borda dupla e faixa de cabecalho por dominio.
- [x] Campos das configuracoes com acabamento preenchido e bordas legiveis.
- [x] Preservar movimento reduzido, pausa e suspensao fora de vista.
- [x] Mostrar um nucleo distante nativo durante a preparacao do WebGL.
- [x] Preparar shaders antes da aproximacao e renderizar imediatamente
      o primeiro quadro da entrada, sem esperar o temporizador idle.
- [x] Adiar restauracao de paginas das previas ate depois da entrada.
- [x] Mesclar fixacoes antecipadas com o cache salvo, sem apagar as antigas.
- [x] Repetir leitura que falha sem gravar um cache vazio.
- [x] Descartar fixacao nova rejeitada e restaurar a anterior se a gravacao falha.

## Validacao

Os testes usam dados sinteticos e configuracoes temporarias. Nenhuma conta,
mensagem ou chave pessoal foi usada.

- Testes dos 11 assuntos e aliases, resposta textual, limpeza preservando
  fixados, capacidade, restauracao, falhas de leitura e rollback de escrita.
- WebGL real com verificacao de movimento por pixels e orcamento de desenho.
- Testes existentes de projecoes, movimentos, configuracoes, controles,
  entrada, persistencia, conexoes e geometria executados em grupos focados.
- Cinco verificacoes nativas passaram: nucleo durante carregamento,
  aproximacao continua, nucleo visivel durante a entrada, quadros avancando
  e quatro assuntos fixados pelos comandos em portugues.
- Capturas revisadas em validation/universal-opening e validation/universal-pins.
- Revisao independente encontrou problemas de cache e fallback corrigidos.
- Sintaxe Python verificada. Nao foi executada a suite inteira, nem uma
  conversa real com microfone, nem medicao de FPS/CPU/GPU da sessao pessoal.

## Limites deliberados

Sao quatro previas simultaneas, uma por assunto semantico. Nao se inventam
dados para um assunto que ainda nao foi consultado, nem se fixa um progresso
temporario de carregamento. Fotos continuam pelo fluxo de anexos existente.
Sem WebGL, a previa usa o resumo textual nativo com os mesmos dados.

As alteracoes estao no projeto usado pelo atalho existente. Nenhum EXE novo
foi empacotado e nada foi publicado no Git nesta rodada.
