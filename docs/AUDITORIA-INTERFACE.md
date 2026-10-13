# Auditoria de interface e sincronizacao

Data: 12/10/2026. Projeto local: Mark-LV-main, DIEF JARVIS.

## Problemas encontrados e corrigidos

- Avisos sem identificador reutilizavam uma apresentacao de outro assunto, mantendo titulo e enquadramento errados.
- Finalizacao de aviso sem identificador podia encerrar o aviso errado.
- Identificadores baseados no relogio podiam se repetir em chamadas rapidas. Agora cada apresentacao tem UUID.
- Focos de transcricoes antigas podiam selecionar registros de uma resposta nova. Navegacao de fala exige a identidade atual.
- Ordinais de outro dominio podiam trocar a noticia, por exemplo uma segunda tarefa durante noticias.
- Animacoes de imagem sobrepunham a regra de visibilidade, exibindo fotos antes do audio reproduzido.
- Apresentacoes narradas iniciavam o prazo de desaparecimento antes da fala. Agora o prazo depende da conclusao do audio.
- Uma resposta sem relacao podia retomar a apresentacao interrompida. Retomada agora e explicita pelo controle da interface.
- Final de uma fala anterior podia concluir uma apresentacao nova ainda sem audio. Agora exige audio da apresentacao ativa.
- Carregamento tardio do renderizador perdia eventos e estado de pausa. Recupera tempo, eventos pendentes e cancelamento.
- Listas acima de vinte registros aceitavam foco em itens que nao estavam desenhados. Paginas internas mantem indices globais.
- Atualizacoes de telemetria apagavam e redigitavam todos os textos. Textos ja revelados permanecem estaveis.
- Filas limitadas removiam os eventos mais antigos silenciosamente. Mantem a ordem e sinalizam degradacao quando excedidas.
- Eventos com horario ja vencido aguardavam outro pacote de audio. Agora sao processados no mesmo lote.
- Dados parciais ou nulos quebravam listas e exibiam None ou valores enganadores. Contrato defensivo e numeros indisponiveis como --.
- Previa solicitada para canto superior ainda ficava embaixo. Posicoes superiores agora usam a faixa superior livre.
- Previa fixada podia cobrir conteudo ou terminal. Enquadramento considera as geometrias reais das previas.
- Conclusao das noticias sem nucleo pronto podia ser perdida; chegada tardia do nucleo restaurava a fase errada.
- Cena generativa podia se revelar ao terminar outra fala sem ter recebido seu proprio audio.
- Destaque de vento/chuva podia atingir uma metrica de outro dominio. Destaques climaticos ficam restritos ao clima.

## Verificacao

- 14 testes nativos novos em tests/test_interface_audit.py passaram.
- 8 testes de sincronizacao/Playwright em tests/test_presentation_audit.py passaram.
- 7 testes de terminal, anexos, previas e cenario em test_workspace.py passaram apos os ajustes.
- 6 testes de noticias fundidas no nucleo, pausa, conclusao e descarte em test_news_core.py passaram.
- Compilacao dos arquivos Python alterados e verificacao de sintaxe de presentation.mjs passaram.
- Bateria geral final: 438 testes passaram, sem falhas, em 599 segundos. Registro: validation/interface-audit/full-suite.log.
- A execucao anterior carregou o codigo antes do ajuste de colisao terminal/foto e teve uma falha em 431 testes. A bateria completa foi repetida no codigo final e passou.
- Capturas revisadas de comunicacoes, configuracoes e noticias.
- Sequencia visual gravada: validation/interface-audit/synchronization-demo.webm.
- O video usa tempo de reproducao simulado, sem voz real nem chamadas de IA.
- Matriz nativa: sete dominios, quatro previas, janelas 820x580 e 1366x768.
- Testes WebGL conferem movimento, pixels nao vazios, dimensoes menores e movimento reduzido.

## Limites e preservacao

- Nao houve login, leitura de mensagens pessoais, envio de mensagens ou consumo de API nesta auditoria.
- Nenhum segredo ou conta foi alterado ou publicado. Sem publicacao Git ou geracao de EXE nesta rodada.
- O protocolo recebe o tempo do PCM reproduzido; marcadores sem timestamps exatos continuam estimados.
- Retomada por voz usa a ferramenta interface_control/resume. Depende de a IA reconhecer o pedido e chamar a ferramenta.
- Atraso real do dispositivo de audio, reconhecimento do microfone e respostas dos provedores ainda exigem conversa ao vivo.
- Passar testes nao demonstra ausencia absoluta de bugs nem valida todos os provedores externos.
- Nao ha tarefas de lint/typecheck configuradas no projeto. Verificacao de sintaxe nao equivale a analise estatica completa.
- Avisos de depreciacao de pynvml/Pillow aparecem em testes; nao foram mascarados nem tratados como falhas funcionais.
