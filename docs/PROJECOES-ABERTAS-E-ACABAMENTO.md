# Projecoes abertas e acabamento visual

## Direcao

Preservar a linguagem vermelho/ciano do DIEF JARVIS e distinguir informacao
temporaria de conteudo persistente. Icones tem volume e movimento; texto fica
frontal. Nenhuma troca de provedor, alteracao de contas ou nova coleta de dados.

## Fases

- [x] Auditar o fundo nativo e as superficies WebGL/DOM.
- [x] Remover vidro e moldura externa de buscas, dados, sistema, agenda,
      tarefas, arquivos, memoria, Gmail e WhatsApp temporarios.
- [x] Colocar simbolo ao lado de texto/lista, com destaque fino na selecao.
- [x] Preservar cards de clima, atualizacao diaria e previas fixadas.
- [x] Preservar noticias fundidas ao nucleo principal.
- [x] Reforcar orbitas, particulas, envelope, movimentos atmosfericos e
      intensidade das bordas sem alterar fatos ou simular sucesso de tarefas.
- [x] Melhorar vidro, chanfros, brilho dos condutores e campos das configuracoes.
- [x] Verificar quadros distintos para cada dominio, legenda estavel, leitura
      longa, projecoes compactas e pausa.
- [x] Rever o codigo com um agente independente e corrigir os achados.

## Bugs encontrados

1. O Windows deste computador informa movimento reduzido. Essa preferencia
   anulava a escolha explicita de animacao completa enviada pelo aplicativo.
   Agora `full` e `reduced` sao respeitados; sem escolha explicita, prevalece
   a preferencia do sistema. A opcao de movimento reduzido do Jarvis permanece.
2. Interrupcao podia congelar orbitas, mas deixar texto, luz e outros componentes
   avancando. O relogio de apresentacao, iluminacao e montagem agora congelam.
3. Ponteiros de agenda usavam o relogio real independentemente da pausa. Agora
   partem de um horario real capturado e avancam pelo relogio de movimento.
4. Metricas e detalhes do sistema disputavam uma linha da grade. Sao separados;
   em tela muito baixa/estreita, ha rolagem e o rodape continua acessivel.
5. Regras antigas de Gmail/WhatsApp mantinham margens no celular. Foram
   substituidas por posicionamento responsivo especifico para projecoes.

## Validacao e limites

- 52 testes focados aprovados em dois processos isolados (31 + 21). A primeira
  execucao combinada encerrou sem relatorio final; por isso os grupos foram
  reexecutados separadamente. Nao foi rodada a suite completa do projeto.
- Testes de renderizacao usam dados sinteticos e comparam pixels entre quadros,
  nao apenas capturas estaticas. Tambem verificam limites e erros JavaScript.
- Quatro verificacoes nativas passaram: clima fixado preservado, fundo nativo
  transparente, icone realmente animado e condutores das configuracoes ativos.
- Capturas: `validation/unframed-projections` e `validation/unframed-native`.
- Sintaxe Python e dos modulos JavaScript alterados verificada.
- Revisao independente confirmou a resolucao dos achados de agenda,
  comunicacoes e sistema, incluindo sistema em 390 x 400.
- Nao houve teste de uma conversa real com microfone/TTS ou leitura de contas
  pessoais. A sincronizacao existente foi preservada e exercitada em simulacao.
- Nao foi gerado outro EXE nem publicado no Git. O atalho existente inicia este
  projeto; encerrar e reabrir carrega as alteracoes.

## Skills

Direcao visual e critica: `frontend-design`. Revisao independente:
`requesting-code-review`. Acessibilidade, texto, responsividade e movimento:
`web-design-guidelines`, com regras oficiais em
https://raw.githubusercontent.com/vercel-labs/web-interface-guidelines/main/command.md.
As skills de marketing nao foram usadas para transformar o painel de trabalho
em pagina promocional. A automacao visual utilizou os testes Playwright/Qt
existentes; o CLI separado de `agent-browser` nao foi instalado nesta rodada.
