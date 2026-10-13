# Interrupcao por voz

O microfone do computador agora analisa fala enquanto o Jarvis responde.
A deteccao local combina quatro criterios: detector WebRTC VAD, volume acima
do piso adaptativo, separacao do eco da propria voz e evidencia sustentada.
O volume isolado nao autoriza cancelamento. O alvo inicial e cerca de 320 ms
de fala confirmada, aumentando para cerca de 768 ms em ambientes com eco ruim.
Isso e janela de evidencia, nao garantia de latencia total do equipamento.

O VAD usa blocos PCM16 mono de 20 ms a 16 kHz, conforme o contrato do pacote:
https://pypi.org/project/webrtcvad-wheels/
A dependencia foi instalada localmente e declarada para o bootstrap.
Sem o detector, a interrupcao automatica falha de forma conservadora; o
cancelamento manual continua disponivel. Nao ha reconhecimento biometrico
nem verificacao local da palavra "Jarvis" neste detector.

Ao confirmar fala humana, a aplicacao cancela a apresentacao, esvazia o audio
antigo e envia os blocos iniciais preservados da correcao. A fala recebida na
confirmacao de interrupcao do servidor nao e descartada. Transcricoes antigas
nao geram novas legendas ou movimentos da boca. A resposta nova pode reutilizar
os objetos da cena, sem limpar pins ou reiniciar um briefing.

O estado distingue geracao ainda aberta de audio apenas em reproducao. Se a
geracao antiga ja terminou, o cancelamento limpa o playback sem bloquear o
audio da resposta nova aguardando uma confirmacao que nao vai chegar.

Escritas no dispositivo ficaram limitadas a lotes de aproximadamente 100 ms.
Se uma escrita antiga termina depois do cancelamento, seu audio pendente e
abortado e nao avanca os efeitos da apresentacao. O dispositivo continua aberto
para a resposta seguinte. Buffers de entrada sao limitados; excesso de audio
antigo nao deve causar excecao no callback nem atraso crescente.

Chamadas canceladas pelo servidor e etapas dependentes ainda nao iniciadas nao
sao executadas. Uma operacao externa ja iniciada pode terminar: parar a fala
nao desfaz automaticamente um envio, alteracao de arquivo ou acao em app.

Microfone silenciado, repouso, PTT sem tecla pressionada e controle pelo celular
continuam respeitados. Esta rodada implementa a deteccao no microfone do PC;
nao altera o caminho de captura do painel remoto.

Foi corrigido o formato do PCM do microfone no filtro de eco: a matriz mono de
uma coluna agora e convertida em vetor antes da analise espectral. As leituras
do microfone e referencias de playback compartilham protecao de concorrencia.

Os testes usam audio sintetizado localmente em arquivo (sem tocar nos
alto-falantes), o VAD real, PCM de eco/silencio, eventos de servidor simulados
e dispositivo de reproducao simulado. Nao foi feita conversa com API real nem
calibracao do microfone/alto-falantes do usuario. Televisao, musica com voz,
outro falante e salas muito reverberantes ainda podem dificultar a separacao.

Verificacao: 281 testes passaram na bateria completa (302,372 segundos).
Os 18 testes especificos atualizados de interrupcao tambem passaram.
Sintaxe Python verificada e dependencias sem incompatibilidades detectadas.
