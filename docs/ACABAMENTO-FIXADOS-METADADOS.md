# Acabamento dos fixados e metadados

## Escopo

Preservar as projecoes abertas aprovadas, melhorar os icones e os cards
persistentes e retirar informacao secundaria perdida nos cantos.

## Checklist

- [x] Fontes das projecoes e do clima junto ao titulo, sem rodape distante.
- [x] Fontes ocultas nas previas compactas; fonte preservada nos dados.
- [x] Noticias e atualizacao diaria preservam seus layouts especificos.
- [x] Cards nativos com fundo solido mais rico, bordas continuas duplas,
      cantos arredondados e condutores nos quatro lados.
- [x] Removido fundo opaco da pagina WebGL dentro do card fixado, que cobria
      o acabamento do card nativo.
- [x] Previas fixadas ampliadas para ate 304 x 190, com icone maior.
- [x] Chuva mais visivel, neve suave, sol pulsante, superficies com linhas
      luminosas, orbitas e particulas com ritmos distintos por dominio.
- [x] Reacao discreta ao cursor somente no icone; texto nao acompanha o cursor.
- [x] Movimento reduzido, pausa e janela oculta respeitados.
- [x] Configuracoes com campos solidos mais preenchidos, bordas arredondadas,
      destaques mais vivos e material consistente.

## Validacao

- Tres testes novos exercitam fontes em nove dominios, oito icones compactos,
  pixels distintos entre quadros, hover, pausa e movimento reduzido.
- Testes existentes de projecoes, movimento, controle, fixados, workspace,
  configuracoes, telas de entrada e clima foram executados.
- A referencia de geometria foi atualizada para verificar estabilidade e
  limites, pois padding e tamanho do icone mudaram intencionalmente.
- Quatro verificacoes nativas passaram: clima fixado preservado, painel
  transparente, icone animado e condutores das configuracoes ativos.
- Revisao independente identificou dois casos adicionais corrigidos e
  retestados: invalidacao da pintura da luz inferior e desligamento da reacao
  ao cursor ao ativar movimento reduzido numa apresentacao pausada.
- Capturas revisadas em `validation/unframed-native` e `validation/living-pins`.
- Sintaxe Python e JavaScript alterados verificada.
- Foram exercitados 50 testes focados distintos em grupos isolados, com
  retestes dos casos ajustados; nao foi executada a suite completa do projeto.
- Dados de demonstracao apenas; nenhuma leitura de e-mail ou mensagem pessoal,
  alteracao de contas, EXE novo ou publicacao no Git.

## Uso

Encerrar e reabrir pelo atalho existente carrega as alteracoes. A referencia
enviada serviu para a densidade e acabamento futurista, nao para transformar
as projecoes abertas novamente em cards. Nao houve verificacao de conversa
real com microfone nesta rodada.
