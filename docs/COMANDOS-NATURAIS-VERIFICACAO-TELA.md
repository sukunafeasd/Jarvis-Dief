# Comandos naturais, verificacao da tela e retorno de camera

Alteracoes locais de 15/10/2026. Sem publicacao, troca de contas, voz ou chaves.

## Protocolos

Pedidos claros aceitam variacoes de verbo, artigo e preposicao: "ativa o
protocolo do ultron", "ligue o Ultron", "quero entrar no modo da Forja",
"desliga o protocolo do ultron". O comando continua correspondendo ao texto
inteiro da pessoa; negacoes, hipoteses e comandos com acoes extras nao sao
executados por uma correspondencia parcial.

Uma referencia curta ambigua ("vamos pro Ultron", "quero usar a Forja") gera
pergunta. A confirmacao vale apenas no proximo turno real, por 120 segundos.
Uma mensagem intermediaria ou prazo vencido invalida a oferta. O runtime
ULTRON confere a autorizacao de forma independente: um sim inventado pelo
modelo nao equivale ao sim real. A confirmacao inicia somente diagnostico;
nao autoriza limpeza, reparos ou outras mutacoes. A Forja entra sem criar
projeto apenas por receber uma confirmacao de entrada.

Nao ha classificador ilimitado de linguagem natural: pedidos fora da gramatica
seguem para conversa. Ambiguidade nao da permissao para executar uma acao.

## Tela

interface_control verifica pos-condicoes de limpeza, remocao de fixados,
fechamento e movimentos com o estado retornado pelo Qt. Um comando pode ter
sido solicitado sem ter produzido o resultado; nesse caso a resposta nao deve
anunciar sucesso. Erros incluem orientacao de reinspecao; quando possivel,
o proprio host inclui o estado atual no erro.

- clear declara escopo temporario e lista fixados, protocolos e atualizacao
  do dia preservados. Nao equivale a apagar tudo que aparece.
- A verificacao de fixados usa a identidade data para respostas de texto,
  nao apenas o kind de uma apresentacao estruturada.
- Movimentos usam bounds reais, nao apenas a variavel da posicao solicitada.
  O movimento lateral sem apresentacao aberta agora reposiciona de verdade.
- scene_viewport informa a area da cena e a origem na janela. Bounds usam
  pixels dessa area; nao confundir com viewport da janela inteira.
- layout_animating indica transicao em andamento. A verificacao pode retornar
  null enquanto falta evidencia; isso nao confirma o enquadramento final.
- A fonte da verificacao e application_state, nao uma analise de pixels.
  Problemas percebidos pelo usuario devem ser tratados como divergencias,
  nao negados porque uma variavel foi atualizada.

## Camera e composicao

O retorno da Forja recalcula a distancia salva quando a janela muda de
proporcao. Evita revelar o nucleo cortado na distancia antiga antes de saltar
para a distancia responsiva. Testado em WebGL real: entrada em 1200x800,
mudanca para 400x900, saida animada; camera identica no fim da promessa e
nos dois quadros seguintes.

O layout Qt respeita movimento reduzido, dispensa animacao sem mudanca e
preserva uma animacao ja em curso para o mesmo alvo. Chamadas repetidas nao
devem reiniciar a interpolacao e deixar o elemento atrasado.

## Validacao

Regressoes offline cobrem frases equivalentes, negacao/hipotese, pergunta e
sim real atravessando host/adaptador/runtime, consentimento inventado, prazo
e turno intermediario. Testes Qt verificam limpeza preservando fixados,
fixacao de texto, movimento lateral real, animacao repetida e movimento
reduzido. Nenhuma limpeza, reparo ou trabalho pago de criacao foi executado.
Dialogo real pelo microfone nao foi utilizado nesta rodada.
