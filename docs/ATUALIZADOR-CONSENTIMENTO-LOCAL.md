# Atualizador com consentimento (alteracoes locais)

Implementado no codigo e instalado localmente como 2.0.13 em 2026-10-22,
sem publicacao no repositorio:

- Estados distintos para consulta, versao atual, versao local superior a publicada,
  nova versao, falha de consulta e versao rejeitada apos rollback.
- Escolha instalar/continuar na abertura de uma instalacao existente.
- Primeira instalacao e pacotes locais explicitamente selecionados preservam seu fluxo.
- Falhas de download nao sao substituidas por uma mensagem de sucesso.
- Consulta em segundo plano durante o uso, a cada 30 minutos; primeiro disparo
  apos 60 segundos. Sem consultas sobrepostas nem notificacoes repetidas da mesma versao.
- Aviso visual nao modal, adiado enquanto a abertura ou fala/processamento estiver ativo.
- Aviso verbal pela conexao existente somente quando o assistente estiver disponivel.
- Reinicializacao solicitada por arquivo exclusivo da sessao; o inicializador espera
  o aplicativo encerrar, libera seu proprio processo e reabre para consultar novamente
  o manifesto assinado. Consentimento antecipado vale somente para a mesma versao.

Validacao realizada: 51 testes automatizados focados, incluindo regressao do
atualizador, comparacao, consentimento, falha de download, consulta offline,
deduplicacao e comando de reinicializacao. Aviso Qt renderizado e inspecionado
com o backend Windows; o backend offscreen isolado nao carregou fontes do sistema.

Pacote 2.0.13 assinado com Equipe Dief, assinatura Authenticode valida,
manifesto assinado e hashes conferidos depois da assinatura. ZIPs e equivalencia
dos arquivos alterados tambem verificados. Instalacao local aplicada sobre a
2.0.11 (a 2.0.12 estava rejeitada). Inicializador confirmou abertura da aplicacao:
current=2.0.13, previous=2.0.11, pending=false.
Ainda requer ensaio de descoberta de uma release futura, reinicio solicitado
pelo aviso durante o uso e voz real. Nao foi feita publicacao.
Mantida a versao anterior como recuperacao; limpeza de arquivos compartilhados
obsoletos precisa de inventario de propriedade, nunca de apagar dados indiscriminadamente.
