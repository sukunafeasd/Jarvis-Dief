# Evolucao do nucleo: diagnostico inicial

Data: 2026-10-18. Escopo: auditoria anterior a implementacao solicitada no plano.
Nenhum codigo de producao, configuracao pessoal ou executavel foi alterado nesta etapa.
Este documento nao certifica o projeto inteiro: registra os caminhos lidos, testes
executados, limitacoes e prioridades. Nao houve chamadas pagas aos provedores.

## Arquitetura observada

- main.py (3816 linhas): sessao Gemini Live, roteamento antecipado de comandos,
  contexto de modos, despacho de ferramentas, captacao e reproducao, rotina diaria.
- ui.py (8111 linhas): janela, estados de apresentacao e integracao com renderizadores.
- core/gemini.py: chamadas auxiliares FAST/SMART/SEARCH e tentativas alternativas.
- core/llm_client.py: clientes de modelos locais e streaming de frases.
- core/fish_audio.py e core/voice_interrupt.py: filas PCM, sintese, cancelamento e VAD.
- core/application_context.py: selecoes, listas e operacoes recentes, com validade.
- core/task_execution.py: planos e evidencias, exclusivamente em memoria da sessao.
- core/action_outcome.py: distingue falha, pendencia, incerteza e resultado reportado.
- core/conversation_memory.py: historico SQLite, redacao de credenciais e contexto curto.
- core/memory_recall.py: recuperacao lexical e filtragem dos fragmentos apresentados.
- core/semantic_memory.py: indice semantico opcional dos fatos persistentes.
- core/personality.py: identidade, preferencias e instrucoes conversacionais existentes.
- actions/ e plugins/: ferramentas e contratos usados pelo despachante.

Ja existem mecanismos importantes. A atualizacao deve conectar e corrigir esses
mecanismos progressivamente, sem criar um segundo aplicativo ou um despachante paralelo.

## Evidencias confirmadas

### 1. Cobertura limitada dos atalhos de presenca

Chamada direta a core.spectro_commands.request(text, True):

| Frase | Resultado |
| --- | --- |
| Sai um pouco dai. | None |
| Ta muito na frente. | None |
| Nao consigo enxergar isso. | None |
| Deixa como estava antes. | None |
| sai da frente | minimal |
| fica um pouco menor | scale, fator 0.8 |

None significa que o atalho nao decidiu; NAO demonstra falha da conversa completa.
O modelo ainda pode escolher uma ferramenta. Falta medir esse percurso com contexto
e observar tanto a acao quanto a resposta. Nao resolver com listas infinitas de frases.

### 2. Planos sem encerramento nem continuidade entre sessoes

ExecutionLedger usa dicionarios locais e o contrato publicado nao oferece concluir
ou arquivar. Apenas planos cancelados sao removiveis quando existem 20 planos.
Reproducao: criar 20 planos e criar o seguinte gera 'Limite de planos ativos atingido'.
Anexar evidencias muda o estado para tracking, sem liberar o plano.
Uma sessao nova tambem perde os planos. Historico textual nao substitui estado de tarefa.

### 3. Busca principal de lembrancas permanece lexical

memory_recall.retrieve combina consultas LIKE com AND entre os termos e variantes,
depois filtra trechos e limita o resultado a tres itens. O caminho direto nao chama
o indice semantico opcional. Sinonimos sem palavras em comum podem ficar de fora.
Preservar filtros de origem e relevancia: ampliar busca nao pode voltar a exibir
afirmacoes aleatorias do assistente como lembrancas confirmadas.

### 4. Continuidade curta na reconexao

conversation_memory.prompt_context usa recent com seis mensagens e 2400 caracteres.
Existem tambem resumo de sessao e contexto do modelo; portanto isso nao significa
que toda conversa tenha apenas seis mensagens. Ainda assim, a retomada de tarefas
nao tem uma representacao persistente equivalente ao plano de execucao.

### 5. Limite de tempo das consultas auxiliares e por tentativa

core.gemini.call percorre ate nove entradas por FAST/SMART. O timeout padrao e
10000 ms, repassado por tentativa; nao existe nesse metodo um prazo total unico.
Isso permite acumulo de espera em falhas sucessivas. Nao e uma medicao da demora
real da conversa Live, cujo fluxo e distinto. Medir primeiro e adicionar um prazo
global e classificacao de erros antes de alterar modelos ou fornecedores.

## Testes executados

Primeira selecao: 108 testes, 5.036 segundos, todos passaram.
Modulos: round7_conversation_intent, round8_context_outcomes, round9_domain_guidance,
round10_conditional_commands, round11_natural_domains, round12_operation_followup,
round13_spoken_style, memory_recall_behavior, memory_voice_routing,
protocol_natural_language, interface_verification, voice_stream_boundaries,
dashboard_lifecycle e spatial_distribution_repair (prefixo test_).

Segunda selecao: 126 testes, 13.013 segundos; 122 passaram, duas falhas e dois erros.
Modulos: command_chaos_round, command_races_round2, fish_playback, voice_interrupt,
followup_state_round, data_integrity_round2, config_atomic_round2,
failure_recovery_stress, performance_bug_round e runtime_recovery_round2.

- Dois erros de UltronFollowup: Playwright ausente no ambiente .test-venv.
- Duas falhas de GateTests: detector VAD indisponivel no ambiente; isso impede
  concluir se ha regressao do algoritmo na instalacao do usuario.
- O traceback 'synthetic receive error' e uma falha injetada pelo teste de recuperacao.

Total desta etapa: 234 testes executados, 230 passaram. Ha 154 arquivos test_*.py
no repositorio; isto e uma selecao, nao a bateria completa nem teste de ponta a ponta.
Tempo de testes nao representa latencia da fala. Nao foram medidos Fish real,
microfone real, qualidade subjetiva de conversa, consumo de tokens nem FPS nesta etapa.

## Ordem de implementacao proposta

1. Preparar ambiente reproduzivel de testes e ponto de recuperacao incluindo arquivos
   ainda nao rastreados. O repositorio tem muitas alteracoes locais que devem ser preservadas.
2. Montar corpus fixo de 50 conversas com contexto: alvo, modo, ferramenta esperada,
   esclarecimento esperado e situacoes em que nenhuma acao deve acontecer.
3. Medir roteamento completo antes/depois. Reaproveitar ferramentas existentes com
   intencoes estruturadas, validacao de alvo e politica proporcional ao risco.
4. Corrigir ciclo de vida de planos; persistir objetivo, bloqueio e proximo passo
   sem transformar historico em autorizacao nem declarar conclusao sem evidencia.
5. Melhorar busca por significado com origem/data e fallback lexical, avaliando
   sinonimos, retomadas e falsos positivos antes de integrar na Forma Neural.
6. Medir fim de fala, primeira resposta, primeiro PCM e reproducao; limitar tempo
   total de consultas e impedir tentativas duplicadas apos resultados incertos.
7. Avaliar personalidade em dialogos, preservando instrucoes existentes e evitando
   respostas fixas. Opiniao e iniciativa devem depender do contexto observado.
8. Revalidar Gemini, Fish, interrupcao, Forja, Ultron, Espectro e cena original;
   so entao gerar pacote local, assinar Equipe Dief e validar instalacao preservando dados.

## Criterios de aceite

- Corpus mede acao correta, alvo correto, ausencia de acao indevida e verificacao do resultado.
- Ambiguidade sensivel pede esclarecimento; conversa casual nao vira tarefa.
- Plano retomado preserva objetivo e pendencias reais, sem executar ordens antigas.
- Memoria sem evidencias relevantes admite a ausencia, sem preencher com trechos recentes.
- Medicoes de voz distinguem espera do provedor, fila e reproducao; sem promessas numericas antecipadas.
- Cena original e recursos Three.js permanecem no pacote e carregam no Qt instalado.
- Atualizacao permanece local; publicacao e uma etapa separada.
