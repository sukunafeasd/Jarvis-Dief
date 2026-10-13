# Auditoria da interface - rodada 7

Data: 13/10/2026.

## Correcoes

- Previa de arquivos/memoria com emptyText nulo causava TypeError ao ser fixada. O texto agora usa a mensagem disponivel ou informa ausencia de itens.
- Campos textuais de registros recebendo listas, objetos ou numeros apareciam como representacoes de objetos. Normalizacao descarta esses valores sem modificar o objeto original.
- region, observed, uptime e emptyText invalidos recebem texto vazio, preservando os campos opcionais ausentes.
- Numeros infinitos, NaN e inteiros fora da faixa numerica do renderizador sao convertidos em valores indisponiveis nos campos diretos do modelo e dos registros. Estados booleanos permanecem intactos.
- Tempos inteiros excessivamente grandes causavam OverflowError no sincronizador de fala. Agora sao rejeitados e os trechos usam a estimativa segura existente.
- Numeros nao representaveis causavam excecao tambem na previa textual. Agora exibem --, sem fabricar um valor.
- Registros sem titulo/detalhe exibiam apenas um separador. O texto de reserva agora ignora esses separadores vazios.
- Um detalhe vazio ocultava o prazo da tarefa na previa e na alternativa textual. O prazo agora e usado quando nao ha detalhe.

## Verificacao

- Execucao completa: 502 testes aprovados em 618 segundos. A execucao iniciou antes do ultimo ajuste de texto de reserva; por isso os conjuntos afetados foram repetidos depois, conforme abaixo. Os dois casos adicionais de texto foram executados na rodada focada, nao no total de 502.
- Seis testes iniciais reproduziram duas falhas e quatro excecoes antes das correcoes.
- Dois testes adicionais reproduziram os separadores vazios e a omissao do prazo.
- Nove testes novos passaram no estado final.
- Quarenta e quatro testes anteriores de interface passaram novamente apos a ultima alteracao.
- Treze sequencias Qt/WebEngine passaram no estado final, com perfil isolado e dados sinteticos.
- Sintaxe Python dos arquivos alterados verificada.

## Limites

Contas e credenciais nao foram alteradas. Os testes nativos nao enviam mensagens nem executam comandos reais. Nao foi gerado novo EXE nem enviado commit.

A normalizacao cobre o contrato dos campos diretos de apresentacao e registros, nao estruturas arbitrarias profundamente aninhadas. Nao representa garantia de ausencia de bugs em todas as integracoes ou na voz real.

Permanece a ambiguidade do protocolo sem identificador unico em execucoes simultaneas da mesma ferramenta/etapa. Avisos de depreciacao de pynvml, Pillow e do cliente streamable HTTP seguem fora do escopo.
