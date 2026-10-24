# Atualizador local: manutencao e compatibilidade

O inicializador existente consulta a release oficial, valida manifesto assinado e
hashes, prepara dependencias e verifica o aplicativo antes de confirmar a troca.
Uma publicacao somente de codigo no GitHub nao equivale a uma release utilizavel:
o canal requer manifesto, pacote de aplicativo, runtime e inicializador compativeis.

## Melhorias no codigo

- Atalho de dependencias compara requirements, interpretador e inventario de
  pacotes instalados. Quando iguais ao ultimo ambiente preparado com sucesso,
  evita pip install; a verificacao integral de arquivos RECORD e o teste do
  navegador privado continuam obrigatorios. Nao foi removida a verificacao de
  hashes de pacotes baixados.
- Alteracao de requirements/Python/pacotes, registro ausente ou invalido volta ao
  preparo convencional. Registro de sucesso so e escrito depois de verificar
  integridade e navegador. Cancelamento nao dispara instalacao por engano.
- Inicializador reconhece helpers antigos que aceitam somente --inspect. Nesses
  casos mantem pip, integridade e navegador, sem exigir os novos argumentos.
- Confirmacao de abertura limpa versoes numeradas obsoletas, conservando atual e
  anterior, e conserva o backup de runtime necessario para rollback. Nao limpa
  antes da confirmacao nem durante transacao interrompida.
- Limpeza limitada aos diretorios gerenciados: ignora junctions/symlinks no nivel
  dos candidatos, nomes desconhecidos e arquivos ocupados. Nao remove data,
  contas, historico, projetos ou browsers. Falha de manutencao nao desfaz abertura.

## Verificacao

30 testes de distribuicao/manutencao passaram. Incluem migracao simulada
1.0.0 -> 2.0.7, preservacao de dados, download invalido/offline, rollback,
interrupcao, integridade, limpeza de junctions Windows e execucao real do parser
antigo em ambiente temporario. Instalacoes e downloads dos cenarios sao simulados;
nao foram apagadas versoes nem instaladas dependencias do usuario nestes testes.

Revisao independente identificou incompatibilidade do novo CLI com rollback;
corrigida com negociacao de capacidade e teste do parser legado.
Grupos adicionados a auditoria geral para rodadas futuras.

## Limites desta entrega

Somente codigo local. EXE instalado ainda 2.0.7, sem estas mudancas.
Sem nova assinatura/build ou publicacao no GitHub. Versoes antigas ja distribuidas
nao recebem codigo retroativamente: dependem de uma release compativel ou novo
instalador. Nao foi medido tempo real de instalacao/abertura nem validado o canal
GitHub ao vivo nesta rodada. Verificacao integral de arquivos ainda pode ser
demorada; o atalho elimina a etapa pip redundante, nao promete abertura instantanea.
Versao anterior e mantida de proposito para recuperacao, nao como codigo ativo
misturado com a versao atual.

## Segunda rodada: caminho de abertura e reparo direcionado

- A pre-verificacao gerenciada nao faz chamadas online a Gmail nem inicia o
  transporte WhatsApp. Exibe conexoes como pendentes de verificacao no painel,
  nao como conectadas. Credenciais e estado de autorizacao nao sao alterados.
  O bootstrap direto conserva a verificacao anterior por padrao.
- Ambiente Python ja validado retorna imediatamente, sem repetir o mesmo
  subprocesso de importacao de pip/ssl/venv. Ambiente quebrado continua sendo
  recriado e validado antes de uso.
- Para lock com versoes exatas e hashes SHA256, reparo seleciona somente as
  distribuicoes danificadas e conserva todos os hashes dessas entradas. Usa
  --no-deps porque o ambiente completo ja foi preparado e inspecionado.
- Formato de lock complexo, sem hashes ou pacote desconhecido preserva o
  caminho integral anterior. Nao escolhe versao nova arbitrariamente.
- Lock temporario de reparo e removido ao terminar, inclusive em falha. Uma
  segunda verificacao de integridade e obrigatoria; dano remanescente bloqueia
  declaracao de sucesso.

38 testes focados passaram em 4,855s no ambiente de testes. Esse tempo nao e
benchmark de instalacao/abertura real. Inclui reparo simulado ponta a ponta,
checagem posterior, falha persistente, preservacao de hashes, cleanup temporario,
cancelamento, compatibilidade legado, rollback e migracao entre versoes.
Grupo incluido na auditoria ampla para rodadas futuras.
Alteracoes continuam somente no codigo local; EXE instalado nao foi substituido.
Revisao independente sem achados no escopo desta rodada. Verificacao sintatica
por AST passou nos quatro modulos. py_compile nao conseguiu escrever seu arquivo
temporario em core/__pycache__ (Errno 2); nenhuma permissao foi alterada para
contornar a limitacao. Testes de importacao/execucao acima passaram normalmente.

## Pacote local 2.0.8

Gerado em 20/10/2026, sem push nem publicacao de release. Artefatos em
%LOCALAPPDATA%/DIEF-JARVIS-Builds/2.0.8-local. O atalho
"Instalar DIEF JARVIS 2.0.8 local" fornece --local-artifacts para instalar
exatamente este pacote, em vez de consultar a release remota.

- 38 testes de distribuicao e manutencao passaram novamente.
- Assinatura Authenticode valida neste computador, certificado Equipe Dief
  B77C85CDABB34F3C30A9432413A6A6A83D1329C6. Autoassinado, sem garantia de
  confianca automatica em outros computadores.
- Manifesto Ed25519, SHA256SUMS e integridade dos dois ZIPs verificados.
- 656 arquivos da aplicacao conferidos byte a byte contra a copia isolada;
  modulos alterados conferidos tambem contra o codigo local.
- Auditoria de recursos 3D e credenciais passou. Probe Qt isolado carregou
  index, space e presentation com ready=true; holograma, ULTRON e sistema
  solar renderizaram. Nao equivale a ensaio completo do aplicativo instalado.
- Instalador ainda nao executado; contas e instalacao existente nao alteradas.
  Nao houve novo teste ponta a ponta de voz nem benchmark de abertura.
