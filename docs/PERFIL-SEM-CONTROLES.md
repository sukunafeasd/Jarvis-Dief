# Perfil sem controles duplicados

A estrela e o painel de Controles nao sao mais criados na interface.
F11 continua alternando tela cheia, sem botao dedicado. Pedidos antigos para
abrir controls sao redirecionados ao Perfil, sem recriar o painel removido.

Nome, cidade, visual Rosto/Nucleo e resumo inicial ficam no Perfil. Cor,
projecoes e voz continuam na pagina de Aparencia e voz. Troca de visual e
resumo tambem continuam disponiveis por comando semantico do Jarvis.

Preferencias antigas de wake word e push-to-talk nao bloqueiam mais a conversa.
Os getters de compatibilidade retornam falso, sem regravar ou apagar chaves
privadas ou outras preferencias do arquivo local. A interface nao expoe esses
modos nem inicia o aquecimento do detector de palavra-chave.

Repouso por interface_control rest on preserva a animacao do holograma.
Fala sustentada reconhecida localmente permite voltar sem Hey Jarvis,
reutilizando o detector de fala/volume da interrupcao e preservando o comeco
da frase. Ruido curto ou volume baixo nao devem acordar. Microfone silenciado
continua respeitado. Mensagem digitada tambem pode sair do repouso.

O despertar automatico desta rodada usa o microfone do PC. O comportamento
acustico real depende do ambiente; os testes usam PCM e callbacks simulados.
O toque no holograma e os comandos rest off continuam disponiveis.

Verificacao: 301 testes passaram na bateria completa (300,488 segundos).
Perfil revisado em captura real da interface Qt; visual e resumo estao na
mesma pagina. Sintaxe Python verificada sem erros.
