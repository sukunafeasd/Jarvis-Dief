# Segunda auditoria: cenarios, abertura e uso combinado

Data: 12/10/2026. Nao foram alteradas contas, APIs ou preferencias pessoais.

## Falhas reproduzidas e corrigidas

1. Abertura sem nenhuma apresentacao: o retorno loadFinished do nucleo chamava _render_presentation sem contexto. A sincronizacao acessava None e lancava AttributeError em callback Qt. O teste nativo reproduziu a excecao antes da correcao. A renderizacao agora ignora contexto inexistente.
2. A saudacao automatica cancelava a entrada e fazia a camera resolver em 320 ms. Fala e pensamento automaticos nao cancelam mais a aproximacao; interrupcao explicita continua disponivel.
3. A entrada comecava quando a pagina carregava, antes de o nucleo e o cenario terem renderizado. Os dois aguardam sinal de prontidao e compartilham o mesmo inicio; staging evita mostrar a cena completa antes da aproximacao.
4. Limpar removia apenas informacoes, mantendo o planeta e modo anteriores. Agora tambem remove foco planetario e restaura ambiente normal.
5. Pedidos explicitos de analise/execucao eram substituidos silenciosamente pelo modo de foco de uma noticia. Agora pedidos explicitos sao respeitados, salvo leitura detalhada/configuracoes; o retorno informa requested_mode e resolved_mode.
6. O nucleo recebia environment.mode sem aplicar aparencia correspondente. Ganhos emissivos agora distinguem os modos, inclusive em movimento reduzido.
7. Planetas continuavam visiveis em analise/execucao, parecendo restos de outro modo. Saem por transicao; analise destaca grade/rede, execucao sua estrutura tecnica, foco simplifica, normal restaura fundo discreto.
8. Trocar o modo apagava o estado de uma operacao real em andamento. A direcao visual nao cancela mais a operacao.
9. Retornos tardios do WebEngine podiam acessar widgets encerrados. Guardas de ciclo de vida, falha idempotente e sinal de prontidao unico.
10. Verificacao de saude contava tempo anterior ao carregamento e desistia cedo em inicializacao pesada. O prazo inicia no carregamento efetivo, com margem de 20 segundos.
11. Previa em canto ocupado podia deslocar outra sem atualizar os slots informados. Movimentacao agora troca os cantos e registra posicoes efetivas.
12. Voltar perdia clima anterior com o mesmo titulo, por exemplo hoje/amanha. Historico diferencia periodo, cidade, contato e leitura.
13. Atualizacao apos fala completa podia esperar audio de novo. Sincronizacao respeita conclusao da apresentacao.
14. Terminal aguardando foto desaparecia quando uma informacao chegava em janela menor. Mantem a area de envio e resolve espacos.
15. Com quatro previas, terminal e informacoes podiam escolher a mesma area livre. Conteudo tambem considera os paineis ativos como obstaculos.
16. A superficie interna da execucao excedia a altura do painel e cortava etapas. Ajuste de perspectiva agora enquadra a superficie inteira.
17. Uma pagina 3D que nunca emitia loadFinished podia deixar o observatorio em staging indefinidamente. Depois de 20 segundos a verificacao libera o fallback, sem manter a tela vazia para sempre.

## Evidencias

- Windows registrou duas quedas de pythonw em Qt6Core, codigo 0xc0000409. O evento nao fornece a excecao Python de origem; nao prova sozinho que ambas tiveram a mesma causa.
- Teste Qt/WebEngine nativo antes da correcao: AttributeError em _sync_presentation_view, chamado pelo loadFinished do nucleo, sem apresentacao aberta.
- Teste nativo depois: nove capturas, sem excecoes, modos efetivos conferidos e limpeza apos Saturno.
- Camera nativa: distancia adicional aproximadamente 22,4 no inicio, zero na chegada, tanto no nucleo quanto no fundo.
- Evidencias: validation/environment-second-audit/result.json e capturas na mesma pasta.
- Novos testes: test_interface_second_audit.py, test_environment_second_audit.py, test_spatial_lifecycle_audit.py.
- Bateria completa: validation/environment-second-audit/full-suite.log.
- Resultado geral: 454 testes, 453 passaram e um timeout de 30 segundos esperando o nucleo WebGL carregar. Nao foi tratado como bateria limpa.
- Repeticao isolada do conjunto afetado: os dois testes passaram em 14,7 segundos; registro refresh-recheck.log. A causa exata do timeout isolado nao foi comprovada.
- Testes locais adicionais finais: 11 casos de interface e 5 de ciclo de vida passaram, incluindo retorno do modo efetivo e fallback para carregamento que nao termina.
- Validacao ampla do observatorio passou com pixels animados, resolucoes ate 4K, seis planetas, cancelamento, suspensao e recursos estaveis. Gravação: validation/observatory-demo.webm.
- Diagnosticos locais futuros: %LOCALAPPDATA%/DIEF JARVIS/logs/runtime-faults.log. Guardam tipo de excecao e pilha, sem mensagem, variaveis, chave ou conteudo das conversas. Nao mascaram excecoes.

## Limites

O teste nativo nao conectou a IA, microfone, Gmail ou WhatsApp. Estados de fala foram simulados. Capturas e resultados de movimento nao garantem ausencia de todo bug ou compatibilidade com todos os drivers. Uma queda nativa futura deve ser investigada com o registro novo. As mudancas exigem fechar e reabrir o aplicativo; nao alteram codigo ja carregado num processo anterior. Sem novo EXE ou publicacao Git nesta rodada.
