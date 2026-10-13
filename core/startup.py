"""Pre-import bootstrap: declared packages only, then observable readiness checks."""
import importlib.metadata
import json
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]


def visual_motion_reduced():
    root=Path(sys.executable).parent if getattr(sys,'frozen',False) else BASE
    try:
        config=json.loads((root/'config/api_keys.json').read_text(encoding='utf-8'))
        return isinstance(config,dict) and bool(config.get('reduce_motion',False))
    except (OSError,ValueError):return False


def missing_dependencies():
    from pip._vendor.packaging.requirements import Requirement
    missing = []
    for line in (BASE / 'requirements.txt').read_text(encoding='utf-8').splitlines():
        text = line.split('#', 1)[0].strip()
        if not text:
            continue
        requirement = Requirement(text)
        if requirement.url:
            raise ValueError('Dependencia externa por URL nao autorizada no bootstrap.')
        if requirement.marker and not requirement.marker.evaluate():
            continue
        try:
            installed=importlib.metadata.version(requirement.name)
            if requirement.specifier and installed not in requirement.specifier:
                missing.append(str(requirement))
        except importlib.metadata.PackageNotFoundError:
            missing.append(str(requirement))
    return missing


def check_startup(progress, stop, install=True):
    progress('Dependências', 'Verificando ambiente Python', 'working')
    missing = missing_dependencies()
    if missing:
        if not install or getattr(sys, 'frozen', False) or sys.prefix == sys.base_prefix:
            progress('Dependências', 'Ambiente incompleto; reparação necessária', 'error')
            return False
        progress('Dependências', f'Instalando {len(missing)} pacotes ausentes', 'working')
        process = subprocess.Popen(
            [sys.executable, '-m', 'pip', '--isolated', 'install', '--no-input',
             '--disable-pip-version-check', '--index-url', 'https://pypi.org/simple', *missing],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
        )
        for _ in range(1800):
            if process.poll() is not None:
                break
            if stop.wait(.5):
                process.terminate(); process.wait(timeout=10)
                return False
        else:
            process.terminate(); process.wait(timeout=10)
            progress('Dependências', 'Tempo de instalação esgotado', 'error')
            return False
        importlib.invalidate_caches()
        if process.returncode or missing_dependencies():
            progress('Dependências', 'Instalação não concluída; verifique a internet', 'error')
            return False
    progress('Dependências', 'Pacotes declarados disponíveis', 'ok')
    assets = ('core/face_model.obj', 'core/prompt.txt', 'core/spatial/viewer.mjs',
              'core/spatial/presentation.html')
    absent = [path for path in assets if not (BASE / path).is_file()]
    progress('Arquivos', 'Arquivos essenciais disponíveis' if not absent else 'Arquivos essenciais ausentes', 'ok' if not absent else 'error')
    if absent or stop.is_set():
        return False
    for name in ('config', 'memory'):
        (BASE / name).mkdir(exist_ok=True)
    from core.factory_defaults import initialize
    initialize(BASE)
    try:
        import sounddevice
        devices = sounddevice.query_devices()
        mic = any(d['max_input_channels'] for d in devices)
        output = any(d['max_output_channels'] for d in devices)
        progress('Áudio', 'Entrada e saída detectadas' if mic and output else 'Dispositivo de áudio indisponível', 'ok' if mic and output else 'warning')
    except Exception:
        progress('Áudio', 'Não foi possível verificar os dispositivos', 'warning')
    try:
        config = json.loads((BASE / 'config/api_keys.json').read_text(encoding='utf-8'))
        configured = bool(config.get('gemini_api_key'))
    except (OSError, ValueError):
        configured = False
    progress('IA', 'Credencial salva; conexão será validada no painel' if configured else 'Configuração da IA pendente', 'pending')
    from core import gmail_connection as gmail
    if gmail.status()['connected']:
        progress('Gmail', 'Testando autorização com o Google', 'working')
        try:
            verified, _ = gmail.verify()
            progress('Gmail', 'Autorização confirmada · somente leitura' if verified else 'Conta requer verificação', 'ok' if verified else 'warning')
        except Exception:
            progress('Gmail', 'Serviço indisponível; autorização preservada', 'warning')
    else:
        progress('Gmail', 'Conta não conectada', 'pending')
    if stop.is_set():
        return False
    from core.whatsapp_web import PROFILE, transport
    if PROFILE.exists():
        progress('WhatsApp', 'Restaurando sessão em segundo plano', 'working')
        result = transport.call('status')
        connected = result.get('connected', False)
        progress('WhatsApp', 'Sessão confirmada' if connected else 'Sessão requer verificação', 'ok' if connected else 'warning')
    else:
        progress('WhatsApp', 'Conta não conectada', 'pending')
    return not stop.is_set()


def bootstrap():
    import tkinter as tk
    root = tk.Tk(); root.title('DIEF JARVIS · Inicialização')
    from core.app_identity import brand_tk_window
    brand_tk_window(root)
    root.overrideredirect(True)
    root.configure(bg='#050d12'); root.resizable(False, False)
    width, height = 660, 440
    root.geometry(f'{width}x{height}+{max(0,(root.winfo_screenwidth()-width)//2)}+{max(0,(root.winfo_screenheight()-height)//2)}')
    from core.fui_bootstrap import BootstrapSurface
    surface=BootstrapSurface(root,width,height,reduced=visual_motion_reduced())
    canvas=surface.canvas;notice=surface.notice
    events = queue.Queue(); stop = threading.Event(); result = {'ready':False}
    started=time.monotonic();closed=False;done=False;after_id=None
    def worker():
        try:
            ok = check_startup(lambda *entry:events.put(entry), stop)
        except Exception as error:
            events.put(('Dependências',f'Inicialização interrompida ({type(error).__name__})','error'))
            ok = False
        events.put(('_done',ok,''))
    def close():
        nonlocal closed
        if closed:return
        closed=True
        if after_id is not None:root.after_cancel(after_id)
        stop.set(); root.destroy()
    canvas.tag_bind('close','<Button-1>',lambda event:close())
    root.bind('<Escape>',lambda event:close())
    root.protocol('WM_DELETE_WINDOW',close)
    def tick():
        nonlocal done,after_id
        if closed:return
        if not surface.motion_reduced and root.state()!='iconic' and root.winfo_ismapped():surface.animate(time.monotonic()-started)
        while not events.empty():
            name,text,state = events.get_nowait()
            if name == '_done':
                result['ready'] = text
                done=True
                notice.configure(text='Ambiente verificado · abrindo holograma' if text else 'Não foi possível iniciar. Feche e tente novamente.',fg='#dce8ed' if text else '#e8a67e')
                if text:
                    root.after(600,close)
                continue
            if not done:surface.update_status(name,text,state)
        after_id=root.after(60,tick)
    threading.Thread(target=worker,daemon=True,name='JarvisPreflight').start()
    tick(); root.mainloop()
    return result['ready']
