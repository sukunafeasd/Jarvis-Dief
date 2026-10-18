# Tema observatorio: cards e configuracoes

Alteracoes locais, sem publicacao ou novo executavel.

## Visual

- Superficies azul-escuras com textura espacial existente, bordas luminosas,
  acabamento arredondado e movimento de luz controlado.
- Perfil organizado em identidade/localizacao e noticias/rotina, com previa
  animada do nucleo real. Apenas uma instancia da previa e criada.
- Conexoes em duas colunas quando ha espaco, com icones locais dos servicos,
  estado real, busca e categorias Contas, Plugins nativos e Skills.
- Cards fixados reutilizam a moldura nativa; clima inclui nuvem iluminada,
  precipitacao animada, temperatura, indicadores e previsao quando ha espaco.
- Projecoes temporarias continuam sem moldura de card.
- Icones externos acompanhados das licencas em resources/ui-icons.

## Correcoes

- Indicadores do clima nao invadem a previsao nem ficam cortados no topo.
- Switches acompanham reversoes programaticas mesmo com sinais bloqueados.
- A previa pausa suas verificacoes quando oculta/minimizada e retoma ao abrir.
- Forja restaura conta/modelo sem sobrescrever uma escolha em edicao.
- Renderizadores ignoram areas de tamanho zero. O bloom do ULTRON nao cria
  mais alvos de renderizacao vazios durante redimensionamentos.

## Validacao em 15/10/2026

40 testes passaram na ultima execucao:
test_observatory_weather, test_observatory_settings,
test_settings_connections, test_settings_hub e test_idle_work_round.

Playwright verificou limites, sobreposicoes, carregamento dos icones,
pixels do holograma, movimento e movimento reduzido em cinco tamanhos de card.
Teste de iframe confirmou recuperacao da previa apos tamanho zero.

tools/validate_observatory.py passou com Qt/WebEngine nativo, dados descartaveis
e conexoes simuladas. Confirmados: um nucleo, pixels visiveis, movimento,
pausa/retomada, tres tipos de card carregados e nenhuma excecao capturada.
A ultima execucao nao apresentou o aviso de framebuffer vazio das anteriores.
Capturas e relatorio: %USERPROFILE%/AppData/Local/Temp/dief-observatory-rufy4s5z.

Alguns testes antigos tentaram salvar capturas em pasta protegida e receberam
erro de escrita. As novas capturas foram salvas e verificadas na pasta Temp.
Logins reais, voz e todas as operacoes externas nao foram exercitados nesta rodada.
Uma revisao anterior encontrou os problemas de Forja e pausa da previa, corrigidos
com testes. A revisao adicional final ficou indisponivel por limite do revisor.
