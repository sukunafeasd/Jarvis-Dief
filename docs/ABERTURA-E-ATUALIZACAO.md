# Abertura e atualizacao de contexto

O inicio de main.py chama o bootstrap antes de importar a interface e o audio.
A janela de inicializacao mostra verificacoes reais de pacotes declarados,
arquivos essenciais, dispositivos de audio, credencial da IA e contas salvas.
A conexao efetiva da IA e validada pelo fluxo normal do painel, nao por um
indicador ficticio na janela inicial.

Pacotes ausentes podem ser instalados automaticamente somente no ambiente
virtual privado, usando o PyPI e requirements.txt. Nao ha atualizacao forcada
de pacotes ja instalados nem instalacao de plugins desconhecidos. Em EXE
empacotado, dependencia ausente requer reparacao do pacote; nao se instala
Python dentro do executavel. Arquivos essenciais ausentes interrompem a abertura.
Contas desconectadas e servicos indisponiveis sao avisos, nao autorizacoes novas.
O bootstrap nao solicita QR, consentimento Google ou senha automaticamente.

Na primeira conexao do painel, o holograma faz uma entrada curta e a voz pode
cumprimentar. A saudacao nao se repete em reconexoes, nao sobrepoe um pedido ja
recebido e respeita repouso/wake word. Movimento reduzido mantem entrada simples.

Com a atualizacao habilitada, o primeiro inicio/contato do dia consulta noticias,
clima, agenda local, tarefas locais e sistema. Gmail conectado acrescenta apenas
contagens da caixa de entrada, sem leitura de assuntos ou mensagens. Google
Agenda nao e declarado conectado: a agenda desta coleta continua local.

O andamento aparece dentro da area do holograma principal, sem um segundo objeto
3D. A frase inicial informa a consulta; os fatos sao apresentados apenas depois
de a coleta terminar. Falhas permanecem identificadas no pacote. Noticias seguem
a apresentacao ilustrada e sincronizada com a fala existente.

Saudacoes e pedidos de atualizacao podem renovar o resumo depois de quinze
minutos. Quatro horas sem contato tambem tornam a atualizacao pertinente.
O dia, a ultima atualizacao e o ultimo contato sao persistidos localmente.
Interromper ou entrar em repouso cancela a apresentacao pendente. O resumo so e
marcado como entregue depois de a resposta terminar, sem marcar sucesso antecipado.

Testes usam fontes simuladas para sucesso, falha, cancelamento e deduplicacao.
Validacao Playwright cobre os elementos reais da apresentacao em janelas grandes
e pequenas, ausencia de sobreposicao, e pixels/movimento do nucleo WebGL.
As imagens em validation/context-refresh-* sao demonstracoes com dados de teste.
Validacao completa com a voz e todas as contas reais exige abrir o Jarvis novamente.
