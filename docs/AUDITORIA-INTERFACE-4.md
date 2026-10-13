# Quarta auditoria: previas e recuperacao de dados

Data: 12/10/2026.

## Falhas corrigidas

- Fixar uma lista perdia o registro selecionado ao expandir: a previa agora recebe o foco real da apresentacao.
- Restaurar uma previa atualizada usava o snapshot antigo e podia sobrescrever os dados novos. A restauracao usa a previa atual e atualiza o contexto correspondente.
- Remover uma previa apagava o contexto fixado de outro assunto. Desfixar altera apenas o contexto correspondente.
- Uma previa salva nao podia ser aberta sem historico de conversa. Abrir o dominio consulta a previa disponivel antes de procurar historico; o indicador de snapshot salvo permanece preservado.
- Contagem de tarefas indisponivel aparecia como None ou era inferida indevidamente. Agora mostra --, sem fabricar um total.
- Titulo nao textual podia lancar AttributeError no callback Qt. Campos textuais sao validados e titulos ausentes/invalidos recebem o nome correto do dominio.
- O texto alternativo da previa sumia antes de o 3D estar pronto. Permanece durante o carregamento; a troca so ocorre quando o renderizador confirma prontidao. Retorno tardio de uma view antiga nao altera a previa nova.
- Captura nativa revelou molduras duplicadas na previa. O conteudo embutido usa apenas a moldura externa; cards independentes mantem o acabamento original.

## Verificacao

- Seis casos iniciais reproduziram quatro falhas e duas excecoes antes das correcoes.
- Oito testes novos passaram em test_interface_fourth_audit.py.
- Todas as auditorias de interface juntas: 44 testes passaram.
- Conexoes e persistencia de previas: 11 testes passaram.
- Cena e comandos: 12 testes passaram.
- Terminal, anexos e cenario: 7 testes passaram.
- Total dos conjuntos focados: 74 testes, sem falhas.
- Verificacao de sintaxe Python passou.
- Validacao Qt/WebEngine nativa passou com seis sequencias, incluindo selecao fixada, dados atualizados, remocao independente e abertura sem historico.
- Evidencias do validador reutilizado: validation/interface-third-audit/native-result.json e pinned-weather-latest.png.

## Limites

A bateria completa nao foi repetida nesta rodada. Perfil e dados sinteticos foram usados na validacao nativa, sem voz/API, leitura de mensagens pessoais ou alteracao de credenciais. Nao houve novo EXE ou publicacao Git. Fechar e reabrir o aplicativo e necessario para carregar o codigo novo. Os testes nao garantem ausencia absoluta de bugs.
