# Fluidez das cameras e espera antes da fala

Rodada local de 15/10/2026. Sem publicacao, mudanca de credenciais ou troca
do modelo/voz selecionados pela pessoa.

## Cenario

- Pensar nao ativa mais analise automaticamente. A analise explicita continua
  disponivel; os fios da rede foram desativados em todos os modos.
- Analise e execucao preservam o sistema solar ambiente. Foco continua
  reservando espaco para leitura, como antes.
- Nucleo e fundo usam requestAnimationFrame; a viagem de camera nao fica
  presa ao limite de 20 FPS do nucleo em repouso.
- Durante viagens, nucleo, fundo e ULTRON acompanham cada quadro disponivel.
  Isso evita cair para 37,5 FPS em monitores de 75 Hz por arredondamento.
- Os contextos usam preferencia de GPU consistente. Removido o buffer de
  desenho persistente desnecessario do nucleo e fundo.
- Evitados redimensionamentos repetidos do canvas sem mudanca de dimensoes;
  o nucleo redesenha imediatamente quando precisa redimensionar de verdade.

## Voz e comandos

- A primeira frase completa do fluxo Fish pode iniciar sem esperar 80
  caracteres. Abreviacoes, numeros e palavras incompletas continuam protegidos;
  os trechos seguintes mantem o agrupamento para nao fragmentar toda a fala.
- Uma consulta comum para mostrar algo na tela nao inicializa Codex nem espera
  a fila de operacoes da Forja. Artefatos salvos sao resolvidos pelo indice
  local de nomes; cache curto permite encontrar registros recem-concluidos.
- A confirmacao de saida do repouso pelo Qt nao bloqueia o loop de audio.

## Medicoes e limites

O probe tools/validate_scene_pacing.py usa Edge headless com WebGL por software,
nao a GPU real. Em duas execucoes locais antes/depois:

| Superficie | Antes: mediana / p95 | Depois: mediana / p95 |
| --- | --- | --- |
| Nucleo em aproximacao | 55,5 / 79,4 ms | 16,7 / 16,8 ms |
| Fundo com planetas | 600,7 / 927,7 ms | 111,1 / 190,4 ms |

Esses numeros mostram melhora neste ensaio, nao garantem desempenho em todo
computador. O fundo ainda sofre custo elevado em renderizacao por software.
O teste de abertura na janela Qt real confirmou cena completa, mesmo nucleo,
viagem concluida e ULTRON fixo. O teste nativo da Forja confirmou entrada,
saida, retorno dos fixados, cancelamento e repeticao com movimento reduzido.

As regressoes cobrem palavras/decimais, primeira frase sem esperar continuacao,
loop responsivo no repouso, consultas comuns sem Codex, indice de biblioteca,
planetas sem fios em analise/execucao, continuidade das cameras e movimento
reduzido. A qualidade percebida da fala e a latencia dos provedores externos
nao foram medidas em uma nova conversa real de microfone nesta rodada.

Resultados: bateria de 127 testes aprovada; bateria de 16 testes de movimento,
abertura e observatorio aprovada; apos os ajustes finais, sete testes focados
de cache e WebGL aprovados. Ensaios nativos de abertura, Forja e ULTRON
aprovados. Ha sobreposicao entre essas baterias; nao somar como testes unicos.
