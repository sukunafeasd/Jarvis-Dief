# Repouso e primeiro contato diario

- [x] Fundo do canvas nao ativa repouso: alvo projetado do nucleo no WebGL.
- [x] Rosto usa os triangulos projetados para distinguir rosto e fundo.
- [x] Toque para despertar continua funcionando em repouso.
- [x] F4 permanece separado do repouso manual.
- [x] Nucleo recua 1.15 unidades e conserva 82% da escala; nao vira um ponto distante.
- [x] Materiais e shader ficam fracos; orbitas e cinco orbes originais continuam girando.
- [x] Rosto tambem apaga e recua visualmente, preservando o alvo de toque.
- [x] Resumo nao e enviado ao conectar/abrir o aplicativo.
- [x] Primeiro contato por voz transcrita ou texto agenda o resumo depois da resposta/audio.
- [x] Data local persistida separadamente das chaves; reabertura no mesmo dia nao repete.
- [x] Resumo desativado e repouso sao respeitados; tarefa cancelada na desconexao.
- [x] 31 testes automatizados aprovados.
- [x] WebGL validado com pixels, cliques no fundo/nucleo, movimento das orbitas e capturas.
- [x] Renderizador nativo abriu com shader pronto, sem falha.

Evidencias: validation/core-results.json, validation/core-resting.png,
validation/core-native.png. O teste diario usa estado temporario e simulacao de
conversa para nao consumir o resumo real do usuario.
