# Auditoria da interface - rodada 6

Data: 13/10/2026.

## Problemas reproduzidos e corrigidos

- Uma manifestacao de clima escondia o painel de uma operacao aguardando confirmacao. O painel agora permanece visivel tanto em running quanto em pending.
- Atualizacoes de uma operacao reiniciavam sua entrada e zeravam a opacidade, provocando piscadas. Uma superficie ja visivel preserva o progresso da animacao.
- Ativar movimento reduzido durante a entrada deixava o temporizador de animacao ativo. Agora ele para imediatamente e a superficie fica totalmente visivel.
- success, completed e done recebiam o mesmo rotulo generico de finished. Agora os estados confirmados aparecem como concluidos; finished continua indicando apenas etapa encerrada.
- A captura nativa revelou que o clima perdia a temperatura quando dividia espaco com execucao. O clima nao fixado em superficies de ate 360px de altura usa uma composicao compacta de duas colunas, com detalhes acessiveis por rolagem. Previa fixada e painéis maiores permanecem inalterados.

## Verificacao

- Os seis testes novos de operacao reproduziram cinco falhas antes da correcao e passaram depois.
- O teste visual novo reproduziu a temperatura fora do viewport (338px em uma superficie de 268px). Passou depois em 600x268 e 420x300.
- Testes de operacao da rodada anterior: 12 aprovados.
- Auditorias anteriores de interface: 44 aprovados.
- Terminal e espaco: 7 aprovados.
- Abertura do nucleo e atualizacao de contexto: 2 aprovados novamente apos o ajuste CSS.
- Total das execucoes focadas: 72 testes aprovados.
- Validacao nativa Qt/WebEngine: onze sequencias aprovadas, sem excecoes capturadas. Captura de clima e execucao inspecionada antes e depois.
- Sintaxe Python dos arquivos alterados verificada.

## Limites

Esta rodada usa dados sinteticos e um perfil isolado: nao acessa contas, nao envia mensagens nem executa comandos PowerShell reais. A suite completa nao foi executada. Nao foi produzido novo EXE nem enviado commit ao Git.

Mantem-se o limite do protocolo sem identificador unico para duas execucoes simultaneas da mesma ferramenta e etapa. Estes testes nao comprovam ausencia de todos os bugs ou sincronizacao com provedores reais de voz.

Avisos existentes de depreciacao de pynvml e Pillow permanecem fora do escopo.
