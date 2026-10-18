# Desenvolvimento Local

Esta copia parte da tag oficial v1.0.0. As correcoes da abertura e o novo
icone permanecem somente no computador, sem publicar outra versao.

O atalho DIEF JARVIS usa o executavel local assinado pela Equipe Dief.
Esse iniciador executa main.py desta pasta e nao baixa codigo para
substituir as alteracoes em desenvolvimento.

As contas, memoria, bancos e sessoes foram copiados da instalacao anterior.
Um backup separado foi mantido antes da migracao. Esses arquivos sao
ignorados pelo Git e nao devem ser adicionados ao repositorio.

O ambiente .venv reutiliza a pasta do projeto anterior por uma juncao
Windows. Nao apague a pasta anterior enquanto esse ambiente estiver em uso.
O endereco de envio do Git desta copia foi desativado para evitar publicar
acidentalmente as alteracoes locais.

Para validar sem usar contas pessoais:

```powershell
.\.venv\Scripts\python.exe tools\validate_local_opening.py
.\.venv\Scripts\python.exe tools\validate_local_opening.py --setup
.\.venv\Scripts\python.exe tools\validate_local_opening.py --width 1200 --height 800 --resize
```
