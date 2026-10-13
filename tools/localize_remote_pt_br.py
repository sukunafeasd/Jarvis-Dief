"""Traduz somente textos de apresentacao conhecidos, preservando o protocolo."""
from pathlib import Path

TEXT={
    '<html lang="en">':'<html lang="pt-BR">', '<title>JARVIS</title>':'<title>DIEF JARVIS</title>',
    '<em>J</em>ARVIS':'<em>D</em>IEF JARVIS',
    '>Remote Access<':'>Acesso remoto<', '>Reconnecting…<':'>Reconectando…<',
    'Press <strong style="color:var(--text)">Remote Control</strong> in the JARVIS desktop app to get a QR code or session key.':'Abra <strong style="color:var(--text)">Acesso remoto</strong> no DIEF JARVIS para obter um código QR ou uma chave de sessão.',
    '>CONNECT<':'>CONECTAR<', '>Connecting<':'>Conectando<',
    'Send a command to JARVIS…':'Envie um comando ao DIEF JARVIS…', 'title="Send file"':'title="Enviar arquivo"',
    'title="Voice command"':'title="Comando de voz"', '>WAKE<':'>ATIVAR<', '>SEND<':'>ENVIAR<',
    "'NO ENC'":"'SEM CRIPTOGRAFIA'", "'Remote session active.'":"'Sessão remota ativa.'",
    "'Connected to JARVIS'":"'Conectado ao DIEF JARVIS'", "'Connection lost — refresh to reconnect.'":"'Conexão perdida. Atualize a página para reconectar.'",
    "'Connection error.'":"'Erro de conexão.'", "'Connection error'":"'Erro de conexão'",
    "'Invalid or expired key'":"'Chave inválida ou expirada'",
    "'Wake word detected — connecting…'":"'Chamada detectada. Conectando…'",
    "stTxt.textContent = 'Active'":"stTxt.textContent = 'Ativo'", "stTxt.textContent = 'Sleeping'":"stTxt.textContent = 'Em repouso'",
    '>You<':'>Você<', '>Sending<':'>Enviando<', "lbl.textContent = 'Sent'":"lbl.textContent = 'Enviado'",
    '>⬇ Download back<':'>⬇ Baixar cópia<', "'File sent!'":"'Arquivo enviado!'", "'Upload failed'":"'Falha ao enviar arquivo'",
    '>Received<':'>Recebido<', '>⬇ Download<':'>⬇ Baixar<', "'File received on computer!'":"'Arquivo recebido no computador!'",
    "'Sending wake signal…'":"'Enviando sinal de ativação…'", "'Voice — tap to speak'":"'Voz: toque para falar'",
    '🎤 One-time voice setup':'🎤 Configuração inicial da voz',
    'Open a new tab → go to':'Abra uma nova aba e acesse',
    '<li>Search:':'<li>Pesquise:', 'Paste this URL into the box:':'Cole este endereço no campo:',
    '<li>Set to <strong':'<li>Selecione <strong', ' → tap <strong':' e toque em <strong',
    '<li>Return here and tap 🎤</li>':'<li>Volte aqui e toque em 🎤</li>',
    "'URL copied!'":"'Endereço copiado!'", "'Microphone denied — tap the address bar lock and allow microphone.'":"'Microfone bloqueado. Abra as permissões do site e permita o microfone.'",
    "'Mic error: '":"'Erro do microfone: '", "'Tap to stop'":"'Toque para parar'",
    "'Voice live — speak now'":"'Microfone ativo. Pode falar.'", "'🎤 Live'":"'🎤 Ao vivo'",
    "'Voice connection failed.'":"'Falha na conexão de voz.'",
    '🎤 <strong style="color:var(--text)">Voice commands:</strong> open':'🎤 <strong style="color:var(--text)">Comandos de voz:</strong> abra',
    'on your phone, search':'no celular e pesquise',
    ', add your JARVIS URL, tap Relaunch.':', adicione o endereço do DIEF JARVIS e toque em Relaunch (reiniciar).',
}


def migrate(path):
    source=path.read_text(encoding='utf-8');result=source
    for original,translated in TEXT.items():result=result.replace(original,translated)
    if result!=source:path.write_text(result,encoding='utf-8')
    return result!=source


if __name__=='__main__':
    root=Path(__file__).resolve().parent.parent
    for name in ('dashboard/static/login.html','dashboard/static/app.html'):
        print(name,migrate(root/name))
