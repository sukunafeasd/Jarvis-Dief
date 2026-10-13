# Observatorio DIEF JARVIS

## Checklist de entrega
- [x] Entrada de 4,3 segundos com viagem em profundidade pelo campo de estrelas.
- [x] Despertar do nucleo existente, com distancia de camera coordenada com o fundo.
- [x] Fala, analise ou execucao interrompem a entrada e acomodam a camera em 320 ms.
- [x] Sol, oito planetas, Lua, aneis de Saturno e trajetorias orbitais lentas.
- [x] Terra e Lua com mapas NASA locais, limitados a 1024x512 na GPU.
- [x] Assistente, analise, execucao, foco e exploracao, sem novos botoes ou abas.
- [x] Selecao por voz via interface_control environment e nomes em portugues.
- [x] Exploracao com nucleo deslocado para a direita; relogio independente.
- [x] Informacoes abertas tem prioridade sobre planetas; contexto solicitado se conserva.
- [x] Noticias fundidas ao nucleo e apresentacao frontal posterior preservadas.
- [x] Pinos, cards, configuracoes, permissoes e contas existentes preservados.
- [x] Reacoes de atencao ligadas ao relogio existente de apresentacao.
- [x] Fluxo visual entre nucleo e painel real somente durante operacao em andamento.
- [x] Advertencia e conclusao derivadas de estados reais, sem sucesso antecipado.
- [x] Spotify atualiza progresso ambiental a partir de current ou play verificado.
- [x] Pausa/troca invalida a previa antiga; dados expiram em 30 segundos.
- [x] Movimento reduzido, janela oculta/minimizada e fallback sem WebGL.
- [x] DPR limitado, qualidade adaptativa com histerese, duas luzes e descarte de recursos.
- [x] Orcamento verificado de ate 32 chamadas de desenho no ambiente.

## Arquitetura
EnvironmentDirector e a fonte de estado semantico, independente da IA.
O HUD envia o mesmo pacote ao espaco e ao nucleo. environment-rig.mjs resolve
a distancia da entrada e o cancelamento pelos mesmos timestamps.
As duas superficies WebEngine continuam separadas, com campos de visao adequados
a suas funcoes. Nao se afirma que viraram uma unica cena/renderizador.
Textos e controles nativos nao viajam com a camera nem perdem resolucao.

O estado nao cria consultas, nao muda provedores e nao fala automaticamente.
Efeitos de atencao usam os eventos do playback existente; nao ha outro
temporizador de artigos nem uma nova linha de fala. Cancelamento remove sinais
transitorios sem apagar o contexto selecionado.

## Comandos
Usar interface_control com action=environment e value:
- normal/auto: devolver a direcao ao assistente;
- foco: ambiente discreto para leitura;
- analise/execucao/exploracao: escolher composicao;
- sol, mercurio, venus, terra, marte, jupiter, saturno, urano, netuno, lua:
  destacar corpo existente, mantendo identidade e voltando a orbita depois.

Inspecionar environment no snapshot antes de alterar. Informacoes abertas
continuam prioritarias; se o pedido e trocar a apresentacao atual por exploracao,
recolher a apresentacao com o comando semantico existente, preservando pinos.
Modo de execucao nao executa ferramentas por si e nao comprova resultado.

## Limites deliberados
- Distancias, tamanhos, direcoes iniciais e velocidades orbitais sao artisticos,
  nao efemerides. Superficies procedurais dos outros planetas sao ilustrativas.
- O fundo distante continua sendo o asset aprovado; estrelas e planetas tem
  profundidade real. Nao foi acrescentado raymarching de nebulosas.
- Musica mostra progresso confirmado, sem inventar equalizador/batidas: o
  conector Spotify nao entrega amostras do audio. A voz existente continua primaria.
- Grades e constelacoes tecnicas sao ambiente, nao um grafo falso de arquivos.
  Diagramas de dados continuam passando pela biblioteca visual existente.
- Sem drones, portais ou minimapas permanentes, evitando competir com informacao.
- Sem sons adicionais nem alteracao da configuracao pessoal nesta rodada.

## Validacao
tools/validate_observatory.py usa apenas arquivos locais e dados sinteticos.
Verifica movimento por diferenca de pixels, canvas nao vazio, 800/390/1920/3840
pixels de largura, selecao de planetas, cancelamento da entrada, ausencia de
loops em movimento reduzido/oculto e estabilidade de geometria/texturas.
Testes nativos verificam comandos, prioridades, relogio e preservacao dos cards.
Testes de midia verificam que somente estado confirmado chega ao ambiente.

Gravacao: validation/observatory-demo.webm. Relatorio:
validation/observatory/report.json. Execucao visual usa Edge headless com
renderizacao de software; seus FPS nao certificam a GPU real nem 60 FPS no EXE.
Nao foi realizada conversa real com microfone/API nem gerado novo executavel.
Sem WebGL, o wallpaper e as manifestacoes nativas continuam disponiveis;
o snapshot informa renderer=fallback para a IA nao afirmar que exibiu um planeta.

Creditos e diretrizes das superficies NASA: core/spatial/assets/SPACE-CREDITS.md.

## Resultado desta rodada
- Suite geral: 414 testes executados, com uma unica falha no limite antigo de
  duas chamadas de desenho do wallpaper. Novo limite do observatorio: 32.
- Criterio atualizado e teste reexecutado: passou. Reexecucoes dedicadas de
  ambiente, interface, espaco, Spotify, pinos e memoria: 51 testes passaram.
- Compilacao dos arquivos Python alterados passou.
- Captura completa confirmou pixels em movimento e enquadramento de 390 a 3840.
- Captura adicional em navegador com WebGL acelerado identificado passou;
  relatorio separado em validation/observatory/report-hardware.json. Nao e uma
  certificacao de FPS do aplicativo Qt ou do EXE.
