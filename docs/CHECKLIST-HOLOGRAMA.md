# Checklist da apresentacao holografica

- [x] Noticias normais e resumo inicial usam `fetch_news_package`, com imagens reais.
- [x] Imagens tentadas para cada noticia (miniatura da busca e metadata da fonte); ausencia nao gera foto inventada.
- [x] Revelacao progressiva avanca com PCM enviado para reproducao, nao com chegada dos dados.
- [x] Interrupcao cancela revelacoes futuras e preserva o contexto; teste de audio atrasado incluido.
- [x] Noticias projetadas dentro do nucleo original, com imagem, titulo, resumo e fonte; setas e foco por narracao.
- [x] Rosto/nucleo se reposiciona com a composicao, sem divisor de janela.
- [x] Clima possui montagem por camadas, sol/nuvem/chuva e revelacao dos dados.
- [x] Sistema possui arcos 3D cuja extensao reflete metricas reais, atualizados somente enquanto visiveis.
- [x] Tarefas possuem segmentos/nos proporcionais ao numero de tarefas; prioridades com acento proprio.
- [x] Agenda possui marcadores e aro temporal com montagem progressiva.
- [x] Arquivos, busca, memoria e demais dados possuem simbolos espaciais seguros e distintos.
- [x] Holograma pode ser arrastado e tocado para alternar repouso/escuta, nos dois renderizadores.
- [x] Estados repouso/fala/escuta/processamento permanecem distintos; quatro estados do nucleo inspecionados.
- [x] Fixar, mover, fechar, recolher e voltar preservam identidade/contexto; pin atual suporta uma apresentacao.
- [x] Configuracoes usam navegacao a esquerda e mantem perfil/chat/atividade/conexoes/IA; resumo inicial configuravel.
- [x] 24 testes automatizados, capturas nativas, movimento de chuva e alternancia de geometrias validados.
- [ ] Validacao completa conversando ao vivo com microfone, incluindo todas as materias do resumo inicial.
- [ ] Sessao de 30 minutos e medicoes de uso de CPU/GPU em hardware final.

Sincronismo sem timestamps de palavras do Gemini usa duracoes estimadas dos trechos
ancoradas na reproducao de PCM. Nao e alinhamento exato por palavra, e ainda pode
existir diferenca correspondente ao buffer do dispositivo de audio.

Capturas e resultados ficam em `validation/`. A ausencia de imagem em uma fonte
permanece explicitamente sem foto. Conta Google depende de integracao autorizada;
agenda e tarefas continuam locais. As melhorias nao equivalem a portar todos os
subsistemas React do alpha12 para Qt.

Interesses separados por virgula geram buscas separadas, reunidas por assunto sem
duplicar artigos. Imagens sao procuradas tanto na busca quanto no HTML/JSON-LD da
fonte; redirecionamentos publicos HTTPS sao limitados e validados.
