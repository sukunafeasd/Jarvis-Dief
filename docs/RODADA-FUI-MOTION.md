# Rodada Cinematic Holographic FUI

## Checklist

- [x] Pesquisar Cinematic Sci-Fi HUD, hologramas 3D e FUI motion.
- [x] Construir luz dinamica nas molduras com shader WebGL local e confiavel.
- [x] Montar simbolos sobre bases de projecao, orbitas tridimensionais e particulas.
- [x] Diferenciar chuva, passos, chama, energia, mensagens e dados.
- [x] Animar foco dos registros e resolucao das imagens das noticias.
- [x] Recolher simbolos e superficie ao encerrar, sem controles extras.
- [x] Animar acabamento Qt das configuracoes, terminais e previas.
- [x] Corrigir presets da biblioteca que paravam logo apos a montagem.
- [x] Validar movimento real, pausa, modo reduzido, limites e capturas.
- [x] Executar regressao completa e registrar video atualizado.

## Arquitetura

`HolographicPanelMotion` desenha condutores luminosos e o scan de montagem em
um unico passe. `HolographicSymbolRig` fornece aneis inclinados, pontos em orbita
calculados na GPU e base emissiva. Ambos compartilham o renderer e o ciclo de
apresentacao existentes: nenhum contexto WebGL ou RAF adicional. A estatistica
de draw calls agora soma ambos os passes, em vez de esconder o custo do segundo.

O texto continua no DOM e de frente. Noticias permanecem dentro do nucleo
original, sem rig secundario. Nenhum marcador altera foco de noticias por tempo:
o foco continua vindo dos sinais semanticos da fala reproduzida. Presets da
biblioteca como `orbitar` e `respirar` continuam ativos apos a entrada; montagem
e desenhos de entrada continuam finitos. `silencio` e movimento reduzido ficam
estaticos. A biblioteca ainda tem geometria/material compartilhados e limites.

As animacoes nativas usam QPropertyAnimation, sob o relogio de animacao do Qt,
com atualizacao limitada as bordas. Esconder, minimizar ou reduzir movimento
suspende o efeito. O background em pixmap permanece em cache; nunca e recriado
por frame. Paineis com QGraphicsProxyWidget consultam a visibilidade real da view.
O rig e seus programas sao reutilizados nas atualizacoes do mesmo dominio.
A apresentacao principal mira 60 fps durante atividade e 30 fps apos estabilizar;
previas compactas mantem atualizacao mais leve. Sao metas, nao benchmark de GPU.

O brilho e localizado em materiais/halos; nao foi adicionado bloom global caro,
desfoque de texto, aberracao cromatica, camera shake ou luzes extras. Os detalhes
sao originais e procedurais. Os modelos escolhem dados/presets, nunca GLSL cru.

## Referencias

- https://territorystudio.com/project/miles/
- https://territorystudio.com/project/ghost-in-the-shell/
- https://threejs.org/docs/pages/ShaderMaterial.html
- https://threejs.org/docs/pages/BloomPass.html

## Limites De Validacao

Validacao realizada em navegador real automatizado para WebGL e Qt offscreen
para telas nativas, com dados sinteticos e credenciais isoladas. Nao equivale a
validacao do EXE integrado com voz audivel, microfone e GPU nativa. O nucleo
principal, as permissoes e conexoes nao foram modificados nesta rodada.

## Evidencias

- Suite completa repetida: 377 testes aprovados em 494,076 segundos.
- 5 testes focados novamente aprovados apos ajustar a reabertura do mesmo contexto.
- Pixels brutos do canvas confirmam movimento na moldura, independentemente das
  animacoes CSS e do texto. Bounds dos textos permanecem iguais entre frames.
- 24 atualizacoes de clima mantem o numero de geometrias estavel; cena testada
  fica abaixo de 65 draw calls. Presets orbital/respiracao continuam apos 1,8 s.
- Modos oculto, reduzido e interrupcao suspendem o relogio dos efeitos novos.
- Qt: esconder/minimizar reduz atividade a zero; restaurar retoma; cache mantido.
- A primeira suite identificou uma regressao no estado logico de fechamento.
  Corrigido: opacity inline marca fechamento imediatamente, enquanto a animacao
  visual termina em 220 ms. A suite completa e os testes de continuidade passaram.
- Reabrir a mesma apresentacao cancela a saida antiga e restaura a superficie,
  inclusive ao receber somente `visible:true`. Coberto pelo teste focado final.
- Python compilado, JavaScript verificado e `pip check` sem requisitos quebrados.
- Video de 12 cenarios em `validation/presentation-motion.webm`, sem voz e com
  dados sinteticos. Frames revisados em `validation/holographic-motion/video-*.png`.
- Nao houve novo EXE, empacotamento, push ou alteracao de credenciais.
