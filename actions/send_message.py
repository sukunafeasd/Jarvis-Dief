import json
import subprocess
import sys
import time
from pathlib import Path

try:
    import pyautogui
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE    = 0.06
    _PYAUTOGUI = True
except ImportError:
    _PYAUTOGUI = False

try:
    import pyperclip
    _PYPERCLIP = True
except ImportError:
    _PYPERCLIP = False

def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

def _get_os() -> str:
    try:
        from memory.config_manager import load_api_keys
        cfg = load_api_keys()
        return cfg.get("os_system", "windows").lower()
    except Exception:
        return "windows"


def _require_pyautogui():
    if not _PYAUTOGUI:
        raise RuntimeError("PyAutoGUI not installed. Run: pip install pyautogui")


def _paste_text(text: str) -> None:
    _require_pyautogui()

    os_name = _get_os()
    paste_hotkey = ("command", "v") if os_name == "mac" else ("ctrl", "v")

    if _PYPERCLIP:
        pyperclip.copy(text)
        time.sleep(0.15)
        pyautogui.hotkey(*paste_hotkey)
        time.sleep(0.1)
    else:
        pyautogui.write(text, interval=0.03)


def _clear_and_paste(text: str) -> None:
    _require_pyautogui()
    os_name = _get_os()
    select_all = ("command", "a") if os_name == "mac" else ("ctrl", "a")
    pyautogui.hotkey(*select_all)
    time.sleep(0.1)
    pyautogui.press("delete")
    time.sleep(0.1)
    _paste_text(text)

def _open_app(app_name: str) -> bool:
    _require_pyautogui()
    os_name = _get_os()

    try:
        if os_name == "windows":
            pyautogui.press("win")
            time.sleep(0.5)
            _paste_text(app_name)
            time.sleep(0.6)
            pyautogui.press("enter")
            time.sleep(2.5)
            return True

        elif os_name == "mac":
            result = subprocess.run(
                ["open", "-a", app_name],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode != 0:
                result = subprocess.run(
                    ["open", "-a", f"{app_name}.app"],
                    capture_output=True, text=True, timeout=10,
                )
            time.sleep(2.5)
            return result.returncode == 0

        else: 
            launched = False
            for launcher in [
                ["gtk-launch", app_name.lower()],
                [app_name.lower()],
            ]:
                try:
                    subprocess.Popen(
                        launcher,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    launched = True
                    break
                except FileNotFoundError:
                    continue
            time.sleep(2.5)
            return launched

    except Exception as e:
        print(f"[SendMessage] ⚠️ Could not open {app_name}: {e}")
        return False


def _open_browser_url(url: str) -> bool:
    import webbrowser
    try:
        webbrowser.open(url)
        time.sleep(4.0) 
        return True
    except Exception as e:
        print(f"[SendMessage] ⚠️ Could not open browser: {e}")
        return False

def _search_in_app(query: str) -> None:
    _require_pyautogui()
    os_name = _get_os()
    search_hotkey = ("command", "f") if os_name == "mac" else ("ctrl", "f")

    pyautogui.hotkey(*search_hotkey)
    time.sleep(0.5)
    _clear_and_paste(query)
    time.sleep(1.0)

def _desktop_send(app_name: str, receiver: str, message: str) -> str:
    if not _open_app(app_name):
        return f"Could not open {app_name}."

    time.sleep(1.0)
    _search_in_app(receiver)
    pyautogui.press("enter")
    time.sleep(0.8)

    _paste_text(message)
    time.sleep(0.2)
    pyautogui.press("enter")
    time.sleep(0.3)
    return f"Message sent to {receiver} via {app_name}."

def _send_whatsapp(receiver: str, message: str) -> str:
    from core.whatsapp_web import transport
    from memory.config_manager import get_plugin_enabled
    if not get_plugin_enabled("whatsapp_web"):
        return "WhatsApp Web desativado. Mensagem não enviada."
    result = transport.call("send", receiver, message)
    if result.get("ok"):
        return result["status"]
    details = result.get('error','Conexão indisponível.')
    stage = result.get('stage','connection')
    stage = {
        'connection': 'conexão', 'contact': 'busca do contato',
        'contact_results':'resultado da busca','chat_header':'abertura da conversa','chat_ready':'carregamento da conversa',
        'composer': 'campo de mensagem', 'message_verification': 'conferência do texto',
        'recipient_verification': 'conferência do destinatário',
        'send_control': 'botão Enviar', 'dispatch': 'acionamento do envio',
        'confirmation': 'confirmação na conversa', 'transport': 'sessão do navegador',
    }.get(stage, stage)
    return f"Não confirmei o envio no WhatsApp · etapa {stage}: {details}" + (' Não repita automaticamente: o resultado é incerto.' if result.get('uncertain') else ' Mensagem não confirmada.')

def _send_telegram(receiver: str, message: str) -> str:
    return _desktop_send("Telegram", receiver, message)

def _send_signal(receiver: str, message: str) -> str:
    return _desktop_send("Signal", receiver, message)


def _send_discord(receiver: str, message: str) -> str:
    return _desktop_send("Discord", receiver, message)


def _send_instagram(receiver: str, message: str) -> str:
    _require_pyautogui()

    if not _open_browser_url("https://www.instagram.com/direct/new/"):
        return "Could not open Instagram in browser."

    _paste_text(receiver)
    time.sleep(1.5)

    pyautogui.press("down")
    time.sleep(0.3)
    pyautogui.press("enter")   
    time.sleep(0.4)

    for _ in range(4):
        pyautogui.press("tab")
        time.sleep(0.15)
    pyautogui.press("enter")
    time.sleep(2.0)

    _paste_text(message)
    time.sleep(0.2)
    pyautogui.press("enter")
    time.sleep(0.3)

    return f"Message sent to {receiver} via Instagram."


def _send_messenger(receiver: str, message: str) -> str:
    _require_pyautogui()

    if not _open_browser_url("https://www.messenger.com/"):
        return "Could not open Messenger in browser."


    _search_in_app(receiver)
    time.sleep(0.5)
    pyautogui.press("down")
    time.sleep(0.3)
    pyautogui.press("enter")
    time.sleep(1.0)

    _paste_text(message)
    time.sleep(0.2)
    pyautogui.press("enter")
    time.sleep(0.3)

    return f"Message sent to {receiver} via Messenger."

_PLATFORM_MAP = [
    ({"whatsapp", "wp", "wapp"},              _send_whatsapp),
    ({"telegram", "tg"},                      _send_telegram),
    ({"instagram", "ig", "insta"},            _send_instagram),
    ({"signal"},                               _send_signal),
    ({"discord"},                              _send_discord),
    ({"messenger", "facebook", "fb"},         _send_messenger),
]


def _resolve_platform(platform_str: str):
    key = platform_str.lower().strip()
    if key in {'whatsapp','whatsapp web','wp','wapp','wtts','wpp','wtss'}:return _send_whatsapp
    return lambda r,m:'Envio não disponível sem um transporte verificado. Nenhum clique cego realizado.'


def send_message(
    parameters: dict,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    params       = parameters or {}
    receiver     = str(params.get("receiver") or '').strip()
    message_text = str(params.get("message_text") or '').strip()
    platform     = str(params.get("platform") or 'whatsapp').strip()

    if params.get('selection') is not None:
        try:
            from core.reference_resolver import resolve_selection
            selected=resolve_selection('whatsapp',params['selection'],session_memory,player,'whatsapp_chats')
            if receiver and receiver!=selected['contact']:raise ValueError('Contato diferente da seleção solicitada.')
            receiver=selected['contact']
        except ValueError as error:return json.dumps({'ok':False,'error':str(error)},ensure_ascii=False)
    if not receiver:
        return json.dumps({'ok':False,'error':'Informe o contato exato ou uma seleção da lista consultada.'},ensure_ascii=False)
    if not message_text:
        return json.dumps({'ok':False,'error':'Informe o texto exato da mensagem.'},ensure_ascii=False)
    aliases={'whatsapp','whatsapp web','wp','wapp','wtts','wpp','wtss'}
    if platform.lower() not in aliases:
        return json.dumps({'ok':False,'error':'Esta ferramenta só possui envio verificado no WhatsApp Web. Para outro aplicativo, use seus controles reais e confira destinatário, texto e resultado. Nenhum clique cego realizado.'},ensure_ascii=False)
    from memory.config_manager import get_plugin_enabled
    from core.whatsapp_web import transport
    if not get_plugin_enabled('whatsapp_web'):
        return json.dumps({'ok':False,'stage':'connection','error':'WhatsApp Web desativado. Mensagem não enviada.'},ensure_ascii=False)
    key=None
    if session_memory is not None:
        try:key,previous=session_memory.begin_send('whatsapp',receiver,message_text)
        except ValueError as error:return json.dumps({'ok':False,'error':str(error)},ensure_ascii=False)
        if previous is not None:
            return json.dumps({**previous,'duplicate_blocked':True,'note':'Este pedido já foi processado; não acionei outro envio.'},ensure_ascii=False)

    print('[SendMessage] Requesting linked WhatsApp transport')
    if player:
        player.write_log(f"[msg] {platform} → {receiver}")

    try:
        result=transport.call('send',receiver,message_text)
        if not isinstance(result,dict):result={'ok':False,'uncertain':True,'stage':'transport','error':'O transporte não retornou uma confirmação válida.'}
    except Exception as e:
        result={'ok':False,'uncertain':True,'stage':'transport','error':f'Não confirmei o envio ({type(e).__name__}). Confira a conversa antes de repetir.'}
    if key is not None:session_memory.finish_send(key,result)

    # "NOT sent" contains "sent". The old test read that as a success and put a
    # tick next to a message that never went.
    ok=result.get('ok') is True
    print('[SendMessage] '+('Confirmed in conversation' if ok else 'Not confirmed'))
    if player:
        player.write_log('[msg] '+(result.get('status','Mensagem confirmada na conversa; entrega não confirmada.') if ok else 'Não confirmei o envio · '+result.get('stage','transport')+': '+result.get('error','Confira a conversa.')))

    return json.dumps(result,ensure_ascii=False)


# ── Tool declaration (auto-discovered by core/action_loader.py) ──────────────
TOOL = {
    "name": "send_message",
    "description": (
        "WhatsApp uses the user-linked WEB plugin, never Windows search. Requires connection/QR first. "
        "Check recipient and send result. Browser acceptance is not delivery/read confirmation. "
        "If result is uncertain, DO NOT retry automatically or suggest another sending method: first ask the user to check the conversation. Explain the specific failed stage instead of a generic connection problem. "
        "Verified sending ONLY via the linked WhatsApp Web session. Other platforms are refused rather than clicked blindly. selection may choose the actual contact from the last unread list. Repeated identical send calls in the same user request are deduplicated, including uncertain results. Write 'message_text' in the USER'S OWN LANGUAGE, exactly "
        "what they asked to be said. If the result says the message was NOT "
        "sent, repeat that plainly along with the reason it gives — never "
        "tell the user a message was sent unless the result said it was."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "receiver": {
                "type": "STRING",
                "description": "Recipient contact name"
            },
            "message_text": {
                "type": "STRING",
                "description": "The message to send"
            },
            "platform": {
                "type": "STRING",
                "description": "WhatsApp or WhatsApp Web. Other platforms require their own verified app controls."
            },
            'selection':{'type':'INTEGER','description':'1-based contact in the last WhatsApp unread page; use only when this is the contact the user selected.'}
        },
        "required": [
            "message_text",
            "platform"
        ]
    },
    "handler": send_message,
}
