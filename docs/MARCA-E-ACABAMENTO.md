# DIEF JARVIS: Marca e Acabamento

Rodada de 12/10/2026, aplicada ao projeto local.

## Identidade

- Identificador nativo do Windows: DIEF.JARVIS.Desktop, definido antes das janelas.
- Nome e icone da aplicacao Qt, com heranca nas janelas auxiliares.
- Icone e identidade do atalho DIEF JARVIS atualizados e conferidos pela API
  de propriedades do Windows.
- Nome padronizado na configuracao inicial, administrador, inicializacao,
  configuracoes, terminal e painel de execucao.
- Creditos do projeto original e identificadores de ferramentas preservados.

Uma instancia que ja estava aberta precisa ser reiniciada pelo atalho para
receber a nova identidade. O arquivo Python compartilhado nao foi renomeado
nem substituido por um EXE independente.

## Acabamento

- Nucleo: reflexos direcionais, microtextura, gravacao superficial discreta e
  resposta breve de material aos sinais semanticos de atencao.
- Rosto: luz de preenchimento lateral, contraste de volume e menor variacao
  entre facetas, sem alterar geometria, boca ou comportamento de escuta.
- Objetos espaciais: materiais mais definidos, mantendo cores por dominio.
- Gmail/WhatsApp: orientacao 3D suave e mais estavel; texto continua frontal.
- Informacoes: bordas, contraste, espaco do cabecalho e foco por teclado.
- Terminal/execucao: superficies grafite-violeta, acentos distintos, botoes
  com foco e hover sem deslocamento e marca propria nos cabecalhos.

## Verificacao

Testes nativos de marca, icones e elevacao; renderizacao real do nucleo em
WebGL com verificacao de pixels, movimento e limites de recursos; comunicacoes
em 900x600 e 390x650; enquadramento do nucleo em desktop e janela pequena.
Modo de movimento reduzido, suspensao quando oculto e interacoes preservados.

Suite completa: 247 testes aprovados em 261,451 segundos. Compilacao de sintaxe
aprovada. Identidade do atalho lida e confirmada na propriedade nativa do
Windows. O nucleo observado manteve 37 draw calls, 35 geometrias e uma textura,
sem crescimento de recursos nos cenarios testados.

Foi corrigida uma regressao descoberta na revisao: color-scheme dark causava
fundo opaco em uma projeccao embutida. A superficie voltou a preservar a
transparencia. Capturas e metricas ficam em validation e nao sao dados de
contas reais. Esta rodada nao testa novas autorizacoes ou envios de mensagens.
