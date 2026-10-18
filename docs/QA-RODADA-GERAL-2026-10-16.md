# Rodada geral local - 16/10/2026

## Escopo e correcoes

- Conexoes desativadas: verificadores e cards fixados respeitam a desativacao antes e depois de consultas. Resultados atrasados nao reconectam plugins nem atualizam cards contra a preferencia atual.
- Forma Neural: o termino da manifestacao libera o estado da janela somente para a mesma consulta. Falhas ou ausencia do renderizador apresentam uma alternativa textual honesta e nao bloqueiam a proxima lembranca.
- FORJA: a entrada encerra a Forma Neural e aguarda sua recomposicao antes da viagem da camera. Falhas de renderizacao restauram a interface e o roteamento normal; uma nova entrada recarrega a pagina e aceita o primeiro comando, sem repetir automaticamente a criacao.
- Interrupcao digitada/remota: comandos de parada reconhecidos sao locais, nao despertam o assistente nem viram uma nova solicitacao ao modelo. Invalidam comandos anteriores ainda em espera.
- ULTRON: o encerramento impede o inicio de consultas que aguardavam o bloqueio de serializacao e rejeita resultados concluidos depois do fechamento. Isso nao equivale a cancelar uma operacao do Windows ja aceita.

## Verificacao final

- Bateria funcional isolada: 534 testes executados, sem falhas, um ignorado porque a conta Windows nao permite criar o link simbolico exigido pelo caso.
- Bateria visual: 22 testes aprovados, incluindo enquadramento, pixels, movimento, inicializacao e carga de renderizacao.
- Ciclo e movimento neural em JavaScript: 11 testes aprovados.
- Regressao de encerramento do ULTRON: caso anteriormente intermitente repetido 30 vezes, sem falhas apos a correcao.
- Ensaios nativos Qt/WebEngine aprovados para FORJA, Forma Neural, configuracoes/cards e ULTRON. FORJA inclui F11, recomposicao neural antes da camera, recuperacao de falha e primeiro comando apos recarga. Forma Neural inclui retorno automatico e 12 ciclos repetidos.
- Conferencia de sintaxe: 406 arquivos Python e 42 modulos JavaScript locais, sem erros detectados na rodada.

Os testes usam dados temporarios, contas falsas e provedores simulados quando necessario. Nao houve teste de voz Fish pela API real, login em contas pessoais, cobranca de geracao Codex nem execucao de limpeza/recuperacao destrutiva. Os ensaios nao demonstram ausencia de todos os bugs nem garantem uma taxa de quadros constante em qualquer computador.

## Reproducao

Na raiz do projeto, com as dependencias locais instaladas:

```powershell
.\.venv\Scripts\python.exe -B tools/run_local_audit.py
.\.venv\Scripts\python.exe -B tools/run_local_audit.py --visual
node --test tests/neural-lifecycle.test.mjs tests/neural-evidence-motion.test.mjs
```

O executor grava logs, relatorio JSON e capturas em pastas temporarias. A captura Playwright e o arquivo de metricas sao redirecionados para essas pastas, mantendo as verificacoes originais. Fixtures antigas de entrega de comandos foram isoladas das atualizacoes de personalidade; a personalidade possui testes separados.

## Evidencias desta execucao

- Funcional: `%TEMP%\dief-audit-core-biu63ch5`
- Visual: `%TEMP%\dief-audit-visual-05dxko7k`
- FORJA nativa: `%TEMP%\dief-forja-native-mrh3lv4k`
- Neural nativa: `%TEMP%\dief-neural-native-w9gc1e98`
- Configuracoes/cards: `%TEMP%\dief-observatory-ucwxtw0w`
- ULTRON nativo: `%TEMP%\dief-ultron-native-nw56kl3b`

Alteracoes restritas ao projeto local. Nenhum release, publicacao, novo EXE ou alteracao de credenciais e dados reais nesta rodada.
