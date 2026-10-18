# Rodada local: modos, avisos e cenas

Data: 14/10/2026. Sem publicacao, compilacao de EXE ou alteracao de contas.

## Checklist de correcoes

- [x] Monitores verificam sessao, novo contato, geracao de resposta, repouso,
  mute, telefone, Forja, ULTRON e atualizacao diaria antes de consultar e antes
  de entregar avisos. Avisos de fundo preservam a condicao original de admissao
  ate o envio; as falas deliberadas do proprio protocolo continuam permitidas.
- [x] Falha de sensor fica isolada no monitor, sem derrubar a sessao.
- [x] Proatividade so registra seu intervalo depois de um envio aceito.
- [x] Gmail e rotinas nao agendam mais falas de fundo sem a verificacao final.
  Desativar um plugin durante a consulta impede a projecao daquele resultado.
- [x] Consultas e validacoes da Forja recebem identidade de entrada. Resultados
  antigos nao substituem a nova cena nem liberam uma operacao mais recente.
  Validacao ainda nao iniciada e descartada antes de abrir o navegador se a
  pessoa ja saiu. Validacao em andamento nao publica seu resultado apos a saida.
- [x] Carregamento diario e ocultado ao entrar na Forja e nao e restaurado como
  uma janela antiga. Retornos atrasados nao reabrem esse carregamento ali.
- [x] Restauracao de fixados espera o fim da Forja/ULTRON. Consultas dos fixados
  pausam enquanto a janela ou os proprios fixados estao escondidos.
- [x] Dar foco explicito a um texto depois da fala revela seu conteudo completo.
  Atualizar uma cena cancelada realinha o tempo com o audio ja reproduzido.

## Validacao

- 301 testes passaram na execucao final conjunta, incluindo os seis contratos
  da janela nativa da Forja, voz, dados, comandos, integracoes, fixados e cenas.
- Compilacao Python e verificacao de espacos do diff passaram.
- Revisao independente dos dois conjuntos de correcoes nao apontou outro
  problema acionavel no recorte revisado.
- O erro sintetico de recepcao exibido pelo ensaio de voz e intencional; a suite
  concluiu com sucesso.

Testes novos em `test_background_mode_guards.py` e `test_mode_lifecycle_round.py`
reproduzem trocas de sessao, contato e modo, resultados atrasados, falha de
sensor, validacao obsoleta, fixados escondidos e texto fora de sincronia.

Os testes da janela nativa da Forja cobrem sequencia de entrada, luz/painel,
pixels e movimento da previa isolada, F11, saida, cancelamento, geometria e
restauracao dos fixados. Usam uma previa local controlada, sem gerar projetos
na conta real.

## Limites

Nao houve sintese paga, avaliacao auditiva de microfone/alto-falantes, limpeza
ou reparo do Windows, nem benchmark de FPS do aplicativo inteiro. Uma consulta
que ja estava em andamento pode terminar; sua entrega e descartada quando
obsoleta. O controle de geracao nao termina uma thread ou navegador que ja
iniciou trabalho. Reiniciar o aplicativo carrega estas alteracoes locais.
