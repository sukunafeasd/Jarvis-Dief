# Noticias Fundidas No Nucleo

## Composicao

- [x] Preservar a apresentacao editorial frontal existente.
- [x] Integrar a narracao ao WebGL do nucleo principal, sem outro holograma.
- [x] Usar ate tres faixas curvas: imagem a esquerda, manchete a direita.
- [x] Recortar as faixas na esfera e preservar o centro energetico.
- [x] Posicionar fios frontais sobre as imagens, ocultando os fios de tras.
- [x] Usar bordas emissivas, conexoes luminosas e revelacao progressiva.
- [x] Manter as cores das fotografias, sem recolorir as noticias com o nucleo.
- [x] Manter manchetes completas disponiveis para acessibilidade.

`core/spatial/news-core.mjs` cria as faixas dentro do grupo do nucleo e usa a
camera e o ciclo de renderizacao existentes. As fotografias chegam como imagens
locais normalizadas pelo provedor de noticias; nao ha buscas de imagens no
renderizador nem execucao de codigo enviado pelo modelo. Fotografias ausentes
recebem um estado explicito, nunca uma imagem falsa de uma noticia.

As faixas escrevem profundidade e sao desenhadas antes dos fios. Os fios da
frente continuam visiveis, enquanto os de tras recuam. A base tecnica segue as
[propriedades de materiais do Three.js](https://threejs.org/docs/pages/Material.html)
e a [documentacao de transparencia](https://threejs.org/manual/pages/transparency.html).

## Fala E Continuidade

- [x] Usar o foco semantico da mesma apresentacao editorial.
- [x] Nao alternar noticias por cronometro independente.
- [x] Revelar as faixas conforme suas noticias forem apresentadas.
- [x] Pausar a revelacao ao interromper, sem projetar um falso encerramento.
- [x] Ignorar sinais de foco de uma apresentacao antiga.
- [x] Manter identidade entre capitulos consecutivos de noticias no resumo.
- [x] Esperar o ultimo capitulo antes de projetar as noticias para a frente.
- [x] Preservar o painel frontal, suas imagens, textos e comportamento posterior.

`ui.py` coordena `fused`, `paused` e `front`. O foco do painel editorial chega
pelo canal existente e e aplicado ao nucleo. A transicao frontal acompanha o
encerramento do audio, nao a chegada do texto. No resumo com varios capitulos,
`newsSequenceId` preserva a composicao e `newsLast` impede uma saida prematura.

`SpatialCoreView.sync_news` envia dados somente quando mudam e tenta novamente
se a API visual ainda nao terminou de carregar. Mudancas de energia da voz nao
reenviam as fotografias a cada atualizacao do nucleo.

## Recursos E Fallback

- [x] Limitar a tres texturas de faixas por pagina de noticias.
- [x] Descartar geometrias, materiais, texturas e carregamentos pendentes.
- [x] Impedir que uma imagem atrasada reabra uma composicao descartada.
- [x] Suspender o ciclo pesado quando o nucleo estiver oculto.
- [x] Preservar informacoes no modo de movimento reduzido.
- [x] Manter a apresentacao frontal se o WebGL do nucleo falhar.
- [x] Remover a composicao antiga ao trocar de assunto ou limpar a tela.

O modo rosto conserva o renderer editorial atual; esta fusao volumetrica e
especifica do modo nucleo. Nenhuma conta, permissao, credencial ou plugin foi
alterado nesta rodada.

## Validacao

`tests/test_news_core.py` cobre a ponte Qt, o ultimo capitulo, interrupcao,
retomada, foco atrasado, troca de assunto, WebGL indisponivel, faixa pequena,
imagens locais em textura, ausencia de carrossel automatico e descarte repetido.
Os dados e imagens dos cenarios sao de demonstracao, nao noticias consultadas
em uma conta do usuario.

`tools/record_news_core.py` registra o nucleo principal junto ao painel editorial,
incluindo interrupcao e saida frontal. Saidas:

- `validation/news-core-fusion.webm`
- `validation/news-core/news-fused-demo.png`
- `validation/news-core/news-front-demo.png`

Os testes visuais usam Edge headless com WebGL por software, e a ponte Qt usa
widgets isolados. O video nao contem voz real. Isso nao equivale a validar
sincronizacao perceptual com o dispositivo de audio do usuario nem a testar um
EXE empacotado. Nenhum novo EXE foi gerado nesta rodada.

Resultado desta rodada: 383 testes aprovados na bateria completa; os seis
testes especificos passaram novamente depois do ajuste final da curvatura.
A verificacao de sintaxe dos quatro modulos JavaScript alterados e a compilacao
dos arquivos Python passaram. `pip check` nao encontrou dependencias quebradas.
