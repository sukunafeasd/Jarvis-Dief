# Auditoria local: fala, tela, ULTRON e atualizacao diaria

Data: 14/10/2026. Alteracoes locais, sem publicacao ou nova versao.

## Checklist implementado

- [x] Atualizacao automatica limitada ao primeiro contato do dia, respeitando a preferencia do perfil.
- [x] Recusa de resumo registrada: outra saudacao no mesmo dia nao reabre a rotina.
- [x] Pedidos explicitos continuam disponiveis, inclusive "briefing do dia".
- [x] Pedidos negativos nao iniciam atualizacao.
- [x] Atualizacao pendente nao atravessa troca de pedido ou de sessao.
- [x] Pequeno indicador nativo, sem botoes, com progresso de fontes realmente consultadas.
- [x] Fontes indisponiveis nao aparecem como consultas bem-sucedidas.
- [x] Inicio da atualizacao recolhe o assunto transitorio anterior, preservando fixados.
- [x] Clima falado continua como projecao sem card; enquadramento corrigido em areas baixas.
- [x] Fim/interrupcao da fala encerra as revelacoes pendentes e a digitacao associada.
- [x] Troca de assunto recolhe apresentacoes transitorias concluidas, sem remover fixados.
- [x] Estado consultavel inclui conteudo dos fixados, carregamento diario e protocolo ULTRON.
- [x] Estado informado vem da aplicacao; nao e apresentado como captura visual do computador.
- [x] ULTRON rejeita snapshots atrasados e retornos de outra geracao da Forja.
- [x] Atualizar diagnostico executa nova consulta, em vez de reapresentar o resultado antigo.
- [x] Cancelamento impede anuncios atrasados; operacoes ja aceitas pelo Windows nao sao falsamente declaradas canceladas.
- [x] Voz Fish selecionada nao alterna silenciosamente para voz nativa em caso de falha.
- [x] PCM preservado entre pacotes, escritas curtas e reinicio do dispositivo antes da nova resposta.
- [x] Segmentacao de voz preserva numeros decimais.

## Validacao

Suites direcionadas executadas nesta rodada: 168 testes de comandos, estado,
ULTRON e audio; 59 testes de atualizacao e apresentacao; seis testes do contrato
nativo da Forja. Todos passaram nas respectivas execucoes finais. A verificacao
adicional da integracao do indicador e do primeiro contato passou por 21 testes.
Os grupos se sobrepoem; estes numeros nao devem ser somados como testes unicos.
Depois da revisao independente do buffer, uma nova execucao de 98 testes de voz
e comandos passou, incluindo a regressao de troca de resposta durante a espera
interna por PCM. O pacote da resposta nova e preservado ao descartar a anterior.

O contrato nativo iniciou uma janela Qt isolada, conferiu a sequencia de entrada,
preview animado, isolamento, F11 e restauracao de fixados. O ensaio agora espera
a primeira animacao real da fixture antes de medir seus quadros; continua
falhando se o preview nao animar dentro do prazo.

Captura do indicador: `validation/daily-refresh-compact.png`.
Regressoes especificas: `tests/test_daily_refresh_contract.py`,
`tests/test_presentation_sync_contract.py`, `tests/test_ultron_state_regressions.py`
e `tests/test_voice_stream_boundaries.py`.

## Limites

Audio foi exercitado com PCM sintetico e saida simulada nesta rodada. Nao houve
nova chamada paga ao provedor nem avaliacao acustica da voz real; latencia da rede,
do provedor e do dispositivo ainda podem afetar a experiencia. Nao foi executada
limpeza, reparo ou outra operacao destrutiva do ULTRON. Contas pessoais e fixados
nao foram redefinidos. Isto e uma rodada direcionada, nao prova de ausencia de
todos os bugs do projeto.
