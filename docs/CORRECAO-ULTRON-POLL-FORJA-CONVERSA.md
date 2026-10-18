# ULTRON: atualizacao da tela e conversa na Forja

## Falha reproduzida

O primeiro estado ULTRON chegava a cena. Os estados seguintes, enviados pelo
poll do Qt, continham um poll_token=object() usado apenas para reconhecer a
resposta da thread. Esse objeto chegava a json.dumps no SpatialCoreView e
levantava TypeError. A cena ficava com o estado anterior (como Defender 14,3%)
e a funcao nao chegava ao aviso de conclusao.

O host agora valida a identidade e geracao do poll e remove esses campos
internos antes de armazenar ou enviar o payload. O controle contra respostas
antigas continua preservado. Status gerado durante uma varredura retorna
scan_wait, e o adaptador nao o marca como completed.

Testes incluem o caminho real de serializacao (nao um mock de sync_ultron)
e uma janela Qt/WebEngine com poll sintetico: Defender 14,3%, conclusao,
aviso unico, dados acompanhando a narracao e retorno ao Jarvis.
Uma consulta real somente leitura tambem concluiu as sete etapas em cerca de
seis segundos neste computador. Nenhuma limpeza ou reparo foi executado.

## Forja

O roteador nao usa mais steer como alternativa para qualquer frase desconhecida.
Conversas, perguntas de capacidade, hipoteses, explicacoes, negacoes e pedidos
de opiniao retornam ao fluxo normal do Jarvis. Ordens explicitas continuam no
projeto; consultas de progresso continuam somente leitura. Abrir um projeto
exige um pedido ancorado, nao uma ocorrencia de "abrir" em uma pergunta ou
negacao. Sim/nao so sao tratados como autorizacao quando existe pedido pendente.
A entrada textual da Forja tambem passa pelo fluxo normal de conversa.

O contexto fornecido ao modelo distingue discussao de ideias e ordens de
execucao. O adaptador continua exigindo o texto real atual da pessoa; nao
autoriza um comando inventado pelo modelo. Pedidos nao reconhecidos pela
gramatica local seguem para conversa, nao executam por suposicao.

## Escopo

Mudancas somente locais, sem publicacao ou alteracao de contas/credenciais.
Os testes de conversa e criacao usam runtimes simulados, sem trabalhos pagos
ou alteracao dos projetos reais. A conversa livre com a IA depende da sessao
de voz conectada; nao foi validada com um dialogo de microfone neste ensaio.
