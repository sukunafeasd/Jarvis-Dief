# DIEF JARVIS

Assistente de desktop em português brasileiro desenvolvido pela Equipe Dief.

## Abrir

Na distribuicao oficial 1.0, baixe **DIEF-JARVIS-Setup.exe** em https://github.com/sukunafeasd/Jarvis-Dief/releases/latest. Ele prepara o Python privado e as dependencias, instala o aplicativo e cria o atalho **DIEF JARVIS**. Nao e necessario instalar Python manualmente. A primeira preparacao exige internet.

O atalho anterior de desenvolvimento continua abrindo os fontes locais. Ele nao se transforma automaticamente no novo instalador. Contas existentes nesse projeto nao sao publicadas nem copiadas para uma instalacao limpa.

O acesso de administrador continua obrigatório. Quando iniciado sem elevação, aparece a tela galáctica do Jarvis; o botão de reinício abre a confirmação oficial do Windows. Cancelar essa confirmação não inicia o assistente nem libera acesso às contas.

## Identidade

- Estrela de cinco pontas: configurações.
- Interface espacial e configuracoes em portugues brasileiro.
- Nome do aplicativo: DIEF JARVIS.
- Ícone original do painel: `config/dief-jarvis.ico`, com tamanhos de 16 a 256 pixels.

Textos de interface, painel remoto e diversas mensagens de operação foram traduzidos. Identificadores de funções, nomes de ferramentas, seletores, propriedades JSON, comandos, fornecedores, bibliotecas e códigos de erro permanecem nos formatos exigidos pelos sistemas. Traduzir esses contratos quebraria as conexões.

## Contas

Conecte as contas em Configurações > Conexões. O Gmail usa autorização Google somente leitura, não a chave de API da IA. O WhatsApp usa a sessão vinculada pelo código QR. Nem todo aplicativo permite operação invisível; ações precisam de controles reais e verificação do resultado.

## Desenvolvimento

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests
.venv\Scripts\python.exe tools\refresh_branding.py --shortcut
```

As alterações no código são carregadas após reiniciar o Jarvis. Não compartilhe arquivos de credenciais, tokens ou sessões de navegador.
