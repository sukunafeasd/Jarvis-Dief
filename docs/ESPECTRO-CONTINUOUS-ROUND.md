# Revisao local: observacao, marcacoes, voz e tarefas

Observacao UIA da janela ativa inicia automaticamente em todos os modos,
com intervalo de quatro segundos e acompanhamento de alvo a cada meio segundo.
Campos de senha e janelas identificadas como sensiveis continuam excluidos.
Nao e streaming continuo de video: imagens sao consultadas por screen_process.
Conteudo observado e contexto, nunca instrucao. A propria janela do Jarvis
usa o estado interno; a observacao UIA externa requer outra janela em foco.

"Pare de observar" funciona em qualquer modo e pausa antes de enviar contexto.
A pausa persiste. "Volte a observar" retoma. Falha de gravacao nao impede a
pausa imediata na sessao. Sair do Espectro nao encerra a observacao.

Marcacoes: contorno, circulo, seta, marca-texto, sublinhado, cruz e cores.
draw permite linhas/simbolos com 2 a 32 pontos normalizados no monitor real.
As sobreposicoes deixam cliques passar, expiram e sao removidas quando a janela
muda. Elas nao executam cliques; acoes usam as ferramentas existentes.
Atualmente um destaque/desenho substitui o anterior. Nao ha editor de pintura.

No Espectro, resultados estruturados viram notas compactas com valores reais,
erros e resultados vazios. Resumo diario automatico fica suspenso; pedido
explicito continua disponivel. Nenhuma nova apresentacao deve abrir na base oculta.

Voz: pequenas pausas de ate 120 ms preservam a evidencia de fala sem contar
ruido/eco como fala. A contagem de fala efetiva continua obrigatoria.

Tarefas: list descobre todos os planos da sessao; read mostra os resultados
por etapa; checkpoint guarda bloqueio e proximo passo. Evidencia expirada
fica nao verificada. Contexto automatico e compacto, limitado a tres planos.
Nao e novo modelo de IA nem garantia de resolver toda tarefa complexa.

Validacao desta rodada:
- Auditoria geral: 800 testes, 1 ignorado, sem falhas/erros.
  %USERPROFILE%/AppData/Local/Temp/dief-audit-core-q132obg_/report.json
- Foco em voz/Espectro/tarefas: 157 testes, sem falhas/erros.
  %USERPROFILE%/AppData/Local/Temp/dief-audit-core-0uc7mgl8/report.json
- Revalidacao final incluindo resumo diario: 172 testes, sem falhas/erros.
  %USERPROFILE%/AppData/Local/Temp/dief-audit-core-dbzb7mkz/report.json
- Renderizador nativo: aprovado.
  %USERPROFILE%/AppData/Local/Temp/dief-spectro-native-i_58rv61/report.json
- Janela UIA real de teste, captura, destaque e privacidade: aprovado.
  %USERPROFILE%/AppData/Local/Temp/dief-spectro-perception-70yv_ov3/report.json

Sem teste de conversa com microfone fisico/provedor pessoal nesta rodada.
Sem publicacao, build de EXE ou alteracao de versao. Reiniciar o launcher local
para carregar os fontes atualizados.
