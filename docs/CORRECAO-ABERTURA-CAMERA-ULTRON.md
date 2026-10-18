# Continuidade da abertura e camera do ULTRON

Data: 15/10/2026. Alteracoes locais, sem publicacao ou modificacao de contas.

## Correcoes

- O carregamento nao desenha mais um segundo holograma nativo. Uma preparacao
  neutra cobre o aquecimento; a primeira cena espacial usa o proprio nucleo 3D.
- O nucleo real permanece distante durante a preparacao, inclusive ao redimensionar.
  Estrelas, sistema solar e ULTRON sao renderizados antes da liberacao da cena.
- A prontidao considera fundo, mapas dos planetas e primeiro quadro do ULTRON.
  Uma falha terminal nao pode emitir sucesso, nem liberar a cobertura para mostrar
  um substituto nativo. Falhas de textura do fundo tambem encerram a espera no
  modo de movimento reduzido, usando o fundo de seguranca.
- A viagem comeca somente depois que a cobertura de preparacao termina de sair.
  O atraso fixo nao e mais usado como prova de que essa transicao terminou.
- ULTRON recebe o mesmo percurso, horario, campo de visao e direcao da camera do
  fundo. Sua posicao e escala no mundo nao sao recalculadas durante a viagem nem
  no redimensionamento. A rotacao da crosta e os efeitos continuam independentes.
- Abrir o nucleo do ULTRON nao desloca sua camera separadamente do cenario.
  A previa autonoma do planeta conserva seu enquadramento proprio.
- O movimento reduzido dispensa a viagem e preserva a prontidao sem espera circular.

## Verificacao

- 26 testes focados passaram, incluindo navegador real em desktop e retrato,
  verificacao de pixels do nucleo verdadeiro, percurso monotono, preparacao
  completa, planeta ancorado, redimensionamento, movimento reduzido e falhas.
- Uma execucao final de 50 testes de abertura, interface, estados de modo e
  ULTRON passou. Os grupos se sobrepoem e nao devem ser somados.
- Na janela Windows real, o ensaio final confirmou primeira cena completa ainda
  distante, chegada ao enquadramento final, mesmo modelo/geometrias, planeta com
  transformacao fixa, movimento de camera e ausencia de excecoes de callbacks.
- Outro ensaio nativo confirmou que a configuracao inicial da API nao inicia
  a cena nem consome a entrada antes da configuracao.
- Capturas da primeira cena e chegada foram inspecionadas visualmente. Relatorios
  e imagens ficam em pastas temporarias `dief-native-opening-*` e
  `dief-opening-continuity-*`, sem usar os dados reais do usuario.
- Sintaxe Python/JavaScript e verificacao de espacos do diff passaram.

## Limites

Ainda existe tempo de preparacao dos recursos 3D, explicitamente mostrado antes
da cena; nao e promessa de carregamento instantaneo. Os ensaios nao iniciaram a
IA nem chamadas pagas, e nao medem FPS sem a sobrecarga de capturas e diagnosticos.
Reiniciar o Jarvis pelo atalho carrega as alteracoes locais.
