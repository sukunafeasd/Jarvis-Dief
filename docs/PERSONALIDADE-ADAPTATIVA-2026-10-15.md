# Personalidade adaptativa do JARVIS

Implementacao local autorizada pela descricao do usuario. Sem publicacao.

## Identidade

Base estavel: inteligencia com iniciativa, conversa natural, humor seco discreto,
lealdade com senso critico e familiaridade progressiva. Avaliacoes devem ter
fundamento; lembrancas e projetos so podem ser mencionados com contexto real.
Iniciativa muda o jeito de sugerir, nunca as permissoes de executar acoes.

## Adaptacao

Quatro dimensoes de estilo: familiaridade, humor, iniciativa e detalhamento.
Nao representam sentimentos nem uma medida psicologica da pessoa.

O host aprende com falas humanas finais reconhecidas e mensagens digitadas,
sem uma segunda chamada de IA por frase. Correcoes claras recebem prioridade.
Sinais casuais geram pequenos ajustes espacados; preferencias explicitas ficam
protegidas de inferencias posteriores. Pedidos temporarios nao viram preferencias
permanentes. O modelo pode registrar inferencias limitadas com personality_control,
citando uma evidencia da fala humana atual. Nao pode substituir a identidade,
escrever regras livres ou escolher valores arbitrarios.

## Persistencia

Na pasta pessoal memory, separada da chave da API:

- long_term.json: fatos duraveis existentes, com migracao preservando a copia antiga.
- personality.json: dimensoes, origem, tratamento e ultimos ajustes; sem dialogos brutos.
- conversations.sqlite3: falas e respostas textuais, com credenciais identificaveis omitidas.

A troca da chave ou reconexao monta novamente as instrucoes com o mesmo perfil,
fatos e trechos recentes. memory_control history/read consulta conversas antigas.
Historico e dados de contexto, nao autoriza repetir acoes nem comprova resultados
descritos pelo assistente. Contexto enviado ao modelo e limitado para evitar
reenviar todo o arquivo a cada sessao.

Leitura invalida nao apaga o arquivo nem e anunciada como memoria vazia. Escritas
de perfil sao atomicas; o historico usa transacoes SQLite. O backup local inclui
os tres registros, sem chaves de API. A recuperacao continua numa pasta separada.

## Interface

Perfil nas configuracoes: indicadores somente de leitura, duas colunas em janelas
largas, uma em areas menores, acabamento do tema aprovado. Mostra origem inicial,
aprendida ou explicita e ultimo ajuste. Nenhum slider, editor ou botao de reset.

## Limites

Nao identifica automaticamente pessoas diferentes pela voz. O estado pertence ao
perfil local deste usuario do Windows. O modelo em uso influencia a qualidade
das falas, mas as preferencias e lembrancas locais nao pertencem ao provedor.
O recurso nao reescreve ferramentas de seguranca ou mensagens operacionais fixas.

## Validacao

- 120 testes automatizados: personalidade, interface, memoria, backups,
  configuracoes, comandos e reproducao Fish com audio sintetico.
- Perfil visual conferido em 850, 600 e 390 pixels; somente leitura, sem
  sliders, campos ou botoes. Configuracoes completas tambem exercitadas em
  1920, 1366 e 800 pixels.
- Duas instancias concorrentes preservam preferencias; duas chaves ficticias
  diferentes recuperam o mesmo perfil, fatos e contexto.
- Regressao para citacoes, hipoteses, negacao, correcoes na mesma fala,
  eventos invalidos e ocultacao de credenciais em JSON/frases corridas.
- Memoria pessoal existente migrada para AppData sem apagar a copia antiga.

Nenhuma API real foi chamada para avaliar a qualidade das novas respostas.
A naturalidade em conversa falada precisa ser avaliada no uso real; nao e
garantida somente por testes de armazenamento, instrucoes e interface.
Nenhuma versao ou alteracao foi publicada no GitHub.
