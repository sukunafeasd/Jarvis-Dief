# Voz Fish e aproximacao do ULTRON

Alteracoes locais. Sem publicacao, migracao de contas ou mudanca da voz
selecionada pelo usuario.

## Voz

- Preservados os fragmentos incrementais originais, inclusive espacos e
  digitos repetidos. Nao inserir espacos dentro de palavras.
- Um ponto recebido depois de um numero pode ser o inicio de um decimal.
  Aguardar a continuacao, inclusive na fronteira de 400 caracteres.
- Nao sintetizar abreviacoes ou palavras incompletas por uma pausa curta
  na transcricao. O fim explicito da resposta libera o trecho restante.
- Manter o produtor disponivel para sintetizar texto posterior enquanto
  o audio preparado ainda escoa, com filas limitadas e cancelamento.
- PCM preservado sem ganho, reverberacao ou alteracao de velocidade.

Validacao: 103 testes de entrega, recepcao, interrupcao e fronteiras passaram.
Uma chamada real com frase neutra retornou 3,39 segundos de PCM; primeiro
audio em 3,17 segundos, maior intervalo observado entre pacotes de 204 ms.
O mesmo PCM passou pela fila de voz, drenada em cadencia real, sem alterar
nenhum byte. Amostra WAV salva em pasta temporaria, sem credenciais.

Limite: o teste de integridade nao demonstra equivalencia auditiva com a
amostra original do site. Timbre e eco percebido precisam ser comparados
ouvindo a voz. A chamada real e uma amostra curta, nao uma garantia de
latencia ou continuidade para todos os textos e condicoes de rede.

## ULTRON

Ativar o protocolo inicia uma aproximacao de 1,8 segundo usando a mesma
posicao e alvo de camera no planeta e no fundo espacial. Desativar retorna
ao observatorio. Atualizacoes da varredura nao reiniciam a viagem.
O planeta permanece fixo no mundo. Movimento reduzido aplica o enquadramento
final diretamente; o fundo e invalidado mesmo quando seu timer esta parado.

Validacao: 69 testes de protocolos, estado e abertura passaram, incluindo
WebGL real em 1440x900 e 390x844, captura de pixels, aproximacao, retorno e
movimento reduzido. Ensaio adicional em Qt/WebEngine confirmou o planeta
ampliado, dados associados a narracao, cameras coincidentes, posicao fixa
e retorno. Leituras deste ensaio foram sinteticas; nenhuma varredura ou
acao de seguranca foi executada contra o Windows.
