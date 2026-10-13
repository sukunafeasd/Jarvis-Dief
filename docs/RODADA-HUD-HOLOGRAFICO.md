# Rodada HUD holografico

Escopo: acabamento visual das manifestacoes e configuracoes. Nucleo principal,
posicoes globais, fala, dados, integracoes e permissoes ficam preservados.

## Fases

- [x] Consultar referencias enviadas e pesquisar HUD / Holographic UI.
- [x] Criar placa de vidro com chanfros, espessura, reflexo e condutores luminosos.
- [x] Colocar a placa atras dos simbolos WebGL, sem encobrir geometria ou texto.
- [x] Adicionar malha blueprint e marcas tecnicas, sem inventar dados.
- [x] Reforcar materiais dos simbolos e brilho dos hologramas de atividade.
- [x] Aplicar textura e acabamento chanfrado nas configuracoes nativas.
- [x] Validar capturas grandes, pequenas e previas fixadas.
- [x] Verificar movimento, acessibilidade, transparencia e cache.
- [x] Executar regressao automatizada e verificacoes de sintaxe.

## Implementacao

`HudSurface` mantem uma textura decorativa, regenerada ao mudar tamanho, tipo
ou ancoras. Nos fatos compactos, as linhas acompanham as posicoes dos rotulos,
com projecao limitada a uma consulta a cada 120 ms e sem escrita a cada frame.
Nao cria contexto WebGL, luzes adicionais, temporizador ou ciclo de animacao.
Compartilha a orquestracao existente e ignora paginas ocultas. Noticias e estado
continuam transparentes dentro do nucleo. O texto continua no DOM, frontal.
O acabamento dos campos e botoes Qt usa gradientes e bordas de relevo, mantendo
as funcoes e paginas existentes. Movimento reduzido desliga reflexos animados.

## Referencias consultadas

- https://uiforge.vikings.studio/create-sci-fi-ui
- https://threejs.org/docs/pages/MeshPhysicalMaterial.html

O vidro e o brilho sao procedurais e locais. Nenhum pacote comercial foi copiado
ou baixado. Nao foi adicionado raymarching, transmission pesado ou luz por card.

## Validacao desta rodada

- Suite completa: 372 testes aprovados em 447,744 segundos.
- 7 testes focados de referencia: geometria do conteudo, movimento real dos
  simbolos, pixels nao vazios, paginas transparentes, cache e controles nativos.
- Capturas em `validation/reference-visual`: clima, previa do clima, agenda,
  sistema, tarefas, Gmail, WhatsApp largo/estreito, atividade, configuracoes,
  material das previas e terminal. Dados sinteticos, sem contas pessoais.
- Sintaxe Python e modulos JavaScript verificada; `pip check` sem problemas.
- Nucleo principal preservado; sem mudancas nos arquivos do seu renderer.
- Gravacao visual local: `validation/presentation-motion.webm`.

## Limites

Os componentes WebGL foram exercitados em navegador real automatizado; as
telas Qt nativas foram exercitadas em modo offscreen. Nao se trata de validacao
integrada do EXE com microfone, fala audivel e GPU nativa. A captura integrada
Qt/WebGL falhou na rodada anterior e nao foi usada como evidencia nesta rodada.
Nenhum EXE foi gerado, nenhuma conta foi reconectada e nenhum push foi feito.
Nao ha configuracao dedicada de lint/typecheck ou empacotamento neste checkout.
