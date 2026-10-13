# Controle de aplicativos

## Fluxo de execucao

O executor transmite um ApplicationContext compartilhado para acoes e plugins.
O contexto guarda o aplicativo confirmado e o ultimo pedido do usuario, com
validade de dez minutos. As respostas das ferramentas incluem esse contexto.
Uma continuacao de pesquisa no Spotify permanece no Spotify; um pedido explicito
de pesquisa na web pode mudar o destino. Isto e roteamento deterministico, nao
compreensao perfeita de qualquer frase.

A abertura no Windows usa executaveis conhecidos, App Paths ou identificadores
exatos de Get-StartApps. Nao digita nomes na busca do Windows. Antes de confirmar
a abertura, verifica se existe uma janela correspondente ao aplicativo.

## Controles e segundo plano

- app_control inspeciona janelas e controles reais via Windows UI Automation.
- A pesquisa exige um unico campo identificavel e suporte a ValuePattern.
- A escrita verifica o valor do campo sem mover mouse ou dar foco a janela.
- Botoes e campos ambiguos nao recebem cliques nem escrita automatica.
- browser_control oferece sessoes headless com perfil proprio do Jarvis.
- O perfil oculto nao compartilha o login do navegador pessoal; pode precisar
  de autenticacao separada e pode ser recusado por determinados sites.
- computer_control continua sendo uma alternativa VISIVEL de mouse/teclado.
  Um pedido background=true e recusado nessa ferramenta.

Dados de paginas e nomes de controles sao observacoes, nao instrucoes confiaveis.
APIs de servicos e controles semanticos devem ser preferidos a coordenadas.

## Limites importantes

Escrever e verificar uma consulta nao confirma resultados encontrados nem musica
reproduzida. O executor deve inspecionar o resultado antes de afirmar conclusao.
Apps que nao exponham controles acessiveis podem precisar de integracao propria
ou controle visivel. Nao ha garantia de controle oculto de todos os programas.
O controle legado de coordenadas continua disponivel e nao foi substituido por
um agente visual universal. Nao foram instalados plugins externos adicionais.

## Verificacao

Testes cobrem continuacao Spotify, destino web explicito, expiracao do contexto,
abertura confirmada, campos duplicados, verificacao de valor, botoes web ambiguos
e perfil web oculto separado. Tambem verificam a recusa de controle global oculto.

Nesta revisao nao foi executado um comando real de pesquisa/reproducao no Spotify
da conta do usuario. E necessario reiniciar o Jarvis para carregar as novas
ferramentas e realizar essa verificacao interativa. As credenciais e a autorizacao
existente do Gmail nao foram alteradas.
