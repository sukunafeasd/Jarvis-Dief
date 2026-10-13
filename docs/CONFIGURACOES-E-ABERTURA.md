# Configuracoes e abertura

O painel inicia em tela cheia. Configuracoes tambem abrem em tela cheia,
com navegacao lateral e tema preto-violeta texturizado, independente da paleta do
holograma. As paginas sao Perfil, Aparencia e voz, Atividade, Chat, Conexoes
e IA e memoria. Ferramentas auxiliares abertas por esse painel permanecem
no mesmo ambiente e oferecem retorno, preservando seus callbacks existentes.

Texto branco, destaques lilas e brilho suave nas acoes principais preservam
o contraste. Um traco de entrada anima ao abrir/trocar de topico por 420 ms;
nao ha loop permanente. Movimento reduzido desliga esse efeito. Ocultar a
janela encerra a animacao imediatamente.

Os controles de cor e voz agora ficam na pagina de aparencia. A chave da
IA pode ser substituida na propria pagina IA e memoria e nunca e preenchida
com a credencial salva. Salvar inicia o fluxo de reconexao existente, sem
afirmar que a autenticacao foi aprovada antes de o provedor responder.

Na entrada principal, o Windows precisa confirmar privilegios de administrador
antes do bootstrap de dependencias, contas ou audio. Sem elevacao, uma tela
oferece reiniciar usando runas. Cancelar o UAC nao abre o painel sem permissao.
O pedido do Windows deve ser confirmado pelo usuario; nao ha bypass de UAC.

O cursor fica invisivel depois de vinte segundos parado sobre o Jarvis ativo.
Movimento, clique, rolagem ou tecla restauram o cursor. Trocar de aplicativo,
fechar ou ocultar o painel tambem restaura. O cursor nao e ocultado sobre
outros aplicativos. A dica de arrastar/tocar do holograma foi removida.

Testes cobrem salvamento, protecao das credenciais, independencia da paleta,
tela cheia das configuracoes, ferramentas internas, limites do cursor e
argumentos/cancelamento da elevacao. Capturas Qt usam fontes instaladas e
tamanhos 800x600, 1366x768 e 1920x1080. UAC real e funcionamento em uma sessao
interativa continuam dependendo da reabertura pelo usuario. Nenhum novo EXE
foi empacotado nesta rodada.
