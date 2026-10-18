# Voz e resumo: revisao local

- Perfil tem a opcao "Silenciar sons do painel". Ela nao desliga a voz, o microfone ou a musica. Salvar perfil persiste a escolha.
- A coleta do dia consulta fontes reais em paralelo. A preparacao das fontes nao bloqueia o ciclo de audio.
- Com Fish configurado, os capitulos sao narrados diretamente a partir dos dados consultados, sem uma rodada adicional da IA para cada assunto. Gmail identifica explicitamente quando apenas cabecalhos foram consultados.
- Consultas ao vivo usam hologramas sem moldura; previas fixadas continuam com seus cards. O progresso da atualizacao conserva seus elementos entre resultados das fontes.
- A reproducao tem um executor exclusivo, fila limitada e pequeno buffer inicial. O PCM recebido nao recebe eco, reverb, ganho ou alteracao de velocidade.
- Pausas de sintese usam o estado de processamento, sem encerrar a noticia. Sons do painel nao se sobrepoem a voz ou as lacunas de preparacao da fala.
- Atualizacoes parciais registram as fontes pendentes; elas nao sao anunciadas como completas. Uma nova solicitacao pode consultar as fontes novamente, sem repetir automaticamente o resumo a cada frase.
- Falhas da Fish nao substituem silenciosamente a voz por outra. A falha fica no registro e uma nova resposta pode tentar novamente.
- O som ambiente e gerado em vetores, reduzindo trabalho na abertura. Nenhum plugin carregado dinamicamente foi removido como se fosse codigo morto.

Os testes usam dados sinteticos e provedores simulados: nao enviam mensagens, executam limpezas nem gastam a API de voz. Qualidade audivel e latencia de rede ainda precisam ser conferidas no uso real, na saida de audio escolhida. Esta revisao nao foi publicada no GitHub.
