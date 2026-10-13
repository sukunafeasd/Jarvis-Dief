# Conexoes e uso dos 32 recursos

## Checklist desta rodada

- [x] Ferramentas locais identificadas separadamente de contas externas.
- [x] Locais ativos por padrao, com disponibilidade calculada pelas dependencias.
- [x] Controle UIA exige permissao real de administrador, nao um estado inventado.
- [x] Testar ferramenta local nao abre formulario de login nem gerenciador vazio.
- [x] Google Agenda/Drive/Gmail envio com caminho de configurar, autorizar e testar.
- [x] Spotify com nova autorizacao ao reconectar e identificacao da conta.
- [x] Conta Spotify diferente da esperada preserva autorizacao anterior.
- [x] Outlook nao reutiliza cache de outro aplicativo ou conta esperada diferente.
- [x] Home Assistant/MCP com configurar e testar o servidor escolhido.
- [x] Reconectar separado de testar, inclusive Gmail leitura e WhatsApp.
- [x] Links oficiais de cadastro Google, Spotify e Microsoft nos formularios.
- [x] Contagem de conexoes inclui servicos externos dos plugins, nao somente o Gmail.
- [x] Botoes empilhados em linhas compactas, evitando corte e sobreposicao.
- [x] Manual para os 23 plugins e para memoria/pesquisa com passos e exemplos.
- [x] Parametros de ferramentas explicados sem alterar enums ou IDs do contrato.
- [x] Checklist completo de 32 recursos consultavel pelo Jarvis, com cobertura parcial explicita.
- [x] Exemplos ilustrativos nunca tratados como IDs/caminhos/dados executaveis reais.

## O que significa ativo por padrao

Nao e necessario conectar uma conta para usar notas, projetos, busca local,
clipboard, documentos, planilhas, planejamento ou backup. Dependencias ausentes
ou falta de administrador produzem estado de reparacao, nao Conectado falso.
As quatorze ferramentas locais foram ativadas no perfil atual, por pedido
explicito do usuario. Nenhuma credencial, conta ou outra preferencia foi
alterada. Novas instalacoes mantem os defaults habilitados; a interface
continua identificando plugins invalidos ou dependencias indisponiveis.

Contas externas continuam exigindo a autorizacao do seu dono. As permissoes
solicitadas sao as usadas pelas funcoes implementadas; instalar um plugin nao
concede permissoes inexistentes. Confirmacoes de envio e alteracoes sensiveis
permanecem no painel. Nao ha remocao de protecoes de credenciais.

## Manual do assistente

resource_diagnostics catalog descreve os 32 itens e sua cobertura.
resource_diagnostics guide com tool igual ao nome real retorna sequencia,
limites, exemplo nao executavel e protocolo de verificacao. Os schemas dos
plugins remetem a esse manual e incluem descricoes adicionais dos parametros.
O prompt orienta consultar o manual para tarefas complexas/desconhecidas.

O manual nao substitui o schema real, a observacao dos controles, autorizacao
da conta nem a consulta posterior ao resultado. Dados externos nao viram
instrucoes ou permissoes. Paginas restantes, corpos parciais e envio incerto
precisam ser informados; nao podem virar conclusao inventada.

## Limites mantidos

Esta rodada reforca conexoes e orientacao de uso; nao implementa todas as partes
pendentes dos 32 itens. Atualizador automatico/rollback, Atalhos iOS, Notion,
gravacao/transcricao de reunioes, sessoes nativas de midia e outras lacunas
continuam descritas em RECURSOS-32.md. Nao ha botao que simule conectar uma
funcao que ainda nao foi implementada.

Testes de conexao/troca de conta nesta rodada usam fixtures/mocks. Nao foi
autorizada ou substituida uma conta real, enviado email, enviado WhatsApp
ou controlado dispositivo real. Nenhum novo EXE ou push GitHub realizado.

Fonte oficial do perfil Spotify: https://developer.spotify.com/documentation/web-api/reference/get-current-users-profile

Verificacao: suite geral aprovada; 26 testes focados em recursos, politicas e
interface aprovados, 19 de configuracoes e 25 de plugins essenciais aprovados.
Os dois testes adicionais de troca de conta Spotify passaram em rodada
separada da suite geral. Compilacao Python aprovada. Botoes oficiais de cadastro
testados com abertura de navegador simulada, sem realizar login real.
