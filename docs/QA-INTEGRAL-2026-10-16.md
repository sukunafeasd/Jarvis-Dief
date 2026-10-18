# Rodada integral de testes - 16/10/2026

## Escopo e isolamento

Revisao local, sem publicacao, troca de credenciais, limpeza do Windows ou
envios reais. Configuracoes, memoria e conexoes de teste usam diretorios
temporarios; ferramentas externas usam fixtures, servidores locais e mocks.
As validacoes nativas usam Qt/WebEngine reais, nao apenas offscreen.

Nao e uma garantia de ausencia de todos os bugs. Contas externas, cobranca,
qualidade subjetiva da voz e acoes administrativas destrutivas nao foram
exercitadas no ambiente pessoal.

## Correcoes verificadas

- Desfixar: falha de gravacao preserva card, cache e disco; retorna erro.
- Conexoes manuais: deadline, fila limitada e descarte de resultados antigos.
- Gmail: salvar/importar nao espera pelo lock de uma autorizacao expirada
  na thread grafica; informa que a autorizacao ainda esta encerrando.
- Atualizacao diaria: fontes sincronas travadas ficam num pool daemon
  limitado, sem bloquear o encerramento do executor padrao asyncio.
- Comandos: nova fala invalida pedido antigo antes de rotear apos persistencia.
- Interrupcao digitada tambem cancela sintese Fish silenciosa, PCM em fila
  e resposta remota ainda aberta, nao somente audio ja audivel.
- Artefatos: negacoes/hipoteses nao fixam arquivos; busca e confirmacao
  respeitam a identidade do turno que originou o pedido.
- ULTRON: relogio acompanha PCM global durante reentrada; interrupcao
  reinicia cursor e relogios juntos, sem antecipar legendas futuras.
- Cards: reserva temporaria de espaco em janela pequena evita cobrir fixados;
  fechar a resposta restaura as posicoes salvas.
- Cantos: troca considera posicoes calculadas reais; valida destino antes
  de salvar e nao anuncia movimento que nao coube.
- Movimento reduzido: ULTRON para a animacao continua, resolve abertura
  imediatamente e respeita a preferencia nos dados holograficos tambem.
  Resize solicita um redesenho unico, sem deixar canvas vazio ou reativar o loop.

## Carga e falhas

Testes novos em test_system_stress_round.py, test_failure_recovery_stress.py,
test_command_chaos_round.py e test_render_stress_round.py:

- 5.000 resultados atrasados de conexao rejeitados por geracao.
- 10.000 cues com fila limitada a 256, cancelamento e finalizacao.
- 5.000 registros concorrentes de execucao; historico limitado a 128.
- 600 turnos concorrentes de personalidade/historico, sem perda de registros.
- 2.000 ciclos de modos e operacoes fora de ordem.
- 500 layouts aleatorios de seis cards, com limites e intersecoes conferidos.
- Saturacao de pool, shutdown, fontes travadas e falhas simuladas de disco.
- Centenas de mudancas WebGL de modo/visibilidade, resize e reentradas ULTRON,
  com recursos limitados apos aquecimento e verificacao de pixels reais.
- Repeticao adicional de 27 casos de estresse: todos passaram.

## Validacoes nativas

- Configuracoes/cards: passed=true, sem excecoes; uma unica previa do nucleo,
  animacao com pixels coloridos, pause/resume e tres cards carregados.
- Abertura: nove contratos passaram; cena completa desde a revelacao,
  aproximacao, planeta fixo e ausencia de troca do nucleo.
- Configuracao inicial: nao inicia abertura nem sobrepoe nucleo aos campos.
- ULTRON --poll: passed=true; camera compartilhada, planeta fixo,
  dados narrados, uma conclusao e retorno da camera.
- Forja: 28 verificacoes nativas passaram, incluindo preview isolado,
  atalhos, cancelamento durante entrada e restauracao da cena.

Capturas e relatorios volumosos ficam no TEMP, com prefixos dief-observatory,
dief-native-opening, dief-ultron-native, dief-forja-native e dief-render-stress.

## Verificacoes estaticas

384 arquivos Python e 30 modulos JavaScript locais analisados sem erros de
sintaxe. git diff --check executado nas alteracoes revisadas.

## Execucao completa

Primeira descoberta: 1.076 testes em 1.046,9 segundos; dez falhas, cinco erros
e um ignorado. Alem das correcoes de runtime, testes legados foram atualizados
para LightSwitch, material atual, duas camadas canvas e prontidao real.
Capturas WebGL passaram a usar pixels compostos, nao toDataURL de um buffer
descartavel. O contrato visual de movimento reduzido identificou um bug real
no ULTRON e foi preservado, com correcao no runtime.

Uma segunda descoberta completa e retestes direcionados sao registrados em
dief-entire-retest-20261015.log no TEMP. O teste ignorado depende de permissao
Windows para criar symlink; nao alteramos politicas para habilita-lo.

Segunda descoberta: 1.097 testes em 1.102,4 segundos, com uma falha de fixture
de abertura, um timeout WebGL e um ignorado. A fixture ja havia sido importada
antes da correcao durante essa execucao; passou depois em processo novo.
O timeout ocorreu esperando updateCore por 30 segundos em software WebGL
sob carga. Nao foi classificado como bug de producao resolvido somente por
passar isoladamente. A verificacao de inicializacao passou a observar erros
explicitos e aguardar ate 60 segundos; foram acrescentadas doze inicializacoes
frias consecutivas em paginas independentes.

Retestes funcionais finais: 128 passaram, incluindo Fish sintetico, comandos,
conexoes, timeout, persistencia e regressao dos movimentos. Nenhuma API real
de sintese ou login foi chamada para atribuir qualidade subjetiva a voz.
Os cenarios de estresse repetidos somaram mais 27 aprovados.

Fechamento visual: 16 testes passaram em 91,5 segundos, incluindo as doze
inicializacoes frias, os dois testes que exigiram reteste na descoberta ampla,
movimento reduzido, resize e estabilidade de recursos. Log:
dief-final-visual-retest-20261016.log, no TEMP.

A suite atual enumera 1.102 casos. Nao foi feita uma terceira descoberta
integral ja com os ultimos quatro casos/fixes carregados desde o inicio;
portanto nao declarar "1.102 passaram juntos". O timeout de 30 segundos
na rodada ampla nao voltou nos retestes, mas sua ausencia definitiva sob
carga concorrente nao esta comprovada. Continua um risco a acompanhar.
Os relatorios acima distinguem passagens amplas, retestes e limites reais.
