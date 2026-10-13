# Distribuicao oficial 1.0

## Arquitetura

O EXE inicial inclui Python/Tk e o verificador criptografico. Ele nao depende
de Qt, do Python do sistema ou de contas conectadas para mostrar a preparacao.
Depois baixa o aplicativo e o runtime do release estavel assinado. O runtime
cria um ambiente virtual separado e o reparador instala requisitos do pacote
usando exclusivamente o indice PyPI oficial. O painel Qt permanece no processo
Python privado, preservando as ferramentas que executam modulos Python.

Os pacotes nao incluem dados pessoais. Config e memory sao pastas locais
compartilhadas entre versoes. Fontes auxiliares desses diretorios sao guardadas
em cada versao para restauracao; os arquivos de contas e memoria nunca sao
sobrescritos pelo atualizador.

## Publicar

1. Altere VERSION.json, core/release_identity.py e CHANGELOG.md.
2. Execute testes de distribuicao, interface e verificacao inicial.
3. Exporte uma copia publica com tools/prepare_public_release.py.
4. Use tools/build_release.py --public CLONE --output SAIDA
   --signing-key CHAVE_FORA_DO_REPOSITORIO. O runtime deve ser Python 3.12 x64.
5. Confira o EXE e os pacotes num diretorio isolado.
6. Publique os fontes e use tools/github_release.py publish --artifacts SAIDA.

A chave privada nunca e incluida no codigo nem nos artefatos. A chave publica
fica fixada no EXE. Trocar a chave requer uma migracao de confianca planejada;
nao gere uma chave nova para cada release. SHA256SUMS.txt e publico.

O canal usa tags vMAJOR.MINOR.PATCH. Commits soltos na main nao atualizam
usuarios; somente releases completos, estaveis e assinados fazem isso.
Nao altere o conteudo de um release publicado: publique um numero novo.

## Recuperacao e limites

Falhas de rede usam a instalacao existente. Falhas de dependencias ou da
abertura mantem a versao anterior. A ausencia de credenciais aparece como
configuracao pendente, nao como conexao confirmada.

Primeira instalacao e reparacao de pacotes ausentes precisam de internet.
Nao e possivel instalar hardware, autorizar contas ou contornar uma politica
corporativa de Windows por este fluxo. O UAC do Windows continua obrigatorio.
O EXE 1.0 nao possui assinatura Authenticode.

Os pacotes Windows usam requirements-win.lock com versoes e hashes do PyPI,
gerados do ambiente limpo validado. A integridade e conferida pelos RECORDs.
A transacao tem um registro persistente, recuperado apos interrupcao abrupta.
O novo EXE e verificado e substituido somente depois de uma sessao bem-sucedida.
O teste de distribuicao exige o binario exato, abre main.py, aguarda o nucleo
renderizar e registra o resultado e os hashes. O repositorio anterior so pode
ser removido depois de conferir este registro e os tres pacotes publicados.
