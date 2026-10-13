# Quinta auditoria: execucao, pendencias e dados de audio

Data: 12/10/2026. Contas e credenciais preservadas.

## Correcoes

- Operacao aguardando confirmacao desaparecia pelo prazo de recolhimento. Pendencias permanecem visiveis ate um novo estado ou fechamento explicito.
- Conclusao de outra ferramenta apagava o estado da operacao em andamento. O diretor acompanha operacoes por nome/etapa e preserva o foco atual.
- Ao terminar a operacao em primeiro plano, outra ainda ativa nao voltava ao painel. Agora seu estado real e restaurado sem prazo de recolhimento.
- Evento finished nao acionava a conclusao correspondente no cenario. Tratamento alinhado ao evento emitido pelo backend.
- Estado desconhecido e cancelamento podiam gerar efeito resolved, parecendo sucesso. Estado desconhecido e ignorado; cancelamento usa settle.
- Conclusao tardia de uma operacao cancelada podia gerar efeito de sucesso. Identidades canceladas sao lembradas em lista limitada; nova execucao explicita e permitida.
- Dados de musica com item de tipo incorreto ou duracao infinita lancavam excecoes. Dados invalidos sao descartados sem inventar reproducao.
- is_playing com texto false era interpretado como verdadeiro. Apenas o booleano true indica reproducao.
- Audio NaN podia ser convertido em intensidade maxima e acender o nucleo. Valores nao finitos geram nivel zero.
- PowerShell nao estava na lista de operacoes exibidas no painel. A etapa agora aparece com nome correto, sem alterar privilegios ou executar comandos durante o teste.

## Verificacao

- Os oito casos iniciais reproduziram seis falhas e duas excecoes. Um caso adicional reproduziu o painel PowerShell oculto.
- 12 testes de operacao/audio passaram.
- 17 testes de ambiente passaram.
- 44 testes das auditorias de interface passaram.
- 7 testes de terminal/anexos/cenario passaram.
- Total dos conjuntos focados: 80 testes sem falhas. Sintaxe Python verificada.
- Validador Qt/WebEngine nativo passou em nove sequencias, incluindo pendencia preservada, conclusao atrasada ignorada e etapa visual do PowerShell sem executar comando.
- Validador reutilizado: tools/validate_native_sequences.py. Evidencias em validation/interface-third-audit/native-result.json e pending-operation.png.

## Limites

O acompanhamento visual nao cancela por si so um processo externo do Windows. O protocolo atual identifica ferramenta/etapa, mas nao recebe um ID unico de transacao: duas execucoes simultaneas da mesma ferramenta e mesma etapa ainda podem ser ambiguas. A lista de cancelamentos e limitada a 64 identidades. Nenhuma conexao real de musica ou envio de mensagem foi usado nesta auditoria. A bateria completa nao foi repetida. Sem novo EXE ou publicacao Git. Reiniciar o Jarvis e necessario para carregar as mudancas; passar nos testes nao demonstra ausencia absoluta de bugs.
