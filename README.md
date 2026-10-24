# DIEF JARVIS 2.1

Assistente desktop em portugues para Windows 10/11 x64, com interface espacial,
nucleo holografico, voz, memoria local e integracoes configuradas pelo usuario.

## Atualizacao 2.1: reparos e estabilidade

A versao 2.1.0 reune as correcoes posteriores a 2.0 em voz, noticias,
contexto, comandos, conexoes e atualizacao Windows. E uma atualizacao de
manutencao, preservando os modos existentes e os dados locais.
Veja o [historico de alteracoes](CHANGELOG.md).

## Recursos existentes

- Modo Espectro: holograma no desktop, observacao da janela ativa, notas,
  marca-texto, setas, cores e desenhos temporarios. Diga "pare de observar"
  para pausar a observacao; "volte a observar" retoma.
- Modo Forja: criacao de projetos com Codex, conta propria, previa e biblioteca.
  Requer Codex instalado e autenticacao individual em Configuracoes > Conexoes.
- Protocolo Ultron: diagnostico, monitoramento e recuperacao controlada.
- Forma Neural: consulta de memorias com fontes e transicao holografica.
- Personalidade adaptativa, contexto de tarefas e acompanhamento de etapas.
- Novos temas, icones, planetas, configuracoes e informacoes fixadas atualizaveis.
- Correcoes de voz, interrupcao, transicoes, conexoes e resumo diario.

A observacao usa controles acessiveis da janela em primeiro plano, nao video
continuo. Janelas sensiveis sao suspensas. Marcacoes nao executam cliques.
Servicos opcionais precisam da conta/chave do proprio usuario; nenhuma chave
Fish Audio ou conta ChatGPT acompanha o instalador.

## Instalar

Baixe **DIEF-JARVIS-Setup.exe** em
[Releases](https://github.com/sukunafeasd/Jarvis-Dief/releases/latest).
Abra o EXE e confirme a solicitacao de administrador do Windows. A tela inicial
consulta atualizacoes, prepara o Python privado, instala os pacotes declarados
e verifica arquivos, audio e conexoes antes de abrir o painel.
A primeira preparacao precisa de internet e pode demorar alguns minutos.
Nao e necessario instalar Python manualmente.

O programa cria um atalho DIEF JARVIS e organiza a instalacao em
`%LOCALAPPDATA%\DIEF JARVIS`:

| Pasta | Conteudo |
| --- | --- |
| `versions` | Versoes do aplicativo |
| `runtime` | Python privado |
| `environment` | Dependencias isoladas |
| `data/config` | Configuracoes e autorizacoes pessoais |
| `data/memory` | Memoria, dados e fixados locais |
| `logs` | Registros para diagnostico |

O instalador usa por padrao o certificado local autoassinado **Equipe Dief**.
Outros computadores podem mostrar aviso de editor desconhecido; a assinatura
nao e um certificado publico nem uma garantia de reputacao no Windows.
Manifestos de atualizacao usam Ed25519 e os pacotes sao conferidos por SHA-256.

## Atualizar

Abra pelo atalho DIEF JARVIS. A verificacao inicial consulta somente releases
estaveis do repositorio oficial. A partir desta versao, uma atualizacao
disponivel pode ser instalada pela tela inicial; o aplicativo tambem verifica
novidades durante o uso. Falha de rede mantem a versao instalada; falha de abertura
preserva a anterior. Contas e memoria nao fazem parte dos pacotes de release.
Uma atualizacao rejeitada nao e repetida a cada abertura.
O EXE inicial tambem e atualizado; sua substituicao ocorre ao encerrar uma
sessao bem-sucedida, quando o Windows libera o arquivo em uso.

Usuarios da 1.0 e 2.0 usam o mesmo canal de atualizacao. Se uma instalacao
antiga nao conseguir atualizar, baixe o novo DIEF-JARVIS-Setup.exe no link
acima e execute-o no mesmo usuario do Windows. Nao apague a pasta de dados.

## Conectar

Configure sua propria IA na primeira entrada. Gmail, Agenda, Drive, WhatsApp,
Spotify e outros servicos exigem suas autorizacoes e, quando aplicavel,
credenciais do provedor. Nenhuma conta ja conectada acompanha a distribuicao.
Microfone, alto-falantes e acesso aos servicos externos dependem do computador
e da disponibilidade desses servicos.

## Desenvolver

Com Python 3.12, execute `python launch.py` para preparar o ambiente local.
O fluxo de codigo-fonte nao faz instalacao do runtime oficial nem atualiza o
clone automaticamente. Consulte `docs/DISTRIBUICAO-1.0.md` para empacotar e
publicar versoes assinadas.

## Licencas

O DIEF JARVIS e desenvolvido e mantido pela Equipe Dief. Os avisos de licenca
de bibliotecas e recursos de terceiros incorporados ao projeto permanecem nos
respectivos arquivos legais. Uso comercial depende das licencas aplicaveis.
