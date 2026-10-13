# Atualizacao diaria e sons do painel

Data: 13/10/2026.

## Fluxo corrigido

- Primeira abertura do dia agenda atualizacao automatica depois da entrada, respeitando a preferencia de resumo automatico. Contato durante a abertura nao cancela essa atualizacao; ela aguarda a resposta em andamento.
- Retorno apos intervalo longo e cumprimentos seguem a politica existente: quatro horas de ausencia, com intervalo de quinze minutos entre atualizacoes automaticas. Pedidos explicitos de atualizar o dia ignoram esse intervalo e funcionam mesmo com resumo automatico desativado.
- O agendamento nao e mais cancelado por qualquer transcricao. A consulta e o resumo constituem uma transacao com identificador proprio, evitando eventos antigos fecharem uma tela nova.
- Noticias, agenda, tarefas, clima e sistema sao consultados de verdade antes dos capitulos. Google Agenda e usado quando conectado; caso contrario, a agenda local e consultada. Gmail conectado consulta contagens e cabecalhos de mensagens importantes nao lidas, sem afirmar leitura dos corpos.
- O resumo usa o pacote de resultados verificados. Fontes com erro sao identificadas, sem fabricar sucesso.
- A introducao termina antes de entrar no resumo. Cada assunto aguarda a fala e o audio anterior terminarem antes de trocar a apresentacao.
- Sem audio reproduzido, a entrega nao e marcada como concluida. A tela apresenta aviso para verificar voz/conexao e tentar novamente.
- A tela de consulta fica protegida de manifestacoes externas, e os capitulos nao expiram durante o resumo. Avisos nao essenciais, rotinas e entrada comum do microfone ficam suspensos durante essa sequencia. O comando local para continua disponivel para cancelar.
- Comandos digitados durante o resumo recebem aviso para aguardar ou cancelar; nao sao executados em paralelo.

## Tela e sons

- Quadro compacto no acabamento HUD existente: vidro escuro, textura tecnica e moldura vermelho/ciano.
- Topicos ativos aparecem acima da barra. O percentual corresponde a fontes finalizadas, incluindo erros identificados; nao avanca por temporizador.
- Sons originais curtos de abertura, clique, projecao, fixacao, repouso, despertar, modos espaciais, inicio de consulta, conclusao e aviso.
- Um efeito por vez, limite de repeticao e volume reduzido durante a voz. Nao ha musica espacial continua ou ruido a cada quadro.
- Arquivos PCM sao gerados no cache local. Nao ha download nem dependencia adicional. Ausencia do modulo multimidia desativa efeitos, sem impedir a abertura do Jarvis.

## Verificacao

- Onze testes novos de politica, fluxo, tela e sons aprovados.
- Resumo diario: 5 testes aprovados.
- Coleta/inicializacao: 7 aprovados.
- Capitulos: 3 aprovados.
- Voz/interrupcao: 22 aprovados.
- Auditorias anteriores de interface: 44 aprovados.
- Atualizacao visual: 2 aprovados.
- Audio concorrente/cancelamento: 2 aprovados.
- Total dos conjuntos focados: 96 testes aprovados.
- Quatro sequencias Qt/WebEngine nativas aprovadas: persistencia da consulta, progresso real, capitulos sem expiracao e liberacao da transacao.
- Captura nativa inspecionada e sintaxe Python/JavaScript verificada.

## Limites

Validacao com dados sinteticos e provedores simulados; nao foi acessado conteudo pessoal nem feita escuta da voz real. A suite completa nao foi repetida nesta rodada. Nao houve novo EXE ou envio ao Git.

Para interromper por voz durante a consulta, o reconhecedor local de para precisa estar disponivel. Nao foi criada uma fila persistente de comandos digitados durante o resumo. O progresso termina quando as fontes concluem ou falham, nao quando todo o audio do resumo termina.
