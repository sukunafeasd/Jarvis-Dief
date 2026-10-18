# Rodada local de estabilidade e desempenho

Data: 14/10/2026. Sem publicacao, nova versao ou alteracao de contas.

## Correcoes

- Fixados de pesquisa agora aceitam a resposta textual real da ferramenta e
  capturam seu modelo sem tentar interpretar prosa como JSON. Logs da consulta
  ficam isolados: atualizar o fixado nao abre outra tela nem inicia fala.
- Uma lacuna no audio nativo nao e mais confundida com fim do turno. O estado
  aguarda geracao, ferramentas ou continuacao antes de concluir a apresentacao.
- Falhar ou cancelar o envio de um aviso interno desfaz o estado de geracao
  ficticio, sem fechar um turno mais novo. A verificacao usa sessao, contato,
  epoch, atividade recebida e identidade do envio. Consumo local e restaurado
  quando o aviso nao chegou a iniciar outra resposta.

## Trabalho reduzido

- Consultas usam um conjunto fixo de oito trabalhadores e fila limitada a 24
  entradas. Timeout nao cria trabalhadores substitutos. Trabalho ainda na fila
  e cancelado quando seu prazo termina; consultas ja bloqueadas continuam contando
  no limite ate retornarem. Lotes preservam ordem e limitam paralelismo local.
- Orquestrar noticias nao ocupa um trabalhador esperando pelo mesmo conjunto.
- Visualizacoes escondidas suspendem renderizacao e revelacao de texto; continuam
  recebendo comandos e retomam movimento quando exibidas.
- Noticias fundidas no nucleo nao renderizam tambem o WebGL da superficie frontal
  invisivel. A selecao acompanhando a fala continua funcionando.
- Formatador numerico e consulta de movimento reduzido sao reutilizados. Vetor
  base e cor temporaria deixam de ser alocados por objeto/quadro. Matriz da camera
  so e recalculada quando a proporcao muda.

## Evidencia

- 269 testes abrangentes passaram: voz, comandos, tarefas, dados, fixados,
  noticias, integracoes, ULTRON e encaminhamento Forja.
- 32 testes de apresentacao/movimento passaram, incluindo navegador real,
  pixels nao vazios, movimento, ocultar/retomar e noticias fundidas.
- Testes novos verificam quantidade fixa de trabalhadores sob timeouts repetidos,
  descarte de trabalho cancelado, resposta nativa em dois lotes separados por uma
  pausa e recuperacao de avisos com falha/cancelamento.
- Revisao independente nao encontrou P1/P2 adicional nas mudancas examinadas.
- Compilacao Python e verificacao de espacos do diff passaram.

Os grupos de testes se sobrepoem e nao devem ser somados como casos unicos.
O traceback de erro sintetico no ensaio de recepcao e intencional: testa a
propagacao da falha; a suite terminou com sucesso.

## Limites

Nao houve sintese paga, avaliacao acustica da voz, limpeza/reparo de Windows ou
benchmark de FPS do aplicativo inteiro. As otimizacoes foram verificadas por
contagem de trabalho e contratos de comportamento, nao por promessa de ganho
percentual. Uma biblioteca bloqueada nao pode ser terminada com seguranca numa
thread Python: se todos os trabalhadores ficarem presos, a busca fica indisponivel
ate algum retornar, mas nao cria threads ilimitadas. O aplicativo deve ser
reiniciado para carregar as alteracoes locais.
