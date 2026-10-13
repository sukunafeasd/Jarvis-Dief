# Conexoes reais e controle do computador

## Auditoria

O projeto tinha zero plugins adicionais. send_message tentava importar um driver
WhatsApp ausente e caia em teclas cegas: busca do Windows, Ctrl+F e Enter.
Esse fallback podia reportar sucesso sem conferir janela, contato ou envio.
O usuario usa WhatsApp Web e iPhone, nao WhatsApp Desktop/Android.

## Implementado

- desktop_accessibility: janelas reais e controles UI Automation. Inspecao antes
  de acao, nomes/IDs/tipos exatos, bloqueio de ambiguidades e campos de senha.
- whatsapp_web: navegador isolado com sessao vinculada pelo usuario. Busca o
  contato, confirma cabecalho, preserva rascunhos e confere nova mensagem no DOM.
  Nunca usa Windows Search nem declara entrega/leitura. Resultado incerto nao
  dispara reenvio ou outro metodo.
- gmail_control: OAuth Google, leitura de cabecalhos e monitoramento opcional de
  novas mensagens na caixa de entrada. Token protegido por DPAPI do Windows.
  Nenhum envio, exclusao, alteracao de leitura ou leitura automatica de corpos.
- Configuracoes > Conexoes: conectar/verificar WhatsApp Web, conectar Gmail,
  vincular iPhone pelo aplicativo Microsoft ja instalado e acesso remoto.
- browser_control: listar/trocar abas da sessao controlada. Nao finge enxergar
  abas pessoais fora da sessao. Operacoes expiradas cancelam a tarefa.
- Prompt recebe plugins ativos e estados de conta, sem credenciais.

## O que depende do usuario

WhatsApp: Conectar WhatsApp Web, escanear o QR no iPhone (Configuracoes >
Aparelhos conectados > Conectar aparelho) e Verificar WhatsApp Web. A sessao
isolada exige esse pareamento, mesmo que outro navegador ja esteja conectado.

Gmail: criar projeto Google, habilitar Gmail API, configurar consentimento e
baixar credenciais OAuth para aplicativo de computador. Se estiver em teste,
adicionar a conta como usuario de teste. Selecionar esse JSON em Conectar Gmail
e autorizar no navegador. Chave Gemini/OpenAI nao substitui OAuth Google.
Depois pedir ao Jarvis para monitorar o Gmail. O monitor verifica a cada 90s,
estabelece uma base inicial e anuncia contagens em momentos de silencio.

iPhone: Vincular ao Celular da Microsoft exige pareamento Bluetooth e
permissoes no telefone. Acesso remoto do Jarvis controla o PC pelo navegador.
Nenhum dos dois concede controle irrestrito dos aplicativos do iPhone.

## Validacao e limites

45 testes automatizados aprovados. A pagina publica real do WhatsApp Web abriu
e exibiu o login, sem conta vinculada e sem nenhuma mensagem enviada.

Testes de WhatsApp usam uma pagina local controlada, sem enviar mensagens reais.
Gmail OAuth e monitoramento usam simulacoes e tokens temporarios ficticios:
nenhuma conta pessoal foi autorizada. O layout foi capturado em
validation/connections-native.png. A verificacao nativa leu e acionou o botao
de uma janela de teste propria, confirmando o evento no aplicativo.

Seletores de WhatsApp Web podem mudar. Nesse caso o conector falha explicitamente
em vez de digitar no lugar errado. Contatos com nomes duplicados requerem
desambiguacao; usar o nome exato salvo. UI Automation nao cobre todos os
aplicativos/desenhos personalizados nem remove limites de privilegio do Windows.

Fontes oficiais:
- https://pywinauto.readthedocs.io/en/latest/getting_started.html
- https://developers.google.com/workspace/gmail/api/quickstart/python
- https://playwright.dev/python/docs/api/class-browsercontext
- https://support.microsoft.com/en-us/windows/apps/phonelink/phone-link-requirements-and-setup
