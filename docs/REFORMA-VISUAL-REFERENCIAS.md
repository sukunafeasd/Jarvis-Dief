# Rodada visual: vidro espacial vermelho e ciano

## Limites

- Somente materiais, desenho, estilos e efeitos visuais.
- Preservar geometria de layout, entrada/saida, foco, fala, dados, comandos,
  integracoes, gestos e persistencia.
- Referencias: as duas imagens fornecidas pelo usuario nesta rodada.
- Nao adicionar os botoes ou dados ficticios presentes nas referencias.

## Checklist Por Fase

- [x] 1. Cards e previas: vidro escuro, microtextura, bordas luminosas,
  vermelho/ciano, contraste e registros legiveis.
- [x] 1. Capturas desktop/compacto, comparacao com referencias e geometria.
- [x] 2. Nucleo: malha viva, contorno vermelho, centro energetico e orbitas.
- [x] 2. Icones: materiais coloridos e profundidade, movimento existente.
- [x] 2. Capturas e movimento: repouso, ouvindo, falando e executando.
- [x] 3. Configuracoes e paineis auxiliares: acabamento coerente, controles
  e navegacao preservados.
- [x] 3. Capturas: perfil, conexoes e janela pequena.
- [x] 4. Testes de regressao, recursos WebGL, reduced motion e compilacao.

## Evidencias

As capturas desta rodada ficam em validation/reference-visual/.
Capturas com dados sinteticos de teste nao demonstram acesso a contas reais.

## Referencia Adicional

Os exemplos de caminhada, energia e calorias orientam simbolos luminosos
sem moldura e valores ao lado. Esse arranjo interno so se aplica a dados
curtos desses assuntos, sem alterar o posicionamento global dos outros
modulos. Nao foi criado provedor de saude, pareamento de relogio ou valores
simulados em producao.

## Validacao E Limites

- Suite geral: 370 testes aprovados. A expectativa da cor antiga do tema foi
  atualizada para a nova paleta, mantendo os testes de contraste e animacao.
- Cinco testes dedicados: geometria dos cards inalterada, projecoes
  transparentes, nucleo vermelho em cinco estados, simbolos resumidos,
  reduced motion, recursos WebGL estaveis e configuracoes nativas.
- Capturas: desktop, 800 px, 640 px, 390 px e previas compactas.
- Nucleo observado com 40 draw calls, 38 geometrias e uma textura;
  contagens estabilizadas depois do aquecimento.
- Movimento: validation/presentation-motion.webm; sequencia sintetica sem
  alterar contas, enviar mensagens ou consumir provedores de IA.
- Compilacao Python e verificacao sintatica dos modulos JavaScript.
- Qt nativo em modo offscreen executou e capturou o fallback e configuracoes.
- A captura integrada Qt/WebGL no desktop nao completou neste ambiente,
  inclusive na tentativa com renderizacao por software. Os componentes
  WebGL foram validados no navegador de teste, nao se deve confundir isso
  com uma verificacao completa do EXE ou de uma conversa real.
- Nao foram alterados voz, comandos, handlers, credenciais, fontes de dados,
  posicionamento global dos modulos ou politicas de autorizacao.
- Nao foi gerado EXE nem publicado no Git nesta rodada.
