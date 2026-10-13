# Conhecimento do sistema e memoria

Esta rodada foi aplicada ao projeto local; nao foi publicada automaticamente.

## Conhecimento proprio

A ferramenta `system_knowledge` consulta o catalogo do painel, as paginas de
configuracoes e as ferramentas realmente registradas na sessao. `tool` retorna
o contrato de parametros, nao uma suposicao do modelo. `component` analisa a
estrutura AST de modulos explicitamente aprovados, com linhas e paginacao;
nao executa codigo nem permite ler arquivos privados ou caminhos arbitrarios.
`runtime` usa a inspecao real da interface, sem capturar a tela inteira.

Os titulos das paginas sao compartilhados entre a UI e o catalogo. Uma
ferramenta disponivel nao implica que a conta correspondente esta conectada.
Conhecer codigo nao concede capacidade de reescrever a aplicacao sozinho.

## Continuidade

Os fatos continuam em `memory/long_term.json`, fora dos provedores da IA.
Nenhuma memoria pessoal foi copiada ou alterada por estes testes.
A busca lexical agora normaliza acentos, ignora palavras comuns da pergunta
e ordena resultados por relevancia; leitura por ID nao depende do filtro.

Gravacao de fatos, exclusao e resumos de sessao usam transacoes locais sob
o mesmo lock e escrita atomica. Ao atingir capacidade, a nova escrita falha
explicitamente sem apagar fatos antigos. Arquivos invalidos sao preservados.
Credenciais identificaveis e chaves de campos secretos sao recusadas.

Resumos recentes persistem mesmo depois de apresentados. O historico e
limitado a 12 resumos; os tres mais recentes entram como contexto, nao como
instrucoes. Resumos podem estar desatualizados. Falha na geracao de resumo
restaura o log em vez de descarta-lo. Fatos pessoais permanecem separados.

## Execucao e limites

O contexto distingue app, lista e selecao. O despacho registra falhas de
chamadas identicas: depois de duas falhas bloqueia repeticao no mesmo pedido
e solicita reinspecao/correcao. Resultado incerto bloqueia repeticao imediata.
O cache e limitado e reinicia com uma nova entrada humana. Parametros de
ferramentas nao sao mais impressos integralmente no log de despacho.

Isso melhora contexto e confiabilidade; nao muda a inteligencia intrinseca do
modelo nem garante operacoes universais em aplicativos. A captura automatica
de fatos ainda depende de save_memory usado pela IA; emails e documentos nao
sao autorizacao para criar memorias. A protecao de credenciais nao identifica
todo tipo possivel de segredo. Nao foram feitas chamadas pagas ou envios reais.

## Verificacao

Bateria completa: 262 testes aprovados em 298,977 segundos. Depois dos ultimos
ajustes, a rodada especifica atualizada de 17 testes tambem passou, incluindo
o despacho real de ferramentas e restauracao do log quando o resumo falha.
Os testes de memoria usam arquivos temporarios e processos novos, sem conta
conectada. Sintaxe Python verificada. A qualidade da conversa com uma API real
nao foi medida nesta rodada.
