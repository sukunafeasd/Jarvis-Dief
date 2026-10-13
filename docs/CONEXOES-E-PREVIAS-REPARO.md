# Reparo de conexoes e previas fixadas

## Diagnostico real

- Spotify: autorizacao validada no servidor, conta Premium, zero dispositivos
  disponiveis no momento da consulta. Nenhuma musica foi tocada durante o teste.
- Google Drive: OAuth existente no Google, mas token local nao confirmado;
  tentativa de conectar recebeu HTTP 403 apos a autorizacao. O console mostrou
  Drive API nao ativada. Ativacao tentou o projeto da credencial, mas o Google
  Cloud falhou ao concluir. Nao declarar Drive conectado ou API ativada.
- Confirmacoes eram filhos da janela principal; configuracoes em janela cheia
  podiam cobri-las. Agora sao janelas modais proprias com foco no cancelamento.
- Resultado da autorizacao no formulario nao atualizava o registro de testes
  da pagina de Conexoes, deixando mensagem e estado anteriores.
- Previa fixada nao era persistida. Photos tambem dependiam do arquivo original.

## Correcoes

- Estado de Conexoes invalidado e atualizado ao terminar autorizacao no formulario.
- Tentativas duplicadas no mesmo formulario bloqueadas enquanto OAuth esta ocupado.
- Google: erro de API desativada separado de autorizacao/permissao. Candidato
  autorizado e salvo criptografado, separado do token ativo; teste pode promove-lo
  somente depois de conferir API e identidade. Falha preserva conexao ativa anterior.
- Spotify: mensagens especificas para 401, 403, 404 e limite. play pode resolver
  musica por query, abrir o player instalado se nao ha devices, aguardar e verificar
  faixa/is_playing. Nao escolhe aparelho arbitrario nem reenvia um play incerto.
- Callback OAuth Spotify nao editavel na tela; Client ID identificado claramente.
- Previa local de dados e posicao armazenada atomicamente com DPAPI. Restaurada
  como snapshot, sem dizer que dado antigo acabou de ser consultado.
- Fotos possuem copia de exibicao local; original nao e alterado. Fotos sem X
  ou botoes de restaurar; controle continua por comandos do Jarvis.
- Desfixar remove a entrada persistida. Caches locais nao entram na distribuicao
  publica: config exportado apenas pela lista permitida existente.

## Limites

- API Drive ainda depende de concluir ativacao no Google Cloud. Erros externos
  nao sao uma confirmacao escondida no Jarvis e nao desaparecem salvando uma chave.
- Fotos copiadas ficam em pin_assets local; nao ha coleta automatica dos arquivos
  antigos nesta rodada. Previa pode conter informacao privada e fica neste PC.
- Snapshot restaurado nao garante atualizacao de clima/email/agenda em tempo real.
- O reconhecedor de voz, renderer e as demais correcoes anteriores foram preservados.
- Nao houve envio de email/WhatsApp, compra, alteracao de arquivos no Drive,
  build de EXE ou publicacao GitHub nesta rodada.

## Validacao

- Suite geral: 362 testes aprovados. Suites focadas de conexoes, plugins,
  persistencia, modal e classificacao de erros repetidas apos os ajustes.
- Compilacao Python e dependencias verificadas sem erros.
- Testes de fotos e previas usam dados ficticios; contas reais somente consultadas.

## Fontes

- https://developer.spotify.com/documentation/web-api/reference/start-a-users-playback
- https://developer.spotify.com/documentation/web-api/tutorials/february-2026-migration-guide
