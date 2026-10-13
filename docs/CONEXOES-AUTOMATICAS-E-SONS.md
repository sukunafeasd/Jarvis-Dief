# Conexoes automaticas e sons

## Correcoes

- Os testes de conexao agora pertencem ao aplicativo, nao a uma janela de configuracoes descartavel.
- Cada abertura verifica contas salvas em segundo plano. A verificacao tambem e renovada a cada cinco minutos e ao abrir Conexoes quando o resultado estiver vencido.
- Gmail, WhatsApp e plugins externos habilitados com autorizacao salva usam seus verificadores reais. Credencial sem autorizacao nao vira conexao confirmada. Nenhum fluxo OAuth e aberto automaticamente.
- Resultados vencidos permanecem como ultimo teste conhecido enquanto a nova verificacao acontece. Falhas de rede/autorizacao substituem o resultado anterior.
- Ate tres verificacoes simultaneas, deduplicacao por provedor e protecao contra respostas atrasadas. Uma chamada que excede o prazo deixa de manter o indicador em verificacao; threads de rede nao podem ser interrompidas a forca e permanecem deduplicadas ate retornarem.
- Sons originais mais audiveis para botoes, alternadores, navegacao, escuta, processamento, repouso, despertar, projecao, fixacao, conclusao e musica.
- Cliques nao cortam avisos/conclusoes. Efeitos abaixam durante a voz. Ambiente espacial discreto silencia durante fala, musica confirmada e janela oculta/minimizada; repouso reduz o volume.
- Animacao orbital de musica acompanha reproducao confirmada, sem inventar batidas; respeita movimento reduzido.

## Validacao

- 71 testes focados aprovados, incluindo estados, deduplicacao, revalidacao, sons, atualizacao diaria, controles, ambiente, fixados e renderizacao WebGL em desktop/mobile.
- Cinco verificacoes nativas aprovadas: teste automatico antes das configuracoes, estado compartilhado, estado preservado ao reabrir, arquivos de audio carregados e suspensao ao minimizar.
- Sintaxe Python e JavaScript verificada.
- Captura isolada em `validation/connections-sounds/connections.png`; resultado em `result.json` na mesma pasta.
- Testes usaram contas sinteticas. Nao houve leitura de mensagens pessoais, nova autorizacao de contas nem audicao do dispositivo fisico. A qualidade percebida dos sons precisa ser conferida no uso real.
- Nao foi gerado um novo EXE; o atalho existente inicia este projeto. Encerrar e reabrir o Jarvis carrega as alteracoes.
