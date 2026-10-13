# DIEF JARVIS 1.0

Assistente desktop em portugues para Windows 10/11 x64, com interface espacial,
nucleo holografico, voz, memoria local e integracoes configuradas pelo usuario.

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

O instalador nao possui certificado Authenticode: o Windows pode mostrar
aviso de editor desconhecido. Manifestos de atualizacao sao assinados com
Ed25519 e os pacotes sao conferidos por SHA-256; isso nao substitui Authenticode.

## Atualizar

Abra pelo atalho DIEF JARVIS. A verificacao inicial consulta somente releases
estaveis do repositorio oficial. Uma versao mais recente e preparada antes de
abrir o aplicativo. Falha de rede mantem a versao instalada; falha de abertura
preserva a anterior. Contas e memoria nao fazem parte dos pacotes de release.
Uma atualizacao rejeitada nao e repetida a cada abertura.
O EXE inicial tambem e atualizado; sua substituicao ocorre ao encerrar uma
sessao bem-sucedida, quando o Windows libera o arquivo em uso.

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

## Creditos

Adaptacao de [MARK LV, de FatihMakes](https://github.com/FatihMakes/Mark-LV),
com modificacoes para DIEF JARVIS. A licenca original **CC BY-NC 4.0** e os
creditos permanecem em `LICENSE` e `NOTICE.md`. Uso comercial nao permitido.
Bibliotecas de terceiros mantem suas proprias licencas.
