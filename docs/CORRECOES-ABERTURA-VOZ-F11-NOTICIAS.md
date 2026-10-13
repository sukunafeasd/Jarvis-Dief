# Abertura, voz, F11 e noticias

Data: 13/10/2026.

## Alteracoes

- Os documentos nativos do nucleo e do espaco iniciam em staging antes do primeiro quadro. Isso impede mostrar o nucleo em tamanho final e depois recuar para iniciar a aproximacao.
- Atualizacoes de estado nao cancelam e recriam continuamente o agendamento de quadros do nucleo. O renderizador preserva seu ciclo; uma avalancha de atualizacoes nao multiplica os quadros.
- Na superficie nativa, o nucleo nao exige preservar o framebuffer de cada renderizacao e nao solicita GPU em modo de baixo consumo. Documentos isolados dos testes conservam a captura de canvas.
- F11 passa pelo filtro de eventos do aplicativo, inclusive com foco no WebEngine. Repeticao automatica da tecla nao alterna a janela varias vezes; configuracoes visiveis recebem a alternancia na propria janela.
- Noticias com nucleo disponivel usam a projecao interna tanto durante a fala quanto depois. O fim da fala muda a projecao para settled, sem retirar as noticias do nucleo. A pagina frontal permanece oculta.
- Sem narracao ativa, noticias podem aparecer internamente no estado settled. Conclusao revela os itens do grupo atual sem iniciar um carrossel automatico.
- Saida PCM usa o tamanho de bloco escolhido pelo dispositivo e buffer de maior estabilidade. A escrita de audio comeca em paralelo com a analise dos visemas, que sai do ciclo principal.
- Cancelamento aguarda a escrita em andamento antes de fechar o dispositivo. Uma escrita antiga nao avanca a apresentacao cancelada; falta de audio reportada pelo dispositivo reinicia a ancora visual.

## Validacao

- Voz/interrupcao: 22 testes aprovados.
- Audio concorrente/cancelamento: 2 testes novos aprovados.
- F11, staging e agendamento: 4 testes novos aprovados.
- Interface das auditorias anteriores: 44 testes aprovados.
- Noticias: 6 testes aprovados, incluindo permanencia interna depois da narracao.
- Total dos conjuntos focados: 78 testes aprovados.
- Aplicacao nativa Qt/WebEngine: onze capturas aprovadas, incluindo dois quadros intermediarios da aproximacao, modos e limpeza. F11 testado no foco interno do WebEngine para sair e voltar a tela cheia.
- Capturas da aproximacao e noticias internas inspecionadas.
- Sintaxe Python e JavaScript dos arquivos alterados verificada.

## Limites

Nao foi executada novamente a suite completa nesta rodada. Nao houve geracao de novo EXE nem envio ao Git. Dados locais, credenciais e conexoes nao foram alterados.

O audio foi validado com dispositivo simulado; nao foi feita escuta da voz real nem medicao de falhas da rede/driver do computador. O buffer maior pode aumentar levemente a latencia, em troca de estabilidade. Essas mudancas nao garantem ausencia de toda falha de audio em qualquer dispositivo.

Quando o nucleo nao existe, falha ou o visual e rosto, a alternativa legivel de noticias ainda e mantida para nao perder informacao. No modo nucleo funcional, nao ocorre mais a passagem automatica das noticias para a frente.
