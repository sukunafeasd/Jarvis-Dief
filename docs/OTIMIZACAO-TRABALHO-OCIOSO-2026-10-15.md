# Otimizacao de trabalho ocioso

## Escopo local

- Catalogo de plugins: uma leitura das preferencias por listagem ou conjunto
  de formularios, sem cache global que esconda mudancas externas.
- Criacao de linhas nas conexoes: um catalogo de formularios compartilhado
  pelo lote, em vez de consulta repetida para cada linha.
- Configuracoes: o temporizador atualiza apenas a aba visivel; para ao
  ocultar a janela e nao consulta plugins/historico quando minimizada.
  Abrir outra aba atualiza seu conteudo imediatamente. Atualizacoes
  explicitas continuam disponiveis para resultados de conexao.
- Icones e estados iguais nao sao reconstruidos a cada segundo. A consulta
  redundante de disponibilidade de extensoes reutiliza o resultado local
  existente, com a invalidacao ja usada apos testes/instalacoes.
- Projecoes WebGL em movimento reduzido e ja estabilizadas reaproveitam
  o ultimo desenho. Dados, redimensionamento, visibilidade, preferencia de
  movimento e narracao invalidam o desenho. Relogios de texto e audio
  continuam funcionando; animacoes normais nao foram desativadas.
- Uma reconexao da IA concluida enquanto as configuracoes estao ocultas
  e conferida antes de anunciar tempo esgotado.

## Medicoes reproduzidas

Com 40 plugins sinteticos, listagem: 40 leituras -> 1; formularios com um
plugin desativado: 79 leituras -> 1. Criacao de quatro linhas: quatro
consultas ao catalogo -> uma; repeticao sem novas linhas -> nenhuma.
Dez atualizacoes do perfil nao consultam inventario, conexoes nem historico.
Dez estados iguais de uma linha nao recriam o icone. Consulta local de uma
extensao permanece em uma chamada durante dez atualizacoes no intervalo.

No teste isolado de uma projecao reduzida estabilizada, o teste WebGL
reproduziu 186 chamadas adicionais de desenho em 500 ms antes da correcao,
e zero depois. Novos dados, resize e retorno ao movimento normal voltam
a desenhar. Isso nao e medicao de FPS do computador do usuario nem
garantia de eliminar toda lentidao de rede, voz ou renderizacao.

## Limpeza

Removidos somente um import sem uso, o campo sem uso `_probed`, o helper
`has_settings` substituido pela consulta em lote e cache de linhas removidas.
As linhas nativas sao retiradas do layout correto. Nao houve exclusao em
massa de arquivos/dependencias: ha carregamento dinamico de plugins,
fallbacks visuais e ferramentas de validacao ainda utilizados.

## Verificacao

Testes novos: `test_idle_work_round` e `test_reduced_presentation_budget`.
Sintaxe dos seis arquivos Python e do modulo JavaScript validada.
Revisao adicional dos ajustes de configuracoes sem pendencias apos corrigir
o caso de reconexao oculta.

Bateria final: 289 testes passaram em 151 segundos. Inclui voz sintetica,
Forja, ULTRON, atualizacao diaria, agenda, configuracoes, pins vivos e
movimento WebGL. Capturas atuais em
`%USERPROFILE%/AppData/Local/Temp/dief-idle-work-final-pvdshai4`.
Capturas de testes legados em Documentos emitiram avisos de escrita e nao
foram contadas como evidencias salvas. Os testes visuais atuais usaram Temp.

O teste antigo de borda foi separado em projecao sem card e card compacto:
ambos verificam pixels em movimento, e o primeiro verifica estabilidade do
texto e geometria. A espera da animacao nativa agora aguarda a condicao real
por ate dois segundos, sem depender de uma pausa fixa de 100 ms.

Sem chamadas pagas, conversa pelo microfone, varredura real do Windows,
alteracao de contas, novo EXE ou publicacao. A tarefa de inicio elevado
do Windows permaneceu habilitada e foi consultada novamente.
