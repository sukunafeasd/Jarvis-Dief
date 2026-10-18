# Continuidade de estado e avisos

Rodada local, sem publicacao ou alteracao de credenciais.

## Problemas corrigidos

- clear agora informa tambem hologramas livres fixados que continuam na
  cena, nao apenas os cards de pinned_previews.
- Mover ao centro exige geometria realmente centralizada quando nao ha
  apresentacao. Composicao automatica nao e anunciada como alinhamento
  visual verificado sem evidencia.
- ULTRON exige antivirus habilitado e protecao em tempo real habilitada
  para exibir protecao ativa. Leituras parciais nao bastam.
- Polls do ULTRON nao substituem o contexto escolhido de cofre ou simulacao
  por diagnostico. Uma nova resposta de comando ainda pode mudar o contexto.
- Atualizacoes antigas da Forja nao podem substituir o novo trabalho nem
  anunciar a previa anterior como conclusao do pedido atual.

## Ordem das atualizacoes da Forja

Cada comando mutante admitido pelo host recebe command_epoch crescente.
Admissao e envio ao worker usam o mesmo lock; a espera pelo resultado ocorre
fora dele. Comandos simultaneos nao podem receber uma ordem e ser enviados
na ordem inversa. O marcador command_pending permanece ativo para o pedido
mais recente, mesmo se um comando anterior terminar primeiro.

A tela descarta snapshots com epoca antiga ou serial regressivo. Os avisos
de voz validam novamente a epoca antes de agendar e antes de falar. A janela
entre receber o pedido e envia-lo ao runtime tambem bloqueia avisos antigos.
Um aviso novo substitui o anterior com seu proprio snapshot, sem herdar a
epoca antiga de uma tarefa que ainda esperava a voz ficar livre.

Se o comando expirar, a previa antiga e preservada, mas o estado informa
falha/necessidade de verificacao. Nao volta a informar sucesso so porque
existe uma previa antiga validada. Nao ha repeticao automatica do pedido.

## Testes

Regressoes com barreiras controladas cobrem poll atrasado, dois comandos de
threads diferentes, comando pendente, timeout e avisos aguardando audio.
Regressoes WebGL usam leituras sinteticas de protecao e verificam a troca e
preservacao de contexto. Nao executam limpeza, reparos ou chamadas pagas de
IA. Os testes de audio usam PCM sintetico; nao foi feita nova conversa real
de microfone nesta rodada.

Resultado final: bateria de 253 testes executada, 252 aprovados e um ignorado
pela indisponibilidade de criacao de link simbolico no ambiente de teste.
Ensaio nativo da Forja aprovado: entrada, saida, fixados restaurados, F11,
repeticao com movimento reduzido e cancelamento sem callbacks atrasados.
