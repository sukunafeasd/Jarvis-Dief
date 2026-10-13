# Terceira auditoria: sequencias e consistencia de estado

Data: 12/10/2026. Contas, credenciais e preferencias pessoais preservadas.

## Correcoes

- Reabrir durante recolhimento cancelava apenas a aparencia, nao o callback atrasado que apagava o contexto. Cada recolhimento agora tem identidade propria; reabrir ou interromper invalida a finalizacao antiga.
- Uma apresentacao fechada era marcada como retomada, mas continuava escondida. Retomada agora exibe, reenquadra e sincroniza o conteudo.
- Retomar em repouso retornava sucesso embora a cena nao pudesse receber audio. O comando recusa esse estado com orientacao para ativar o Jarvis primeiro.
- Recuperacao por dominio no historico perdia o item selecionado. Preserva a selecao real.
- Retomada zerava um relogio de audio ja ativo, apesar de os timestamps do provedor continuarem cumulativos. O relogio ativo preserva o tempo; um relogio efetivamente cancelado inicia uma nova epoca.
- O navegador podia somar de novo audio de outra resposta ao retomar. Resume recebe a origem atual do relogio e compensa o deslocamento.
- Pacote de transcricao sem text lancava KeyError em callback Qt. Texto ausente ou invalido e ignorado sem fabricar uma fala.
- Texto nulo, timestamp invalido, NaN/infinito ou duracao invalida podiam quebrar ou contaminar o agendador. Entradas sao validadas; audio inexistente nao marca reproducao ativa.
- Um retorno de foco ja agendado podia alterar uma cena apos a pausa. Foco originado da fala e ignorado enquanto pausado; selecao explicita continua disponivel.
- Reabertura renderiza novamente a superficie para desfazer opacity/animacao de saida, em vez de mostrar uma superficie ainda invisivel.

## Verificacao

- Oito casos iniciais reproduziram cinco falhas e tres excecoes antes das correcoes.
- Conjunto novo final: 11 casos em test_interface_third_audit.py, incluindo compensacao do tempo no navegador.
- As tres auditorias de interface passaram juntas: 36 testes.
- Relogio de apresentacao: 14 testes passaram.
- Cena/comandos: 12 testes passaram.
- Noticias no nucleo: 6 testes passaram.
- Auditoria de apresentacao no navegador: 8 testes passaram.
- Upgrade de apresentacoes: 5 testes passaram. Total dos conjuntos focados nesta rodada: 81 testes, sem falhas.
- Verificacao Python e sintaxe de presentation.mjs passaram.
- Qt/WebEngine nativo: reabrir durante saida, restaurar selecao e retomar noticia fechada passaram sem excecoes.
- Evidencias nativas: validation/interface-third-audit/native-result.json e capturas na mesma pasta.

## Limites

Nesta rodada foram executados os conjuntos afetados, nao novamente a bateria completa do projeto. Testes nativos usam perfil temporario e dados sinteticos, sem API, microfone ou mensagens reais. Avisos de depreciacao de pynvml e um aviso de liberacao COM/IUnknown apareceram na verificacao do relogio; nao foram ocultados, e o processo concluiu com codigo zero. Nao houve novo EXE, publicacao Git ou garantia de ausencia absoluta de bugs. Fechar e reabrir o Jarvis e necessario para carregar as mudancas.
