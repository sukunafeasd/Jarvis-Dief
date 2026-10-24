# Abertura incremental local

- Reutiliza hash previamente conferido apenas se caminho, tamanho, mtime_ns,
  ctime_ns, identidade do arquivo e hash esperado no RECORD continuam iguais.
- Cada arquivo continua sendo consultado; arquivo removido ou alterado invalida
  sua entrada. Cache ilegivel, de outra raiz, expirado ou com data futura exige
  leitura completa. Cache so e gravado apos uma inspecao sem danos.
- Leitura completa obrigatoria apos 24 horas. Este cache e um acelerador de
  manutencao, nao um mecanismo antimalware ou prova contra adulteracao hostil.
- Consulta remota fica limitada a quatro segundos na abertura de instalacao
  previamente confirmada. Instalacao inicial, transacao pendente e pacote local
  explicito conservam seus fluxos anteriores. Timeout nao declara atualizado.
- 40 testes de manutencao/distribuicao passaram. Ensaio no ambiente de testes:
  primeira leitura 34,89s; repeticao 14,29s, zero pacotes danificados em ambas.
  Nao representa tempo total de abertura nem benchmark do PC instalado.
- Somente local. Nenhuma release ou codigo enviado ao GitHub.
