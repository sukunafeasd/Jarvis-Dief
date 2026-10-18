# Modo Espectro local

## Presenca no Windows

O nucleo Three.js existente aparece sobre o Windows, sem painel de controles,
com fundo transparente e sem roubar o foco. Continua usando a mesma sessao,
voz, memoria e ferramentas do Jarvis. Nao ha uma segunda personalidade ou IA.

Comandos de exemplo:

- "Jarvis, ativa o modo espectro."
- "Diminua seu tamanho" / "fique um pouco maior".
- "Fique mais transparente" / "deixe com 50% de opacidade".
- "Se mova para a esquerda" / "um pouco pra direita".
- "Va para cima" / "va para outro monitor".
- "Sai da frente" / "volte ao tamanho normal".
- "Volta pra base."

Tambem e possivel arrastar o nucleo. A regiao externa deixa os cliques passarem.
Tamanho, transparencia e posicao respeitam limites da area util do monitor.
Preferencias gerais e por aplicativo sao persistidas; o ajuste manual prevalece
sobre reposicionamento automatico durante a sessao.

Ctrl+Alt+Shift+F12 interrompe a fala e restaura a base sem depender do microfone.
A entrada e recusada se o Windows nao permitir registrar esse atalho. Isso nao
cancela operacoes ja aceitas pelo sistema. Falha de renderizacao restaura a base.
Forja e ULTRON continuam na janela principal; a transicao retorna a base primeiro.

## Observacao e marcacoes

Selecione o aplicativo desejado e diga "acompanhe este aplicativo". A autorizacao
fica vinculada a janela em primeiro plano no instante desse pedido; uma troca
de janela durante a autorizacao exige novo pedido. O contexto do modelo nao
pode conceder essa permissao por conta propria ou repetir um consentimento antigo.

- "O que voce esta vendo?" consulta o contexto real disponivel.
- Pedidos para apontar elementos usam identificadores reais da acessibilidade.
- Circulos, contornos, setas e notas temporarias aparecem sem botoes ou paineis.
- As marcacoes acompanham a geometria do alvo e somem se ele perder validade.
- "Limpa a tela" remove as marcacoes do Espectro, sem apagar os cards da base.
- "Pare de observar minha tela" pausa a observacao e limpa o contexto e destaques.
- "Volte a observar" retoma apenas aplicativos ja autorizados.
- "Nao me interrompa" silencia sugestoes; "pode dar sugestoes" permite novamente.

A observacao usa Windows UI Automation com consultas limitadas a cada quatro
segundos. Enquanto existe um alvo marcado, sua posicao e revalidada em trabalho
separado, com intervalo minimo de meio segundo, sem repetir a leitura completa
da janela. Consultas lentas continuam limitadas a um worker; esse intervalo nao
garante atualizacao em tempo real em qualquer aplicativo.
Alguns aplicativos nao expoem todos os elementos; ausencia de um
controle nao prova ausencia de conteudo. Janelas sensiveis reconhecidas pelo
titulo sao recusadas, mas esse filtro nao substitui cuidado com dados pessoais.

Nao ha envio automatico de capturas. Quando a ferramenta visual existente e
explicitamente acionada no Espectro, a captura usa apenas a janela autorizada,
com verificacao de identidade e permissao antes e depois. Nao ha retorno
silencioso para captura de toda a area de trabalho. Aplicativos que bloqueiam
PrintWindow podem exigir usar os controles acessiveis em vez de imagem.

O overlay e as marcacoes solicitam exclusao de captura ao Windows quando essa
funcao esta disponivel. Conteudo observado e tratado como dados nao confiaveis,
nunca como novas instrucoes ou autorizacao para executar comandos.

## Iniciativa e privacidade

Sugestoes partem de eventos reais de tarefas e indicacoes observadas de erro,
com deduplicacao, prazo de validade e intervalo minimo. Sao revalidadas contra
a janela e o texto atual antes de serem usadas. Uma mensagem de erro observada
nao comprova sua causa; o Jarvis deve explicar a limitacao e oferecer ajuda.

Nao existem permissoes novas para executar comandos arbitrarios em segundo
plano. Acoes continuam passando pelas ferramentas e autorizacoes existentes.
O modo nao se reativa sozinho na proxima sessao; observacao tambem inicia pausada.

spectro.json guarda aplicativos autorizados, preferencias de apresentacao e um
registro limitado de eventos. Nao guarda o texto bruto das janelas ou capturas.
Revogar observacao invalida resultados pendentes, cancela trabalho ainda na fila
e impede novas leituras entre etapas de acessibilidade. Chamadas nativas ja em
andamento podem precisar terminar; seu resultado e descartado apos revogacao.
Workers compartilhados e limitados evitam acumular consultas presas entre sessoes.

## Implementacao

- core/spectro.py: janela, geometria, transicoes, integracao e retorno global.
- core/spectro_commands.py e actions/spectro_control.py: pedidos e ferramenta estruturada.
- core/spectro_perception.py: contexto e alvos reais via UI Automation.
- core/spectro_observer.py: ciclo limitado de observacao e invalidacao.
- core/spectro_annotations.py: marcacoes transparentes e sem foco.
- core/spectro_capture.py: captura sob demanda de uma janela autorizada.
- core/spectro_initiative.py: eventos limitados e deduplicados.
- core/spectro_store.py: persistencia atomica de preferencias e permissoes.
- ui.py e main.py: mesma sessao de voz e despacho pelo thread Qt.

## Validacao

tests/test_spectro.py e tests/test_spectro_complete.py cobrem ciclo de vida,
comandos, geometria, permissoes, revogacao, eventos tardios, persistencia,
marcacoes, contexto e trabalho limitado. tools/run_local_audit.py executa a
bateria geral em dados temporarios sem alterar contas ou memorias pessoais.

tools/validate_spectro.py testa o renderizador real: pixels, transparencia,
movimento, resposta a audio sintetico, ajustes reais por comandos, hit-test Win32
e retorno pela mensagem nativa do atalho registrado.

tools/validate_spectro_perception.py abre um aplicativo sintetico descartavel em
outro processo: autorizacao pelo adaptador real JarvisUI, leitura UIA, destaque,
movimento da janela, captura restrita, sugestao de evento real e privacidade.

Nao houve teste de conversa completa por microfone com provedores pessoais,
nem teste fisico em varios monitores com DPI diferentes. Os testes de voz usam
texto e audio sinteticos; a mensagem de atalho nao simula teclas fisicas.
Essas verificacoes nao garantem ausencia de qualquer bug ou compatibilidade
com todos os aplicativos Windows.

O EXE iniciador local carrega os fontes desta copia ao reiniciar. Nesta rodada
nao houve reconstrucao do EXE nem publicacao no GitHub.

### Evidencias desta rodada

- Regressao focada final: 152 testes, sem falhas ou erros.
  %USERPROFILE%/AppData/Local/Temp/dief-audit-core-8tjk7zmp/report.json
- Bateria visual e de stress de renderizacao: 32 testes, sem falhas ou erros.
  %USERPROFILE%/AppData/Local/Temp/dief-audit-visual-8bcxrqwl/report.json
- Renderer nativo, com tamanho/posicao/opacidade e retorno real verificados:
  %USERPROFILE%/AppData/Local/Temp/dief-spectro-native-2tf6ch2t/report.json
- Observacao nativa, alvo seguindo janela, captura restrita e privacidade:
  %USERPROFILE%/AppData/Local/Temp/dief-spectro-perception-nygp5q18/report.json
- Bateria geral: 777 testes, 1 ignorado e 1 erro de timeout de inicializacao
  no teste de card compacto. O grupo completo desse teste passou na repeticao
  isolada (5 testes). A causa do timeout nao foi comprovada.
  %USERPROFILE%/AppData/Local/Temp/dief-audit-core-vpwj_l63/report.json
  %USERPROFILE%/AppData/Local/Temp/dief-audit-core-3ilhrd0b/report.json

### Reforco de comportamento e apresentacao

Ajustes consecutivos usam o destino da animacao anterior, nao um quadro
intermediario. A preferencia pendente e salva antes de sair, encerrar ou trocar
o aplicativo de referencia. Um segundo sinal de renderer pronto nao recria o
observador nem reinicia sua autorizacao.

Uma nota cancela o alvo anterior; limpar ou perder o alvo invalida resultados
atrasados para impedir que uma marcacao antiga reapareca. O snapshot expoe
transition (destino e animacao), marking (pending/visible/lost/idle) e os alvos
efetivamente visiveis. Isso permite conferir o efeito antes de afirma-lo.

As marcacoes usam a cor atual do Jarvis, brilho contido, entrada suave,
conector com pulso reagindo ao nivel de voz e texto posicionado dentro da tela.
Movimento reduzido desativa o pulso em deslocamento e a entrada animada.
Uma marcacao nao e um clique; execucao e verificacao continuam nas ferramentas
proprias da tarefa, nao na camada de desenho.

A busca usa iteracao preguicosa da arvore UIA, com limite de 256 elementos e
orcamento cooperativo de 350 ms entre chamadas. Uma chamada nativa individual
pode ultrapassar esse orcamento; nao sao criados workers substitutos sem limite.
O contexto declara que e parcial: nao localizar um controle nao prova que ele
desapareceu. Trocas rapidas entre monitores usam o destino ja solicitado.

Evidencias do reforco:
- Bateria geral: 794 testes, sem falhas ou erros, 1 ignorado por permissao Windows;
  carregada antes dos ultimos ajustes da busca limitada.
  %USERPROFILE%/AppData/Local/Temp/dief-audit-core-_0ubzu8v/report.json
- Regressao focada apos ajustes: 117 testes, sem falhas ou erros.
  %USERPROFILE%/AppData/Local/Temp/dief-audit-core-ixwnc0a1/report.json
- Bateria visual e stress de renderizacao: 32 testes, sem falhas ou erros.
  %USERPROFILE%/AppData/Local/Temp/dief-audit-visual-_htwt2xw/report.json
- Holograma nativo e controles reais:
  %USERPROFILE%/AppData/Local/Temp/dief-spectro-native-605wvc1k/report.json
- Marcacoes, captura restrita, alvo em movimento e privacidade apos busca limitada:
  %USERPROFILE%/AppData/Local/Temp/dief-spectro-perception-6jfih83h/report.json
