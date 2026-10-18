# Rodada de correcoes: voz, FORJA e ULTRON

Alteracoes locais, sem publicacao e sem substituir conexoes pessoais.

## Checklist

- [x] Impedir troca silenciosa de Fish para voz nativa durante falhas/reconexao.
- [x] Invalidar PCM, callbacks e trechos antigos depois do cancelamento.
- [x] Descartar repeticoes de transcricao sem impedir uma nova resposta legitima.
- [x] Evitar saudacao sobreposta a fala pendente.
- [x] Retirar X e seta do painel FORJA; Enter envia e Shift+Enter quebra linha.
- [x] Mostrar status real resumido, sem comandos brutos ou fragmentos do agente.
- [x] Nao executar duas vezes o mesmo turno de comando recebido.
- [x] Tratar perguntas de progresso como consultas, nao como novas criacoes.
- [x] Recuperar o ultimo projeto ao reabrir, mantendo a conversa e os arquivos.
- [x] Preservar a ultima previa valida quando a candidata falha.
- [x] Separar falha de validacao de falha na geracao; nao reiniciar automaticamente.
- [x] Corrigir falso erro de service worker criado pelo verificador Playwright.
- [x] Publicar identidade da revisao junto com a URL da candidata, sem corrida.
- [x] Retomar trabalhos ativos sem anunciar falso estado pronto.
- [x] Manter login disponivel mesmo se um projeto antigo nao puder ser retomado.
- [x] Rejeitar callbacks obsoletos e permitir nova verificacao apos trabalho ativo.
- [x] Conferir projeto, revisao e URL antes de aceitar a verificacao da candidata.
- [x] Suavizar a aproximacao da camera e a revelacao do painel.
- [x] Fixar ULTRON em coordenadas do mundo, sem ancora seguindo a camera.
- [x] Impedir atualizacoes atrasadas do ULTRON de alterar a tela durante a FORJA.

## Verificacao real

A rodada final executou 208 testes sem falhas, com um teste de links simbolicos
ignorado por indisponibilidade de permissao neste Windows. O ensaio nativo
passou por 28 verificacoes. A revisao independente encontrou corridas adicionais
de estado; elas foram corrigidas e receberam testes de regressao.

A previa local existente que aparecia rejeitada na captura foi aberta em perfil
isolado e passou em codigo, recursos, inicializacao, pixels e enquadramento,
sem erros de console. Nenhuma nova geracao foi necessaria. Sua revisao foi
preservada e marcada como validada a partir dessa verificacao real.

A voz Fish foi sintetizada e reproduzida pelo caminho de audio por 7,89 segundos,
sem falha registrada. Isso nao mede a acustica do ambiente nem garante latencia
zero da API. A voz nativa so pode ser usada quando explicitamente selecionada.

As transicoes foram verificadas com pixels e movimento no Edge em 1440x900 e
390x844; a janela Qt real passou pelas verificacoes de entrada, tela preta,
painel, F11, isolamento, restauracao de itens fixados, reentrada e cancelamento.

Os testes de motor usam servidor simulado; nao representam uma nova criacao
completa no provedor. Os testes de diagnostico nao executam limpeza, reparo ou
acoes destrutivas no computador. Os limites de uso da conta continuam sendo
controlados pelo provedor, e nao sao contornados por estas correcoes.
