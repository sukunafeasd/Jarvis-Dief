# Contexto, F11, fixados e modos

Data: 13/10/2026.

## Atualizacao de contexto

Pedidos como se atualize, me atualiza e atualize seu contexto agora consultam as fontes, guardam o pacote verificado em _day_context e enviam esses fatos para a sessao ativa sem solicitar fala nesse envio. Depois ha uma confirmacao curta, sem apresentar os capitulos de noticias/agenda/tarefas.

Um resumo completo permanece disponivel com me de um resumo do dia. A abertura automatica e os cumprimentos continuam usando o resumo conforme a preferencia existente. A atualizacao manual confirmada evita uma segunda apresentacao automatica imediatamente depois.

## F11

O atalho DIEF JARVIS da area de trabalho foi conferido: aponta para o pythonw do ambiente privado e main.py deste projeto.

A alternancia agora usa a janela que recebeu o comando, em vez de escolher configuracoes apenas porque estavam visiveis. As paginas WebEngine possuem tambem um encaminhamento local de F11 para a janela do aplicativo quando o evento chega ao documento, evitando depender exclusivamente do filtro Qt.

## Limpeza

Clear fecha informacoes temporarias e nao chama mais a remocao das previas. Dados, fotos, contexto fixado e elementos criativos pinned permanecem. A biblioteca visual recebeu uma variante de limpeza que conserva objetos pinned.

As instrucoes do assistente e da ferramenta foram corrigidas para nao associar limpar tela a desfixar. Remocao de fixados continua sendo uma acao separada.

## Modos

- A grade do ambiente foi retirada da renderizacao em todos os modos.
- A iluminacao do fundo muda entre assistente, analise, execucao, foco e exploracao.
- Analise usa aneis mais abertos/inclinados e movimento mais lento.
- Execucao usa outra inclinacao e maior ritmo orbital, sem fabricar etapas executadas.
- Foco recolhe a esfera externa, aneis e segmentos decorativos, destaca o reator central e reduz movimento/fundo. Noticias fundidas preservam a esfera que as envolve.
- Exploracao conserva planetas e orbitas reais da biblioteca.
- Um modo explicitamente pedido nao e mais substituido por foco devido a um contexto antigo de leitura. Configuracoes abertas ainda priorizam foco.

## Verificacao

102 testes focados aprovados: 6 novos, 7 de coleta, 17 de ambiente, 17 da biblioteca visual, 11 de atualizacao e 44 das auditorias de interface.

Tres sequencias nativas Qt/WebEngine aprovadas: clima fixado permanece ao limpar; F11 interno do documento sai de tela cheia; F11 interno volta a tela cheia. Os testes adicionais conferem direcionamento com configuracoes visiveis, contexto verificado sem cards de resumo e diferencas entre capturas dos quatro modos do nucleo.

Sintaxe Python/JavaScript verificada. Capturas dos modos inspecionadas.

## Limites

Os processos ja abertos precisam ser encerrados e reabertos para carregar os novos arquivos. Nao houve novo EXE ou envio ao Git, nem alteracao de contas/credenciais.

Nao foi executada novamente a suite completa. Os testes usam dados e sessao simulados; o encaminhamento F11 foi testado no WebEngine nativo, nao em todos os teclados/drivers. O contexto do dia e mantido na sessao em memoria, nao foi criado um novo arquivo permanente com dados pessoais.
