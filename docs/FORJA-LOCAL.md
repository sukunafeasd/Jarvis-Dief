# FORJA integrada ao DIEF JARVIS

Esta implementacao e local. Nenhum release ou envio ao GitHub foi feito.

## Uso

- Em Configuracoes > Conexoes, abra Codex / Modo Forja e conecte sua
  propria conta ChatGPT, ou informe sua propria chave OpenAI no campo protegido.
- Diga "ativar modo forja". A camera entra no nucleo, o cenario fica preto
  e a luz forma o painel aprovado. A saudacao acontece depois da entrada.
- Descreva a criacao por voz ou no campo de texto do painel. Ajustes permanecem
  no mesmo projeto. "Crie outro projeto chamado Reator" inicia outro projeto.
- "Para" interrompe a fala; "cancele a criacao" interrompe o trabalho Codex.
- "Salve o projeto", "salve na biblioteca como Reator", "desfaca a alteracao",
  "refaca" e "salve na area de trabalho" sao comandos de controle.
- "Abra o projeto Reator" retoma um projeto salvo pelo nome exato.
- "Sair da Forja" preserva o projeto e devolve a camera ao Jarvis.
- Fora da Forja, "fixe Reator na tela" reutiliza um artefato realmente salvo
  na biblioteca, em uma vista isolada. Nao cria uma imagem ficticia.

## Checklist da integracao

- [x] Interface preta e painel verde do prototipo preservados.
- [x] Transicao ligada ao nucleo real, nao a um video ou esfera duplicada.
- [x] Prontidao de pagina oculta corrigida; viewport ocupa a janela inteira.
- [x] F11, saida, reentrada, cancelamento e movimento reduzido verificados.
- [x] Itens fixados ocultados temporariamente e restaurados ao sair.
- [x] Motor oficial App Server, separado da IA principal e da voz Fish.
- [x] Conta e modelos reais consultados; nao ha estado conectado ficticio.
- [x] Arquivos, revisoes, biblioteca e exportacao persistentes.
- [x] Previa candidata validada antes de substituir a ultima previa utilizavel.
- [x] Conteudo criado sem ponte Qt, sem acesso ao controle nativo do Jarvis.
- [x] Exportacao so para pasta explicitamente solicitada; nao sobrescreve dados.
- [x] Reconhecimento literal da ativacao ULTRON, incluindo formas educadas.
- [x] Fish sem eco artificial, com fila limitada, pre-buffer e escrita de audio
  fora da rotina principal. Teste de sintese e reproducao real concluido.

## Contas e seguranca

Cada usuario conecta a propria conta no proprio computador. Autorizacoes ficam
no armazenamento oficial de credenciais Codex, separado do projeto. Nao sao
copiadas da sessao do aplicativo Codex, embutidas no codigo nem exportadas.

O filho Codex usa token de usuario padrao mesmo se o Jarvis for administrador.
Assinatura do executavel, identidade, elevacao e grupo de processos sao
verificados antes de libera-lo. Nao ha concessao automatica de privilegios ou
instalacao global. A prontidao do sandbox Windows deve estar confirmada.

O schema instalado nao restringe completamente a leitura de arquivos do host.
Portanto, workspace-write nao e isolamento total de dados: para trabalho nao
confiavel, uma conta Windows separada ou uma VM ainda e recomendavel. Pedidos
de ferramentas privilegiadas sao recusados, nao convertidos em consentimento
automatico. O lancamento a partir de host elevado foi ensaiado de verdade:
host administrador, filho Codex nao elevado, conexao autenticada e sandbox
pronto. Quando o token vinculado UAC e apenas de identificacao, a abertura usa
o token primario do Windows Explorer, com identidade, sessao e privilegios
verificados. Nao eleva o Codex nem altera a protecao do Windows.

## Verificacao

Os testes automatizados usam contas e servidores simulados, sem cobrar geracao.
O teste nativo usa a janela Qt real, capturas e conteudo de teste isolado.
Os testes explicitos `tools/validate_fish_live.py --play` e
`tools/validate_forge_live.py --generate` usam as conexoes locais e devem ser
executados somente para uma verificacao deliberada. A segunda opcao cria um
novo projeto de teste e consome uso da conta conectada.

Uma conexao autenticada nao garante disponibilidade de todos os modelos,
limites ilimitados, acerto de toda criacao ou ausencia de latencia do provedor.

Na primeira verificacao da integracao, o login ChatGPT foi confirmado e sete modelos
foram retornados. A geracao de teste foi aceita, mas o provedor encerrou a etapa
por limite de uso da conta. Portanto a geracao ponta a ponta com esta conta
ainda nao foi aprovada: o aviso de limite foi corrigido e nao houve novas
tentativas automaticas. Os testes de fluxo com servidor simulado e as 28
verificacoes da janela nativa passaram; 169 testes passaram com uma verificacao
de links simbolicos indisponivel neste Windows. A voz Fish foi sintetizada e
reproduzida de verdade por 7,52 segundos, sem falhas registradas.
