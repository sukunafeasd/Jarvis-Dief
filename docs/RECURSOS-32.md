# Recursos do DIEF JARVIS: acompanhamento dos 32 itens

Nao ha 32 conexoes prontas ou uma garantia de controlar qualquer aplicativo.
Os recursos compartilham modulos. Ha 24 plugins descobertos. Instalar um
modulo nao autoriza uma conta externa.

## Implementado nesta etapa

| Item | Recurso | Situacao real |
| --- | --- | --- |
| 1 | Contexto de aplicativos | Base anterior de contexto/UIA/DOM preservada; nao promete controle universal. |
| 2 | Verificacao | Ledger registra retorno real sem tratar tool_reported como prova independente. Operacoes confirmadas tem job consultavel. |
| 3 | Planejador | Etapas, cancelamento e vinculo a evidencias reais. Nao executa o plano automaticamente. |
| 4 | Memoria contextual | Memoria anterior preservada; registros locais e biblioteca adicionados. Busca lexical, nao embeddings. |
| 5 | Conhecimento pessoal | Indexacao explicita, fonte, hash e indicacao de fonte alterada/incompleta. |
| 6 | Conexoes | Novos destinos/configuracoes e estados pendentes/testados; sem autorizacao automatica. |
| 7 | Controle Windows | UIA existente preservada; nao foi reescrito nesta etapa. |
| 8 | Diagnostico | Dependencias/arquivos e reparo somente de pacotes declarados, com confirmacao. |
| 9 | Gmail ampliado | Rascunhos e envio em token separado; nao amplia a autorizacao somente leitura anterior. |
| 10 | WhatsApp | Transporte e testes anteriores preservados; nenhuma mensagem real enviada nesta etapa. |
| 11 | Outlook | Login MSAL/Graph, leitura paginada e envio com confirmacao; Mail.Send exige autorizacao atualizada. Aceitacao nao prova entrega. |
| 12 | Contatos | Cadastro local, apelidos e recusa de selecao ambigua. Nao sincroniza todos os provedores automaticamente. |
| 13 | Agenda inteligente | Conflitos e intervalos livres da fonte consultada; pagina incompleta/eventos sem horario impedem disponibilidade confirmada. |
| 14 | Projetos | Projetos/subtarefas locais com prazo, prioridade e conclusao. |
| 15 | Notas | Notas internas, cofre Markdown/Obsidian e Notion configuravel; paginas precisam ser compartilhadas com a integracao. |
| 16 | Reunioes | Transcricao de arquivo de audio pelo Gemini apos confirmacao, extrato e candidatos a tarefas sujeitos a revisao; sem gravacao ao vivo automatica. |
| 17 | Busca local | Nome, metadados e conteudo textual em pasta explicita; maximo 2000 arquivos/15 segundos. |
| 18 | Organizador | Duplicados por hash sem excluir; movimentacao confirmada com comprovante para desfazer. |
| 19 | Documentos | Leitura anterior + comparacao de trechos e criacao de DOCX/TXT/MD novos. |
| 20 | Planilhas | Criacao XLSX/CSV, estatisticas, grafico de barras e edicao de celulas em copia nova. Formulas fornecidas como texto nao executadas. |
| 21 | Imagens | OCR, conversao PNG/JPG/WEBP e anotacoes rect/text em copia nova, com limites de coordenadas. |
| 22 | Clipboard | Leitura explicita e escrita confirmada. Sem coleta continua. |
| 23 | Downloads/conversao | HTTPS publico solicitado, limite de 25 MB, sem executar; redirecionamento exige URL final. Anexos/Drive anteriores preservados. |
| 24 | Git | Status, resumo de diff e historico; nao publica, nao executa hooks nem testes arbitrarios por este plugin. |
| 25 | Casa inteligente | Home Assistant REST: consulta e controle confirmado de luzes/switches/fans. Token protegido. Fechaduras/alarmes fora do controle inicial. |
| 26 | iPhone | Abre pareamento Microsoft e informa limites. Atalhos iOS e controle amplo nao implementados. |
| 27 | Midia Windows | Volume com leitura posterior e lista de saidas. Controle de sessoes/selecionar saida pendente; Spotify anterior preservado. |
| 28 | Pesquisa | Pesquisa com fontes anterior preservada; nao substituida nesta etapa. |
| 29 | Monitoramento | Arquivos escolhidos, avisos somente ao mudar, enquanto Jarvis esta aberto. Monitores anteriores preservados. |
| 30 | Backup | Memoria/organizador/recursos/preferencias permitidas, manifesto e hash. Sem arquivos de tokens/sessoes. Recuperacao separada; aplicacao integrada ainda pendente. |
| 31 | MCP | SDK oficial, endpoint fixo e allowlist humana, confirmacao por chamada, reinspecao de schema. Sem stdio, instalacao de servidores ou OAuth MCP remoto. |
| 32 | Atualizador | Consulta releases oficiais, sem inventar versao local. Instalacao/assinatura/rollback dependem do pipeline de distribuicao ainda pendente. |

## Configuracao

Em Conexoes, Gmail rascunhos usa a credencial OAuth de computador do Google,
mas exige uma nova autorizacao para gmail.compose; o leitor anterior fica intacto.
Outlook exige registro de aplicativo publico Microsoft e login da conta.
Home Assistant exige servidor e token do proprio usuario. MCP exige endpoint
e nomes de ferramentas permitidas. Nenhum desses dados acompanha os defaults.

Novos registros ficam em memory/resources.sqlite3, ignorado pelo Git. Tokens
Microsoft/Home Assistant/Google novos usam o armazenamento DPAPI existente.
O token do Home Assistant nao e salvo em texto no formulario de configuracao.

## Testes e limites

Testes usam contatos, documentos e contas artificiais. A ponte MCP foi testada
contra servidor local real com ferramenta de soma; Outlook, Gmail compose e
Home Assistant tiveram testes de contrato/mocks, nao contas reais autorizadas.
Nao foram enviados emails ou WhatsApps reais, movidos arquivos pessoais,
gravadas reunioes ou ligados dispositivos reais nesta rodada.

MSAL e MCP instalados no ambiente virtual e declarados em requirements.txt.
Uma conexao MCP simples nao implica suporte a qualquer servidor/autenticacao.
Nao ha novo EXE ou publicacao GitHub nesta etapa.

## Referencias oficiais

- MSAL Python: https://learn.microsoft.com/en-us/entra/msal/python/getting-started/acquiring-tokens
- Gmail drafts.send: https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.drafts/send
- Home Assistant REST: https://developers.home-assistant.io/docs/api/rest/
- MCP Python SDK v1: https://github.com/modelcontextprotocol/python-sdk/tree/v1.x

Este arquivo e um registro de implementacao, nao uma lista de todas as funcoes
concluidas. Os itens marcados como pendentes precisam de outras etapas e QA.

Verificacao desta etapa: suite geral com 319 testes aprovados em 306,652
segundos, mais dois testes novos de interface/criptografia aprovados em rodada
separada. Compilacao Python aprovada; pip check sem conflitos. MSAL 1.39.0
e MCP 1.30.0 instalados. Captura de Conexoes revisada em
validation/resource-connections.png. Avisos de descontinuacao existentes nao
impediram os testes. Nao foi feita medicao de CPU/GPU, teste de conta real,
lint independente, typecheck estatico ou geracao de um novo executavel.
