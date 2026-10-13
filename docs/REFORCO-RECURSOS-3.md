# Reforco de recursos: terceira rodada

## Entregas reais

- Notion em Conexoes: formulario, cadastro oficial, token DPAPI temporario,
  validacao da identidade antes de substituir conexao, pesquisa/leitura
  paginadas e criacao confirmada em pagina compartilhada.
- Outlook: envio Graph com Mail.Send e confirmacao humana, identidade conferida
  novamente, resultado distingue solicitacao aceita de entrega final.
- Planilhas: grafico de barras baseado na matriz real; escala nao corta valores
  negativos; edicao de celulas em copia nova preservando fonte e formulas textuais.
- Imagens: anotacoes por coordenadas validadas, cores aprovadas, original preservado.
- Downloads: URLs HTTPS publicas solicitadas, limite de 25 MB, sem seguir
  redirecionamento automaticamente e sem executar arquivos baixados.
- Backup: preferencias de perfil/aparencia exportadas por allowlist, sem campos
  de credenciais ou configuracoes de conexao; bancos e memoria anteriores mantidos.
- Reunioes: transcricao de arquivo de audio fornecido, usando o Gemini existente,
  somente apos confirmacao de envio; texto exige revisao, sem criar tarefas automaticamente.
- Manual do Jarvis atualizado: quando usar, IDs e parametros reais, como
  continuar leitura, consultar job_id e nao inventar sucesso.

## Validacao

Testes de criacao de XLSX/graficos, edicao literal e preservacao da fonte,
anotacao de PNG, tamanho de downloads, destino privado e redirecionamento,
Notion de identidade incorreta/conteudo aninhado e envio Outlook pendente/202.
Testes usam fixtures; nenhum email real foi enviado nem conta real autorizada.
Notion usa HTTP oficial com testes de contrato, nao um workspace real.
As preferencias pessoais nao foram exportadas pelos testes: configuracao de
teste explicitamente isolada. Nenhum EXE novo ou push GitHub.
Suite geral: 336 testes aprovados. Suite focada posterior: 35 testes aprovados,
incluindo o novo teste de transcricao com confirmacao e revisao obrigatorias.

## Ainda pendente

Os 32 itens continuam sendo categorias, nao 32 conexoes independentes.
Gravacao ao vivo de reunioes, execucao controlada de suites de projetos,
Atalhos iOS, controle nativo de sessoes/troca de saida de audio, restauracao
integrada, OAuth MCP remoto e atualizador assinado com rollback ainda nao
estao completos. Nao foram marcados como conectados ou implementados.

## Referencias

- https://developers.notion.com/reference/get-self
- https://developers.notion.com/reference/post-search
- https://learn.microsoft.com/en-us/graph/api/user-sendmail?view=graph-rest-1.0

DNS e validacao de URL dos downloads sao protecoes limitadas: nao representam
um proxy de rede isolado nem uma garantia contra todas as formas de rebinding.
