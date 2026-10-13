# Identidade FUI Em Todas As Telas

## Checklist

- [x] Compartilhar o material dos cards com as telas nativas.
- [x] Vidro escuro, textura de grade, microgravura e reflexo discreto.
- [x] Molduras chanfradas, condutores ciano e cantos emissivos vermelhos.
- [x] Configuracoes: seis paginas, campos legiveis e navegacao lateral preservada.
- [x] Conexoes: cards com estados reais, botoes e credenciais preservados.
- [x] Administrador: atmosfera galactica, nucleo projetado com profundidade,
      filamentos, centro luminoso, orbitas e movimento contido.
- [x] Dependencias: novo HUD, nucleo animado, etapas e progresso reais.
- [x] Configuracao inicial de IA: mesmo vidro, moldura e luz em movimento.
- [x] Audio, memoria, plugins, configuracao de plugins, pareamento,
      camera e confirmacao: compartilhar o acabamento nativo.
- [x] Fallback de administrador sem Qt: mesma identidade em Tk.
- [x] Modo de movimento reduzido sem esconder informacoes.
- [x] Suspender luzes/animações em telas ocultas ou minimizadas.
- [x] Capturas grandes e pequenas; gravacao de movimento nativo.

## Implementacao

`core/fui_geometry.py` produz fios e filamentos originais projetados em perspectiva.
Nao depende de Qt, WebGL, imagens externas ou modelos baixados. Qt e Tk usam
essa mesma geometria na entrada; o nucleo principal WebGL do painel continua
inalterado. Os nucleos das entradas sao projeções vetoriais, nao novos contextos
WebGL: a verificacao de dependencias precisa funcionar antes de instalar Qt.

`core/fui_paint.py` fornece a placa de vidro e o desenho do nucleo. HudGlassFrame,
SettingsSurface e ElevationDialog reutilizam a placa por tamanho/DPR. As luzes
de moldura permanecem fora da area dos textos. A animacao nativa utiliza o
relogio de animacao Qt; a inicializacao Tk usa um unico ciclo para fila e visual.

`core/fui_bootstrap.py` usa Tk e a geometria local. Pillow acrescenta o bitmap
galactico quando estiver disponivel; sem Pillow, o HUD e o nucleo continuam
funcionando. Os estados nao fingem conexoes ou sucesso. Cor e texto apresentam
o resultado enviado pelo verificador, mantendo erros e pendencias visiveis.

Todas as telas preservam os controles e callbacks existentes. Senhas e chaves
continuam ocultas; a alteracao nao muda OAuth, permissao do Windows, instalacao
de dependencias, confirmacoes de outras ferramentas ou execucao do PowerShell.
Janelas de autorizacao do Windows e paginas de login de provedores externos
nao pertencem ao renderer do Jarvis e nao recebem este tema.

## Validacao

`tests/test_fui_screens.py` cobre as seis paginas, cache, movimento, modo reduzido,
minimizacao, controles iniciais, frames auxiliares e funcionamento sem Qt/Pillow.
Os testes de entrada, marca, idioma e recursos tambem verificam callbacks e
estados de conexao. As capturas de demonstracao usam configuracoes isoladas:
nenhuma credencial do usuario foi incluida na gravacao.

Saidas:

- `validation/all-screens/`: capturas das seis paginas em 1366 e 800 pixels,
  administrador em dois tamanhos, primeira configuracao e confirmacao.
- `validation/startup-finish.png`: verificacao de dependencias com estados simulados.
- `validation/all-screens-fui.webm`: administrador, configuracao inicial e seis
  paginas com movimento real dos widgets Qt, gravados em ambiente offscreen.

O video nao e uma gravacao de uso com voz, contas conectadas ou um EXE novo.
Nao foi gerado um novo executavel nem alterado o repositorio publicado.

Resultado: 398 testes aprovados na regressao geral; oito testes especificos das
telas e dois de entradas/configuracoes passaram novamente apos os ajustes finais.
Uma falha de importacao no desenho das orbitas foi corrigida e recebeu um teste
direto de pintura, evitando depender apenas de callbacks de eventos Qt.
Compilacao Python aprovada e `pip check` sem dependencias quebradas. Capturas
e video foram conferidos; a verificacao visual nativa usa Qt offscreen, nao
uma sessao com contas reais.
