# Rodada local: fixados vivos, buscas e coerencia de fala

Data: 14/10/2026. Nenhuma publicacao no GitHub.

## Fixados com fonte real

O temporizador verifica os fixados a cada segundo, fora da thread da interface.
Consultas locais de sistema e tarefas/agenda podem atualizar a cada segundo.
Clima consulta a cada 120 segundos; noticias e buscas a cada 300 segundos;
Gmail e Google Agenda a cada 60 segundos; previas nao lidas do WhatsApp a cada
30 segundos. O intervalo nao promete que a propria fonte publique novos dados
nessa frequencia. Valores so mudam quando uma consulta real retorna.

Filtros, cidade, periodo e pagina consultada ficam ligados ao fixado. Uma nova
pergunta sobre outra cidade nao substitui o card existente. Atualizacoes de fundo
nao abrem apresentacoes, nao falam, nao reconstroem o holograma do medidor e nao
gravam o cache em disco a cada segundo. A escolha/posicao continua persistente.

Consultas lentas recebem aviso de desatualizacao. A ultima leitura e preservada;
nao e substituida por zero, caixa vazia ou sucesso inventado. Resultados atrasados
de fixados removidos/substituidos sao descartados. Ha limite de trabalhadores,
reserva para telemetria e recuo apos falhas, evitando tempestade de requisicoes.

Operacoes de fundo sao restritas a consultas. Nao ha envio, exclusao ou abertura
automatica de conversa WhatsApp para atualizar um card. Fotos, textos criativos
e artefatos salvos sao conteudo estatico. Leituras de mensagens completas nao
sao reabertas automaticamente. Fixados antigos sem metadados da consulta original
podem precisar ser consultados e fixados novamente; o sistema nao inventa filtros.
Clima antigo com cidade e sistema possuem identificacao suficiente para consulta.

## Idioma e pesquisas

Buscas priorizam portugues e contexto brasileiro, preservando pais explicitamente
solicitado. Titulos/resumos estrangeiros passam por traducao com cache; URL, fonte
e imagem nao sao substituidas pela traducao. Falha na traducao e indisponibilidade,
nao permissao para apresentar silenciosamente outro idioma. A validacao considera
o contexto das manchetes curtas traduzidas, sem tratar frases inglesas em maiusculas
como portugues.

A deteccao usa langdetect com semente fixa e cache. Documentacao consultada:
https://pypi.org/project/langdetect/
Deteccao de textos curtos continua sendo probabilistica; nao e garantia linguistica.

Consultas e miniaturas possuem esperas limitadas que nao aguardam o encerramento
de um executor bloqueado. Falhas e comparacoes sem dados nao abrem paineis como
se fossem resultados. A traducao utiliza a conexao de IA existente e pode consumir
a quota dela no uso real; testes desta rodada usam respostas simuladas.

## Fala e interface

- Terminar uma ferramenta nao encerra uma fala ainda em reproducao.
- O estado e reconciliado depois do decremento das ferramentas em andamento.
- Salvar memoria segue o mesmo contrato de estado.
- Avisos internos nao sao perdidos por uma entrada local ja consumida, nem
  atravessam novo pedido/sessao enquanto aguardam.
- Um cue ancorado ao PCM nao fica atras de estimativas antigas.
- Alterar um simbolo preserva os eventos agendados dos outros elementos.
- Janela minimizada nao e declarada como conteudo visivel ao usuario.

## Validacao e limites

Regressoes: `test_live_pins.py`, `test_search_locale.py`,
`test_current_bug_round.py` e `test_live_pin_visual.py`.

Executadas suites de consultas, integracoes, comandos, voz, apresentacao e estado.
O ensaio visual usa navegador real, verifica pixels nao vazios, movimento e
preservacao do elemento do medidor durante atualizacoes. A suite abrangente
final passou em 273 testes, sem chamadas pagas a provedores. A verificacao
das dependencias tambem terminou sem incompatibilidades declaradas.

Nao houve limpeza/reparo real do computador, redefinicao de contas, migracao
de credenciais ou nova medicao acustica. Testes de voz usam PCM sintetico e saida
simulada. A rodada nao certifica ausencia de todos os bugs do projeto.
