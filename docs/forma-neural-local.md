# Forma Neural integrada localmente

## Uso

Reabra o aplicativo pelo atalho local. Exemplos de pedidos:

- "Jarvis, lembra do que planejamos para a Forja?"
- "Procure nas nossas conversas o que combinamos sobre o projeto."
- "O que voce lembra das minhas preferencias?"
- "Entra no modo lembranca, Jarvis."
- "Meu querido, procura na lembranca uma coisa para mim."
- "Entra no modo lembranca e busca o que falei sobre musica."

A forma acompanha chamadas reais de memory_control, recall_memory e qdrant_memory.
Respostas sem consulta de memoria nao acionam uma animacao ficticia. O modelo pode
solicitar mais contexto quando a pergunta nao identificar uma lembranca.

## Comportamento

O mesmo nucleo original se desmaterializa antes da formacao cortical. As
particulas, sinapses e dendritos derivam da previa visual aprovada. Ate tres
fragmentos recuperados aparecem distribuidos ao redor do cerebro, com fonte e
data quando disponiveis. Conteudo adicional continua acessivel pela ferramenta;
o limite visual nao limita a consulta nem altera seu resultado.

Uma lembranca usa percurso de 2,4 segundos; duas, 3,6; tres, 4,8. A fala
nao espera a animacao. A forma permanece durante a fala e por quatro segundos apos
a formacao sem fala, depois reconstitui o nucleo em 1,4 segundos. Movimento
reduzido e respeitado. O relogio da transformacao utiliza o tempo transcorrido,
mesmo com queda de quadros; o brilho e limitado a 1200 x 900 pixels internos.

Pedidos explicitos de lembranca fora da Forja possuem roteamento local:
anunciam a consulta e leem evidencia realmente recuperada, sem depender de o
modelo escolher chamar uma ferramenta. Mencionar um plano da Forja nao e uma
ativacao ou criacao. A leitura de voz nativa agrupa introducao e resultados em
uma requisicao para nao interromper a propria introducao.

O visual nao usa perguntas e respostas casuais recentes. Trechos de historico
precisam ter mais de cinco minutos e conter uma decisao, preferencia, requisito
ou plano; perguntas, cumprimentos e confirmacoes triviais ficam fora. Fatos
persistidos continuam disponiveis sem essa idade minima. O historico bruto nao
foi apagado: sua leitura continua disponivel pela ferramenta de conversa.

Particulas, membrana, sinapses, conexoes e rotulos utilizam a cor efetiva do
nucleo, inclusive mudancas de tema e cores de estado. Nao ha vermelho fixo.

O brilho recebe o nivel do audio do aplicativo somente na fase speaking. O foco
semantico recebe trechos no relogio de PCM reproduzido, usando a infraestrutura
de narracao existente. Nenhuma amostra de voz ou memoria demonstrativa foi
instalada no produto. O historico de respostas anteriores conserva a indicacao
de que nao comprova execucao.

Interrupcao, limpeza de tela, noticias, outra manifestacao, configuracoes, repouso,
ULTRON e Forja encerram ou suspendem a visualizacao conforme o contexto. Fixados
nao sao apagados. IDs de consulta impedem resultados atrasados de reabrirem
memorias canceladas. Falhas visuais nao interrompem a ferramenta de memoria.

## Validacao de 16/10/2026

### Refinamento de evidencia e acabamento visual

- Selecao ordena candidatos elegiveis antes do limite visual, considerando
  origem, decisao/preferencia, relevancia e data. Repeticoes do mesmo fato nao
  ocupam varios fragmentos; negacoes e numeros permanecem distintos.
- Inventario solicitado nao pesquisa literalmente por "tudo/todas". Consulta
  a preferencias aceita declaracoes pessoais, nao estado passageiro de apps.
  Historico tambem admite a forma singular de um assunto pedido no plural.
- Em pedidos de lembranca, a resposta da ferramenta ao modelo usa a mesma
  evidencia filtrada da projecao. Consulta atrasada e descartada se a sessao,
  turno ou contexto mudar. Registros aninhados agora tambem sao narrados.
- Fala local menos repetitiva, sem apresentar registros vazios como citacoes.
  Nenhuma memoria original foi apagada ou migrada nesta rodada.
- Luz da forma neural tem ataque e decaimento suaves. O destaque deixa de
  circular entre lembrancas por temporizador: exige correspondencia ao trecho
  narrado. Texto que mistura varias lembrancas nao escolhe uma prematuramente.
- Membrana cortical com faces/normais orientadas para fora, transparencia mais
  leve, contorno e reflexo controlados. Pontos do nucleo principal mais definidos,
  acabamento emissivo da superficie e vetor reutilizado nos pulsos das sinapses.
- 146 testes de logica/voz aprovados; 22 testes adicionais de movimento/render e
  estresse verificados. Tres deles precisaram redirecionar capturas/metricas para
  pasta temporaria por erro de gravacao, mantendo todas as assercoes originais.
  11 testes JavaScript aprovados, incluindo cem ciclos de consulta/cancelamento.
- Ensaio Qt nativo aprovado: formacao em 5,17 segundos, capturas intermediarias,
  orientacao real das normais, resposta/release da luz com nivel sintetico,
  foco da evidencia, tema refletido em pixels, busca vazia e movimento reduzido.
  Doze consultas/cancelamentos no renderizador sem crescer geometrias/texturas.
  Sem chamadas pagas a Fish, sem ensaio de microfone real e sem publicacao.

### Roteamento da fala e buscas sem resultado

- Reproduzidas variantes reais do historico de comandos, incluindo formas de
  tratamento, hesitacoes, "modo lembranca" e pedido indireto "eu quero que tu vai
  para aquele modo onde tu consegue puxar as lembrancas". Assunto explicito apos
  a entrada e aproveitado; condicionais e negacoes nao iniciam a consulta.
- Corrigido o encerramento imediato da transformacao quando uma consulta
  retornava vazia. Uma consulta concluida sem resultado ou indisponivel agora
  forma o cerebro com status honesto, sem fragmentos inventados, e retorna ao
  nucleo automaticamente. Cancelamento continua distinto de falha de consulta.
- Movimento reduzido tem um temporizador leve de ciclo de vida, sem animacao
  continua, para que os estados finais tambem expirem nessa preferencia.
- 139 testes Python aprovados, incluindo transcricao Live fragmentada passando
  pelo roteador real e supressao da resposta generica duplicada. Provedores de
  fala simulados; sem chamadas pagas e sem teste de microfone/conta real.
- 9 testes JavaScript aprovados. Ensaio Qt com projetos temporarios, comando
  indireto real, resposta de assunto e busca vazia; captura conferida mostrando
  cerebro e status de nenhuma lembranca, sem registros de exemplo no produto.

### Consulta por assunto e projetos existentes

"Tinha algum projeto na Forja que eu tinha comecado?" consulta metadados reais
de projects/manifest.json e library/artifact.json, sem iniciar o Codex, entrar na
Forja ou criar conteudo. Projetos e suas copias salvas nao sao contados duas vezes.
Arquivo ilegivel e comunicado como verificacao incompleta, nao como biblioteca vazia.

Lembrancas agora exigem correspondencia com o assunto inteiro, em palavras
completas, e mostram apenas o trecho relacionado. Pergunta vaga pede o assunto
com a forma neural aberta, sem fragmentos inventados. Historico de respostas do proprio assistente nao
entra como lembranca do usuario; propostas anteriores so entram quando pedidas.
Inventario geral explicitamente pedido usa fatos persistidos, nao conversa casual.

### Comandos naturais e consulta pendente (16/10)

- "Busca nas lembrancas", "pesquise nas memorias" e a variante "lembracas"
  entram na forma neural e perguntam qual assunto consultar. Sem assunto,
  nenhuma pesquisa generica e feita e nenhum registro e projetado.
- A resposta curta seguinte, como "sobre a Forja", completa a consulta na mesma
  sessao, durante uma janela de 35 segundos. A forma sem assunto retorna ao
  nucleo apos espera limitada; nao representa uma pesquisa concluida.
- Comandos de protocolo, atualizacao do dia e inventario real da Forja nao sao
  capturados por essa pergunta pendente. Ofertas vencidas ou de outra sessao
  nao consomem uma nova resposta.
- Respostas antigas de confirmacao/promessas do assistente sao filtradas.
  Relevancia apenas pelo titulo nao autoriza projetar um texto alheio ao tema;
  excecao limitada a valores categoricos de identidade como nome ou cidade.
  Registros originais nao foram apagados. Registros aninhados tambem recebem
  o mesmo trecho filtrado, sem reapresentar o texto completo.
- 104 testes Python e 8 JavaScript aprovados. Ensaio Qt nativo aprovado com
  projetos temporarios, distratores, pergunta sem assunto e resposta seguinte.
  Captura conferida: cerebro visivel, legenda discreta, nenhum fragmento falso.
  Voz validada na fila de teste, sem chamada paga ao Fish ou conta real.

Corrigida a massa de cor na dispersao: somente Points recebem deformacao com
deslocamento individual. Meshes e linhas conectadas desaparecem cedo, sem esticar
triangulos. Membrana cortical so aparece no fim da formacao; linhas e sinapses
aguardam a montagem. Dispersao escalonada, pontos menores e bloom mais contido.

- 95 testes Python e 6 JavaScript aprovados nesta rodada.
- Ensaio nativo com a pergunta sobre projetos: tres projetos temporarios reais,
  memorias de Spotify e agenda presentes como distratores, somente nomes e estados
  dos projetos na voz de teste e nos fragmentos. Formacao medida em 5,30 segundos.
- Capturas intermediarias em 25%, 45% e 65%; nenhuma superficie conectada com
  deformacao dispersiva. Captura da fase suspensa mostra pontos separados, sem
  os leques opacos reportados pelo usuario.
- Voz validada na fila de teste, sem chamada paga a Fish nem uso de conta real.

### Revisao de entendimento e fluidez

- 82 testes Python aprovados: incluem a frase exata reportada, fatos persistidos,
  exclusao da pergunta atual, conversa casual antiga, plano relevante antigo,
  falha de armazenamento, cancelamento e agrupamento da voz nativa. Incluem
  regressoes de memoria, protocolos, contexto de voz e limites de streaming.
- 6 testes JavaScript aprovados: formacao em 4,8 segundos, queda de quadros,
  cancelamentos, resultados atrasados e cem ciclos completos.
- Ensaio nativo com a frase exata e dados temporarios: busca real no arquivo de
  memoria, anunciacao e evidencia entregues a fila de voz de teste, tres planos
  relevantes visiveis, pergunta atual ausente e retorno ao nucleo. Formacao
  medida em 5,17 segundos incluindo entrega e compilacao inicial.
- Mudanca de tema confirmada tanto no estado quanto nos pixels da captura Qt.
  Nenhuma conta real ou chamada Fish paga foi usada no ensaio.

### Primeira integracao

- 52 testes Python: memoria, dispatcher, verificacao de interface, estados e audio.
- 10 testes adicionais de sincronizacao de apresentacao.
- 5 testes JavaScript: ciclo de vida, timeout, movimento reduzido, respostas fora
  de ordem e cem ciclos completos sem reter fragmentos.
- Dois ensaios nativos completos, com configuracao e registros temporarios:
  ponte Qt, tres registros persistidos recuperados, transformacao gradual,
  forma completa, estado observado, cancelamento e retorno ao nucleo.
- Vinte recuperacoes/cancelamentos no renderizador original: 46 geometrias antes
  e depois; nenhuma visualizacao ativa ao concluir.
- Conferencia visual no renderizador original e na janela completa do aplicativo.

Na primeira execucao de uma regressao existente, a gravacao de captura em
validation falhou por acesso ao arquivo. O mesmo teste passou redirecionando
somente as capturas para uma pasta temporaria; suas verificacoes foram mantidas.
O aviso de dependencia pynvml obsoleta e anterior e nao foi alterado nesta tarefa.

Nao foi feita chamada paga ao provedor de voz nem ensaio de conversa com conta
real. Os testes confirmam a ligacao ao sinal existente, nao latencia ou qualidade
do servico externo. Sem alteracao de credenciais, dados pessoais, assinatura do
EXE, configuracao do Windows ou publicacao no Git. O launcher local existente
carrega main.py deste projeto; nao foi necessario gerar outro executavel.
