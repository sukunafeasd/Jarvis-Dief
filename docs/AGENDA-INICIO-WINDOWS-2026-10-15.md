# Agenda e inicio automatico elevado

## Agenda

Listagens comuns e resumo diario excluem eventos automaticos do tipo
`birthday`, incluindo os aniversarios do proprio usuario. O filtro usa
`eventTypes` da API; nao apaga eventos nem filtra titulos arbitrarios.
Compromissos vindos do Gmail e outros tipos regulares continuam incluidos.
Pedidos explicitos podem usar `include_birthdays: true`, preservado tambem
na especificacao de atualizacao dos cards fixados.

Referencia: https://developers.google.com/calendar/api/v3/reference/events/list

## Inicio do Windows

A tarefa DIEF-JARVIS-Logon-<SID> substitui o registro antigo JARVIS_AI.
Usa a conta interativa atual, Highest, sem senha salva, SYSTEM ou alteracao
do UAC. Executa somente o EXE fixo, com diretorio de trabalho definido,
15 segundos depois do logon. Permite bateria e nao encerra o Jarvis depois
de algumas horas por limite padrao do Agendador.

O perfil consulta a tarefa real e pode desativa-la. A preferencia de
desativacao fica em autostart.json, separada das credenciais. Instalacoes
novas habilitam por padrao na primeira abertura administrativa real.
Testes e perfis isolados nao registram tarefas automaticamente.
Instalacoes gerenciadas usam o EXE da raiz, nao a pasta de versao.

Referencia: https://learn.microsoft.com/en-us/windows/win32/taskschd/security-contexts-for-running-tasks

## Validacao

246 testes passaram, incluindo 13 novos casos de agenda/inicializacao e
controle no perfil atual das configuracoes. Sintaxe de oito arquivos
validada. Revisao adicional sem novos problemas
materiais. A tarefa real foi cadastrada com confirmacao do Windows e
consultada novamente: pronta, habilitada, Highest, Interactive, EXE local
e pasta corretos, atraso PT15S, bateria permitida e limite PT0S.
A validacao normaliza nome da conta para SID, pois o Windows pode devolver
o nome em vez do identificador passado no cadastro.
As capturas das seis abas em 1366x768 e 800x600 foram gravadas na pasta
temporaria dief-settings-logon-fdoli9ev (16 imagens). Quatro capturas de
outros testes legados ainda emitiram aviso de escrita na pasta protegida;
nao foram consideradas evidencias visuais salvas.

Nao houve reinicializacao/logon real nem novo teste de voz com microfone.
Sem novas consultas a contas Google, alteracao de credenciais, EXE novo ou
publicacao de release. O EXE local existente foi mantido.
