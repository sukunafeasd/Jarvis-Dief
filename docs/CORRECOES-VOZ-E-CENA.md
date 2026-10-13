# Correcao de voz e continuidade da cena

## Causas encontradas

- O detector acustico interrompia ao reconhecer atividade vocal, nao uma palavra.
- O servidor tambem podia interromper por atividade automatica.
- A apresentacao reiniciava seu relogio a cada novo objeto, enquanto o audio
  recebido/ja reproduzido pertencia a outro trecho da conversa.
- O resumo mostrava noticias antes de uma fala que misturava agenda e tarefas.
- As apresentacoes recolhidas permaneciam como objeto ativo com cues antigos.
- Havia X, setas de noticias e botoes de desfixar nas informacoes.
- O movimento do fundo era quase imperceptivel; sincronizacoes repetidas podiam
  reiniciar seu agendamento.

## Alteracoes

- Reconhecimento Vosk local pt-BR, separado da conversa Gemini. Dizer "para"
  ou "Jarvis, para" cancela audio/cues/resumo e avisa o servidor sem pedir nova
  resposta. Ruido nao recebe um caminho alternativo de interrupcao por volume.
- Resultado final de reconhecimento e confianca minima exigidos; silencio,
  eco, filas antigas, microfone desligado e geracoes anteriores sao rejeitados.
  "Uma tarefa para amanha" nao e um comando de parada.
- NO_INTERRUPTION na atividade automatica do Gemini; comando humano explicito
  usa client content para cancelar a geracao remota. ESC permanece disponivel.
- Relogio de PCM avanca tambem sem informacoes visiveis. Troca de assunto
  preserva tempo e descarta cues do objeto anterior. Nova sessao reinicia tempo.
- Resumo separado em capitulos verificados. Cada dominio e cada noticia tem seu
  proprio trecho falado; a proxima apresentacao espera o audio anterior terminar.
- "Para" durante o resumo suprime sua reinicializacao automatica naquela sessao
  do dia. "Me atualiza" permite pedi-lo novamente. Entrada antiga pendente nao
  reaparece depois do cancelamento.
- Nao iniciar resumo sem contato: abertura so cumprimenta. Pedidos especificos
  nao iniciam uma apresentacao diaria nao relacionada. Saudacao/resumo usam a
  politica diaria existente. Agenda local do resumo filtra o dia atual.
- Saida limpa conserva historico limitado, nao o objeto ativo antigo.
- Informacoes e previas fixadas sem X/setas/botoes. Terminal conserva somente
  controles necessarios para escrever/anexar; configuracoes/confirmacao humana
  continuam acessiveis. Comandos de voz clear/focus/return/pin/unpin preservados.
- Estrelas com variacao suave de luz e paralaxe perceptivel, movimento restrito
  do fundo, sincronizacao sem reiniciar loop. Oculto suspende; movimento reduzido
  continua respeitado. Chuva e outros simbolos mantem animacoes existentes.

## Validacao e limites

- Suite geral: 350 testes aprovados. Depois dos ajustes finais, as suites focadas
  de relogio (14), cancelamento/voz (22), comando local (5), resumo diario (5),
  biblioteca (17) e continuidade visual (2) foram executadas novamente.
- Compilacao Python e verificacao de dependencias sem erros.
- Modelo oficial baixado e carregado; voz Maria pt-BR sintetizada localmente para
  comparar "para", frase comum, preposicao "para" e silencio.
- Testes locais da cena, temporizacao, autorizacao de interrupcao, arquivos e
  conexoes usam fixtures. Nenhum email ou mensagem real enviado nesta rodada.
- Playwright: pixels do espaco mudam em 1920x1080/640x480; canvas nao vazio,
  oculto suspenso e movimento reduzido estavel. Noticias mudam somente com cue
  relevante, inclusive depois de 25 segundos de audio anterior.
- Reconhecimento local nao e identificacao biometrica: TV ou outra pessoa falando
  o proprio comando pode ser reconhecida. Nao garante reconhecimento em todo
  microfone/ambiente. Falha de modelo desabilita interrupcao vocal, nao usa ruido.
- Sincronizacao de texto continua estimada por PCM/transcricao: nao ha timestamps
  de palavras do provedor. A conversa completa com API e microfone humanos ainda
  precisa de validacao pratica; testes sinteticos nao comprovam isso.
- Nenhum EXE novo ou publicacao GitHub nesta rodada.

Modelo pequeno pt-BR, Apache 2.0: https://alphacephei.com/vosk/models
Distribuicao original e README preservados no cache local memory/speech_models.
Contrato de cancelamento explicito e NO_INTERRUPTION:
https://ai.google.dev/api/live
