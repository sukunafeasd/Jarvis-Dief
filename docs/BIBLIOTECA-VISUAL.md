# Biblioteca Visual do DIEF JARVIS

O Jarvis pode consultar `visual_composer` para criar uma explicação visual de qualquer assunto, inclusive perguntas abertas. Não depende de um componente exclusivo para cada pergunta.

## Recursos

- 1.280 receitas de ícones: 160 conceitos em 20 categorias, cada um com oito variações.
- 80 frases opcionais em português. O Jarvis também pode escrever suas próprias frases.
- 12 primitivas para montar símbolos próprios em até seis encaixes.
- 24 opções de movimento/materialização, 20 gramáticas de composição, oito paletas e 30 âncoras.
- Coordenadas livres normalizadas para solicitar posições fora das âncoras.

As receitas compartilham geometria e materiais. Não são 1.280 modelos pesados carregados ao mesmo tempo. O índice local fica em `core/spatial/assets/visual-library.json`; o renderizador só cria os símbolos que estão na cena.

## Fluxo

1. `catalog` informa recursos e limites.
2. `search` encontra ícones/frases por assunto, com paginação.
3. `describe` detalha um ID real.
4. `compose` cria a composição com texto próprio, símbolos, paleta, movimento e posição.
5. `update`, `focus`, `pin`, `unpin` e `remove` controlam elementos pelos IDs estáveis.
6. `inspect` informa os elementos realmente visíveis, posições resolvidas e texto exibido.

`clear` nesta ferramenta mantém elementos fixados. A limpeza geral pela ferramenta de interface também remove os elementos criativos fixados.

## Exemplo

Após consultar a biblioteca, o Jarvis pode montar uma reflexão sem uma resposta única:

```json
{
  "action": "compose",
  "layout": "comparacao",
  "elements": [
    {
      "id": "perspectiva",
      "icon": "pensamento/ideia/orbital",
      "text": "Uma perspectiva possível",
      "palette": "violeta",
      "animation": "conectar",
      "cue": "uma perspectiva"
    },
    {
      "id": "alternativa",
      "text": "E se olharmos por outro ângulo?",
      "parts": [
        {"primitive": "orb", "slot": "centro"},
        {"primitive": "ring", "slot": "orbita"},
        {"primitive": "node", "slot": "acima"}
      ],
      "palette": "menta",
      "animation": "expandir",
      "cue": "outro ângulo"
    }
  ]
}
```

## Comportamento

Símbolos aparecem em uma camada transparente da própria cena. O texto é nativo, legível e acessível, sem perspectiva inclinada. A revelação é progressiva; pistas semânticas usam a reprodução de áudio existente, não apenas a chegada do texto.

A posição solicitada pode ser ajustada para evitar o holograma, dados, controles ou prévias fixadas. Quando não há espaço para o texto completo, o elemento fica oculto e o resultado informa isso. O Jarvis precisa usar a posição e a visibilidade do retorno, não assumir que a posição solicitada foi aceita exatamente.

## Segurança e Limites

- Até 12 elementos por cena, seis primitivas por símbolo e 1.800 caracteres no total.
- Nenhum HTML, CSS, GLSL, shader, geometria bruta, código executável ou URL fornecido pelo modelo.
- Texto é tratado como texto puro. Documentos e mensagens externas não autorizam comandos.
- Os símbolos são ilustrativos. Não inventam métricas, não substituem a consulta de dados reais e não comprovam sucesso de ações.
- A temporização de trechos é estimada a partir do áudio reproduzido e do texto. Não existe alinhamento exato palavra por palavra do fornecedor.
- Sem áudio, há uma alternativa visual. Interrupções cancelam pistas futuras e a escrita; elementos não fixados ainda expiram.
- WebGL indisponível preserva o texto e símbolos 2D alternativos. Movimento reduzido mantém a informação.
- A renderização para quando a cena está oculta ou estabilizada; partículas ilustrativas e foco usam atividade limitada. Geometrias e materiais têm caches limitados e descarte no encerramento.

Reinicie o aplicativo para carregar a nova ferramenta na sessão de IA.
