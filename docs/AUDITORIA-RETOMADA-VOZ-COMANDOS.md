# Rodada local: retomada visual, voz e comandos

Data de conclusao: 15/10/2026. Sem publicacao, novo EXE ou alteracao de contas.

## Checklist

- [x] Cenas de textos/simbolos respeitam a propriedade da tela por Forja e
  ULTRON, inclusive apos reflow, vencimento de elementos e restauracao da janela.
- [x] A escrita incompleta retoma ao voltar de uma janela oculta/minimizada.
  Relogios finalizados e cenas canceladas nao sao reativados por essa retomada.
- [x] O temporizador de escrita para quando a cena esta escondida, sem reiniciar
  seu intervalo em todo reflow quando ele ja esta correto.
- [x] Falas nativas de protocolo guardam a sessao, interrupcao, contato e geracao
  do modo de origem. Texto invalidado nao atravessa uma reconexao nem desfaz uma
  interrupcao. A escolha de voz limpa continua sem fallback nativo silencioso.
- [x] Avisos pendentes de progresso da Forja sao substituidos pelo status atual;
  sair/reentrar, falar novamente ou reconectar invalida avisos antigos. Um estado
  silencioso tambem descarta avisos pendentes do estado anterior.
- [x] Resultados tardios de comandos da Forja nao falam confirmacoes antigas em
  uma sessao/modo novo. Consultas obsoletas nao iniciam a etapa seguinte.
- [x] Comandos digitados e do painel remoto autenticado usam o mesmo roteamento
  local para Forja, ULTRON e atualizacao diaria. O pedido remoto continua sendo
  registrado como entrada real, nao como autorizacao inventada pelo modelo.
- [x] Um pedido lento nao e enviado ao modelo depois de um contato mais novo ou
  da troca de sessao. A verificacao inclui o contexto real registrado na interface.
- [x] Tentativas de reconexao por falha de rede possuem pausa minima de tres
  segundos, crescimento progressivo e teto de sessenta segundos, mesmo depois
  de uma reconexao voluntaria ter usado espera zero. A troca de chave invalida
  agora redefine o atributo de espera real, nao uma variavel local sem efeito.

## Testes e revisao

- 330 testes passaram no conjunto geral final, apos a ultima correcao de
  identidade das falas. Os seis contratos da janela real da Forja tambem passaram
  nesta rodada, antes desse ultimo ajuste exclusivamente de roteamento de voz.
- 95 testes focados passaram apos o ajuste final; sobrepoem o conjunto geral e
  nao devem ser somados como casos unicos adicionais.

Regressoes novas em `test_command_delivery_round.py`,
`test_protocol_voice_context_round.py` e `test_visual_mode_resume_round.py`.
Os testes usam sessoes, voz e consultas controladas; nao chamam os provedores.
A revisao ampla inclui voz, comandos, integracoes, fixados, relogios, ULTRON,
Forja e os seis contratos da janela nativa, com previa local isolada.

A revisao cruzada encontrou e levou a corrigir a entrega concorrente de um
pedido antigo apos um pedido novo. A regressao reproduz dois pedidos com o
mesmo horario e valida a identidade serial real da interface; o horario sozinho
nao basta para distinguir entradas rapidas. Compilacao Python e verificacao de espacos
do diff passaram. O traceback sintetico de recepcao no ensaio de voz faz parte
do teste de recuperacao, nao indica falha da suite.

## Limites

Nao houve sintese paga, escuta acustica em microfone/alto-falantes, benchmark
de FPS do aplicativo inteiro ou limpeza/reparo do Windows. Uma operacao que
ja comecou nao e desfeita por invalidar sua confirmacao visual/falada; os dados
e o projeto permanecem preservados. Reiniciar pelo atalho carrega as mudancas.
