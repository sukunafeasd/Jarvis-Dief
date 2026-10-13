# Seis integracoes essenciais do Dief Jarvis

Foram adicionados seis plugins ao projeto, preservando os tres anteriores.
Reabra pelo atalho existente: a descoberta de novos plugins acontece no inicio.

## Conexoes

Em Configuracoes > Conexoes aparecem os plugins instalados e seus estados.
Conectado exige verificacao do servico; biblioteca ou credencial salva nao
equivalem a login confirmado. Ferramentas locais possuem Testar ferramenta.

### Google Agenda

1. Ative a Google Calendar API no projeto Google Cloud da credencial OAuth.
2. Nas configuracoes do plugin informe a conta desejada. O campo JSON pode
   ficar vazio para usar a credencial de aplicativo para computador do Gmail.
3. Autorize Google Agenda no navegador. O token fica separado do Gmail.

Permissoes: consultar calendarios e consultar/criar/alterar/excluir eventos.
Exclusao exige pedido explicito e um identificador real. A agenda local continua
separada. Quando Google Agenda estiver autorizado e o plugin ativo, o resumo
do dia passa a consultar essa fonte e identifica sua origem.

Exemplos: "Veja minha agenda Google de hoje", "Crie um compromisso amanha
das 14h as 15h", "Leia os detalhes daquele compromisso". Datas desconhecidas
nao podem ser inventadas e devem ser esclarecidas na conversa.

### Google Drive

Ative a Google Drive API e autorize o plugin da mesma maneira. Acesso somente
leitura: pesquisar nomes, consultar metadados, baixar arquivos e exportar
documentos Google. Download nao significa leitura: documentos le o caminho
retornado. Limite de 25 MB por arquivo. Nenhum arquivo e executado.

### Spotify

Cadastre um aplicativo em https://developer.spotify.com/dashboard e informe
seu identificador nas configuracoes. Cadastre exatamente este retorno:
http://127.0.0.1:8767/callback

Clique em Autorizar Spotify. Usa PKCE, sem pedir segredo de cliente. A conta
deve cumprir as regras atuais do Spotify; controle de reproducao exige Premium
e um dispositivo Spotify Connect disponivel. A API nao permite contornar essas
condicoes. Pesquisa retorna musicas reais; reproducao deve ser verificada pelo
estado atual. Os comandos nao dependem de adivinhar botoes na tela.

## Ferramentas locais

- Navegacao estruturada: Playwright existente, sessao propria e segundo plano
  por padrao. IDs de controles observados expiram em 90 segundos. Usa rotulos
  reais, rejeita senhas, verifica preenchimento e exige nova inspecao apos acao.
  Nao controla automaticamente abas pessoais nem controles dentro de iframes.
- Documentos e anexos: texto paginado de PDF, DOCX, XLSX, PPTX, TXT/CSV e OCR de
  imagens. Tesseract foi instalado com portugues e ingles. PDF escaneado sem
  texto e identificado como incompleto, nao transcrito ficticiamente. Anexos
  reais do Gmail podem ser listados e baixados antes de leitura. Macros, codigo
  e instrucoes recebidas nunca sao executados pelo leitor.
- Rotinas pessoais: consulta imediata ou agendamento uma vez/diario de tarefas,
  agenda, Gmail importante, clima e noticias. Horario futuro com fuso, registros
  persistentes, limite de 100 rotinas e controle de duplicacao. Executam com o
  Jarvis aberto e disponivel; nao sao um servico permanente do Windows.

## Seguranca e verificacao

Tokens Google Agenda, Drive e Spotify sao isolados e protegidos por DPAPI para
o usuario do Windows. Nova autorizacao de uma conta Google diferente da conta
solicitada nao substitui a conexao anterior. Conteudo recebido e dado externo,
nao permissao para agir. Falhas de API nao sao anunciadas como sucesso nem
provocam repeticao cega de envios ou alteracoes.

Os testes usam contas ficticias e APIs simuladas. Navegacao e leitura local
foram exercitadas de verdade, incluindo OCR em portugues. Nao houve login,
criacao de eventos ou reproducao em contas reais nesta rodada.

Resultado de validacao: suite completa de 239 testes aprovada em 250,837
segundos. Depois dos ajustes finais de exibicao, 12 testes de conexoes/painel
e 25 testes dos plugins foram aprovados novamente. Compilacao de sintaxe
aprovada e pip check sem conflitos. O teste antigo de descoberta foi atualizado
para exigir exatamente os nove plugins instalados, em vez de apenas tres.

Fontes oficiais consultadas:
- https://developers.google.com/workspace/calendar/api/v3/reference/events/insert
- https://developers.google.com/workspace/drive/api/guides/manage-downloads
- https://developer.spotify.com/documentation/web-api/tutorials/code-pkce-flow
- https://developer.spotify.com/documentation/web-api/references/changes/february-2026
