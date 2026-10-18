# Escuta, contexto diario e personalidade

Correcoes locais dos relatos de 16/10/2026. Sem release ou push.

## Mudancas

- Interrupcao por fala sustentada religada ao callback real do microfone.
  Antes, durante a reproducao, somente o reconhecedor local de "para" recebia
  os blocos. Agora o gate de voz tambem recebe esses blocos, independentemente
  da disponibilidade do reconhecedor de palavras.
- Exige voz acima do limiar adaptativo, evidencia diferente do eco e cerca
  de 320 ms sustentados. Cliques curtos, silencio e eco nao bastam nos testes.
  O inicio detectado e reenviado ao modelo para nao perder o novo pedido.
- Interromper funciona tambem enquanto a atualizacao aguarda dados, sem
  audio audivel. Um novo pedido digitado pode cancelar o resumo em andamento.
- Silencio seletivo do servidor passou a ser opt-in: o comportamento padrao
  nao deixa o modelo ignorar chamadas diretas como se fossem conversa ambiente.
  Preferencia explicitamente habilitada continua sendo respeitada.
- Fontes do dia sao consultadas silenciosamente ao conectar quando falta a
  entrega do dia. Isso nao abre tela nem fala por cima da saudacao. O resumo
  continua aguardando contato humano e a resposta anterior terminar.
- Uma consulta inicial recente pode ser reaproveitada uma vez, por ate dois
  minutos. Pedidos seguintes consultam novamente; nao reutilizam esse pacote
  para sempre. Desativacoes de Gmail/Agenda sao conferidas antes de entrega.
- Consultas comecam em paralelo com a fala de abertura da atualizacao, nao
  somente depois dela. Sucesso so e marcado depois dos dados/falas verificados.
- Tentativa cancelada antes de iniciar nao consome a atualizacao do dia.
  Tentativa antiga/fracassada nao bloqueia o dia inteiro; ha intervalo de cinco
  minutos antes de nova tentativa automatica no proximo contato humano.
  Uma entrega concluida nao se repete. Recusa explicita pausa a automatica.
- "Se atualize", "pode se atualizar agora" e variantes de cortesia seguem a
  rota de contexto, nao a atualizacao do programa/Windows ou as configuracoes.
- Capitulos longos usam prazo proporcional ao texto em vez de um minuto fixo.
  Excertos falados nao sao mais cortados no meio da ultima palavra, e as
  noticias terminam com pontuacao.
- Preferencias de personalidade aprendidas agora chegam silenciosamente a
  sessao atual, apenas quando mudam e se o turno ainda for valido. Antes so
  entravam nas instrucoes ao reconectar. Falha de sincronizacao nao apaga o
  perfil salvo nem e reportada como falha de armazenamento.
- Instrucoes de conversa reforcadas: fluidez, recomendacao fundamentada,
  interesse, humor ocasional e ausencia de ferramentas desnecessarias para
  conversas/opinioes. Nao sao piadas ou sugestoes obrigatorias por resposta.

## Validacao

- Bateria final: 188 testes passaram em 34,597 s.
- Inclui regressao de voz sustentada sem modelo de palavra-chave, rejeicao de
  eco/ruido curto, cancelamento, atualizacao em paralelo, consulta silenciosa,
  recuperacao de tentativa antiga e sincronizacao de personalidade.
- Audio longo simulado ultrapassou um minuto sem ser cortado pelo prazo antigo.
- Inclui testes existentes de Fish, streaming, escuta, resumos, personalidade,
  fontes parcialmente indisponiveis, opt-out, comandos e latencia.
- git diff --check limpo nos arquivos alterados desta rodada.
- Amostra REAL Fish com frase generica, sem microfone/conteudo privado:
  ok=true; bit_exact=true; 3,25 s de audio; primeiro PCM em 2,97 s;
  maior intervalo entre blocos do provedor: 0,219 s.
  WAV original em %TEMP%/dief-fish-sample-d6nd4zhx/fish-original.wav.
- Log final em %TEMP%/dief-contact-round3-final-check.log.

Uma fixture nova inicialmente deixou de fornecer show_manifestation; ela foi
corrigida e reexecutada. Baterias intermediarias se sobrepoem a final; nao somar
as contagens como casos unicos. Nao foi repetida a suite integral nesta rodada.

## Limites

A amostra curta nao prova continuidade de toda fala longa ou qualidade subjetiva
de timbre. A latencia medida do provedor permanece parte do tempo de resposta.
Sensibilidade e separacao de eco precisam ser conferidas com o microfone,
volume das caixas e ruido do ambiente reais. Nao afirmar ausencia total de
cortes ou resposta instantanea apenas pelos testes sinteticos.

Reiniciar o Jarvis para carregar o codigo e a configuracao de sessao atualizados.
Contas, voz selecionada e credenciais foram preservadas.
