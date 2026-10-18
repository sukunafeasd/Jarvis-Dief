# Voz: limites de pacotes e reproducao

Revisao offline de `core/fish_audio.py` e exclusivamente de `_play_audio` em
`main.py`. As rotas de daily refresh e os callbacks de microfone nao foram
alterados.

## Defeitos reproduzidos e corrigidos

- Um pacote PCM maior que 4.800 bytes era enviado inteiro ao dispositivo,
  ultrapassando o limite pretendido de 100 ms por escrita. Agora o restante
  aguarda localmente, mantendo a ordem e cada byte do audio original.
- Uma fronteira de transporte no meio de uma amostra de 16 bits fazia o player
  descartar todo o lote. Agora o byte final espera o proximo pacote da mesma
  resposta. Se a resposta termina com uma amostra incompleta, somente esse byte
  e descartado, com aviso. A espera nao ocupa o loop em processamento continuo.
- Uma resposta nova recebida durante a espera pela fila podia ser escrita antes
  do reinicio do dispositivo; o reinicio na iteracao seguinte cortava seu audio.
  O reinicio ocorre antes da primeira escrita da resposta nova. Interrupcoes
  descartam tambem o restante local pertencente a resposta anterior.
- Se a resposta muda durante a espera interna do buffer de jitter, o pacote
  recem-recebido e guardado com seu proprio epoch antes de descartar o lote
  antigo. Ele nao e misturado ao PCM que acabou de ser cancelado.
- A Fish procurava pontuacao em um texto artificialmente cortado no limite de
  segmentacao. Um ponto decimal nessa fronteira virava fim de frase, separando
  `123.45` em duas sinteses. A busca agora considera o texto seguinte, sem
  aumentar o limite dos segmentos.

## Validacao

`tests/test_voice_stream_boundaries.py` contem sete testes com PCM sintetico,
saida de audio simulada e sintese substituida por um gerador local. Os tres
casos iniciais falharam antes das correcoes e passaram depois.
A regressao da espera interna forca a mudanca de epoch na segunda leitura da
fila, com dois bytes antigos e 2.400 bytes novos. Antes da correcao a fila
ficava vazia sem nenhuma escrita; depois somente o pacote novo e reproduzido.

Suites de regressao: `tests/test_fish_playback.py`,
`tests/test_voice_bugfix_round.py` e `tests/test_audio_eighth_audit.py`.
O fixture de apresentacao Fish usa agora o relogio real, incluindo o contrato
de finalizacao introduzido pela revisao de apresentacao.

Nao houve chamadas a provedores, acesso a credenciais ou alteracao de voz,
modelo, ganho, velocidade, configuracoes de latencia ou politicas do Windows.
Os testes verificam integridade e ordem do PCM, limites de escrita e descarte
por resposta. Qualidade audivel, latencia de rede e comportamento do driver
real nao sao medidos por esses dispositivos simulados.

## Revisao rapida ULTRON

Revisao somente leitura dos contratos de runtime, confirmacao, serializacao de
snapshots e callbacks de apresentacao. Nenhum defeito acionavel foi encontrado
nesse recorte; os 17 testes de `tests/test_ultron_state_regressions.py` passaram.
Isso nao representa auditoria completa de operacoes Windows ou dos arquivos do
cofre. Nenhum arquivo ULTRON foi alterado nesta tarefa.
