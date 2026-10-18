# Agenda diaria e recuperacao do monitor

Alteracoes locais, sem publicacao ou mudanca de credenciais.

- A Agenda Google do resumo diario consulta o dia local inteiro, em vez de
  consultar a partir do horario atual sem limite final. Inicio e fim recebem
  o fuso correspondente a cada meia-noite. A especificacao de atualizacao
  preserva esses mesmos limites.
- O monitor ULTRON deixa de anunciar atividade quando a coleta ou o
  processamento de amostras falha. Registra somente a classe do erro,
  permite nova ativacao e remove o erro anterior ao reiniciar.
- Cancelamento normal nao e registrado como falha.
- A captura do teste visual diario usa pasta temporaria, evitando escrita
  bloqueada na pasta Documentos.

## Validacao

As duas falhas foram reproduzidas antes das correcoes. Cinco testes novos
cobrem limites do dia, virada do ano, falha de coleta/processamento,
reinicio e cancelamento. A bateria final passou: 170 testes, incluindo
atualizacao diaria, cards vivos, ULTRON, comandos naturais, Forja e audio
sintetico. Sintaxe dos quatro arquivos alterados validada. Revisao
adicional nao encontrou problemas concretos nestas alteracoes.

Sem consulta real a contas, varredura do Windows, nova chamada paga de voz
ou conversa pelo microfone. Os testes nao comprovam ausencia de todos os
bugs, nem a qualidade percebida da voz real.
