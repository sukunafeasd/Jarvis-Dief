# Protocolo ULTRON Local

O planeta do laboratorio foi integrado ao cenario do DIEF JARVIS, com suas
texturas, lava, camadas de basalto, reator fechado e animacoes. Fica no lado
oposto ao sistema solar e se aproxima quando o protocolo e ativado.
As informacoes sao projetadas sem cards nem botoes, por trechos do audio
reproduzido pelo proprio Jarvis. Nao existe uma segunda IA ou voz independente.

## Comandos

- `Jarvis, ativar protocolo ultron`: inicia o diagnostico local somente leitura.
- `status`: apresenta dados reais disponiveis de recursos e protecao.
- `monitorar`: acompanha recursos; alertas nao interrompem fala ou confirmacao.
- `consultar cofre`: lista copias reais. `crie um backup da pasta CAMINHO` prepara uma copia.
- `recuperar na area de trabalho`: prepara recuperacao em uma nova pasta.
- `simular falha`, `simular disco`, `simular recuperacao`: testes isolados, sem provocar pane real.
- `limpeza segura`: somente temporarios antigos elegiveis, com copia de recuperacao.
- `seguranca maxima`, `varredura completa`, `verificar integridade profunda`, `reparar windows`: operacoes fixas do Windows com permissao real e confirmacao especifica.
- `sim`: confirma apenas a pergunta vigente no turno imediatamente seguinte.
- `nao` ou `cancelar`: descarta a pergunta pendente; nao cancela comandos ja aceitos pelo Windows.
- `desativar protocolo ultron`: encerra acompanhamento e restaura o holograma e as previas.

Pedidos e confirmacoes usam o texto real final do usuario e um serial monotono.
Transcricoes parciais e pedidos substituidos nao autorizam operacoes. O cofre
fica em `%LOCALAPPDATA%/DIEF-JARVIS/ultron`, sem alterar contas ou credenciais.
O protocolo nao desativa protecoes do Windows, nao aceita shell arbitrario
e nao promete ausencia de malware ou recuperacao garantida.

## Validacao

`tests/test_ultron_integration.py` verifica ferramentas, limites e confirmacoes
com operacoes Windows simuladas. `tests/test_ultron_host_contract.py` cobre
transcricao final, projecao e alertas. `tools/validate_ultron_scene.py` verifica
desktop/mobile; `tools/validate_ultron_native.py` verifica a ponte Qt/WebEngine
com perfil descartavel e dados sinteticos, sem contas ou chamadas de voz pagas.

Integracao somente local. Nenhum release ou novo EXE foi publicado.
