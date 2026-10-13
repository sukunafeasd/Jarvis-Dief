"""EXE inicial: prepara o Jarvis mesmo em Windows sem Python instalado."""
import argparse
import ctypes
import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import sys
import threading
import time
import uuid
from core.distribution import Installation, latest_release, prepare_dependencies
from core.release_identity import VERSION


def clean_child_environment():
    from core.installer_process import environment
    return environment()


def run_probe(python, application, progress, stop, env):
    from core.installer_process import spawn,close_tree
    process = spawn([str(python),'-m','core.distribution_probe'], cwd=application, env=env,
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, encoding='utf-8',
        creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    events = queue.Queue()
    def reader():
        for line in process.stdout:
            try: events.put(json.loads(line))
            except ValueError: pass
    reading=threading.Thread(target=reader, daemon=True);reading.start()
    deadline=time.monotonic()+180
    while process.poll() is None:
        if stop.wait(.1) or time.monotonic()>deadline:
            close_tree(process);reading.join(timeout=5);process.stdout.close()
            raise RuntimeError('Verificacao interrompida ou sem resposta.')
        while not events.empty():
            name,text,state=events.get_nowait()
            progress('Conexões' if name in {'Gmail','WhatsApp'} else name,text,state)
    close_tree(process)
    reading.join(timeout=5);process.stdout.close()
    while not events.empty():
        name,text,state=events.get_nowait();progress('Conexões' if name in {'Gmail','WhatsApp'} else name,text,state)
    if process.returncode: raise RuntimeError('O ambiente nao passou na verificacao. Tente novamente.')


def install_launcher(root,shortcut_folder=None):
    if not getattr(sys,'frozen',False): return
    destination=root/'DIEF JARVIS.exe'
    if Path(sys.executable).resolve()!=destination.resolve(): shutil.copy2(sys.executable,destination)
    shortcut=(Path(shortcut_folder) if shortcut_folder else root)/'DIEF JARVIS.lnk'
    if shortcut_folder:Path(shortcut_folder).mkdir(parents=True,exist_ok=True)
    # This helper receives paths as arguments; it never interpolates them as commands.
    import base64
    values=[str(shortcut),str(destination),str(root),str(root/'data/config/dief-jarvis.ico')]
    assignments=';'.join('$p'+str(i)+'=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String("'+base64.b64encode(value.encode()).decode()+'"))' for i,value in enumerate(values))
    script=assignments+';$w=New-Object -ComObject WScript.Shell;'+('' if shortcut_folder else "$p0=[IO.Path]::Combine($w.SpecialFolders('Desktop'),'DIEF JARVIS.lnk');")+' $s=$w.CreateShortcut($p0); $s.TargetPath=$p1; $s.WorkingDirectory=$p2; $s.IconLocation=$p3; $s.Save()'
    subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-EncodedCommand',base64.b64encode(script.encode('utf-16le')).decode()],
        creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),check=True,capture_output=True)


def prepare(root, progress, stop, fetch=latest_release,shortcut_folder=None):
    if os.name=='nt' and getattr(sys,'frozen',False):ctypes.windll.kernel32.SetDllDirectoryW(None)
    installation=Installation(root);state=installation.state()
    progress('Atualizações','Consultando o canal oficial de releases','working')
    try:
        release=fetch()
    except Exception:
        if not state.get('current'): raise RuntimeError('Nao foi possivel obter a versao oficial. Verifique a internet e tente novamente.')
        progress('Atualizações','Sem acesso ao canal; mantendo a versao instalada','warning')
        release=None
    if release:
        try:application=installation.install(release,progress,stop)
        except InterruptedError:raise
        except Exception:
            state=installation.state()
            if not state.get('current'):raise
            application=installation.application(state['current'])
            progress('Atualizações','Download nao concluido; mantendo a versao instalada','warning')
        progress('Atualizações','Versao '+installation.state()['current']+' disponivel neste computador','ok')
    else: application=installation.application(state['current'])
    try:
        python=installation.prepare_python(stop)
        prepare_dependencies(python,application,progress,stop)
        env=clean_child_environment();env['DIEF_MANAGED_ROOT']=str(root)
        env['PLAYWRIGHT_BROWSERS_PATH']=str(root/'browsers')
        run_probe(python,application,progress,stop,env)
    except Exception:
        if installation.state().get('pending') and installation.rollback():
            application=installation.application(installation.state()['current'])
            progress('Atualizações','Restaurando a versao anterior','warning')
            python=installation.prepare_python(stop)
            prepare_dependencies(python,application,progress,stop)
            env=clean_child_environment();env['DIEF_MANAGED_ROOT']=str(root)
            env['PLAYWRIGHT_BROWSERS_PATH']=str(root/'browsers')
            run_probe(python,application,progress,stop,env)
        else: raise
    install_launcher(root,shortcut_folder)
    return installation,python,application,env


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path)
    parser.add_argument('--prepare-only',action='store_true');parser.add_argument('--validate-artifacts',type=Path)
    args=parser.parse_args()
    if args.validate_artifacts and not args.root:raise ValueError('O teste exige uma pasta isolada explicita.')
    root=(args.root or Path(os.environ.get('LOCALAPPDATA',str(Path.home())))/'DIEF JARVIS').resolve()
    from core.elevation import require_admin
    if not require_admin(): return 0
    mutex=None
    if os.name=='nt':
        ctypes.windll.kernel32.CreateMutexW.restype=ctypes.c_void_p
        import hashlib
        mutex=ctypes.windll.kernel32.CreateMutexW(None,False,'Local\\DIEF.JARVIS.'+hashlib.sha256(str(root).casefold().encode()).hexdigest()[:16])
        if ctypes.windll.kernel32.GetLastError()==183:
            ctypes.windll.kernel32.CloseHandle(ctypes.c_void_p(mutex));return 0
    import tkinter as tk
    from core.app_identity import brand_tk_window
    from core.fui_bootstrap import BootstrapSurface
    window=tk.Tk();window.title('DIEF JARVIS '+VERSION);brand_tk_window(window)
    window.overrideredirect(True);window.geometry(f'660x440+{max(0,(window.winfo_screenwidth()-660)//2)}+{max(0,(window.winfo_screenheight()-440)//2)}')
    surface=BootstrapSurface(window,names=('Atualizações','Dependências','Arquivos','Áudio','IA','Conexões'))
    surface.canvas.create_text(628,76,text='v'+VERSION,fill='#a3f0ff',font=('Segoe UI',10),anchor='e')
    events=queue.Queue();stop=threading.Event();started=time.monotonic();result={};closed=False
    validation=None
    button=tk.Button(window,text='Tentar novamente',command=lambda:start(),bg='#233348',fg='#edfaff',relief='flat')
    def worker():
        nonlocal validation
        try:
            if args.validate_artifacts:
                from unittest.mock import patch
                from core.distribution import verified_manifest
                import hashlib
                artifacts=args.validate_artifacts.resolve()
                release=verified_manifest(json.loads((artifacts/'release.json').read_text()))
                if not getattr(sys,'frozen',False) or hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest()!=release['launcher']['sha256']:
                    raise ValueError('O teste exige executar o EXE exato deste manifesto.')
                if (root/'data/config/api_keys.json').exists():
                    saved=json.loads((root/'data/config/api_keys.json').read_text())
                    if saved.get('gemini_api_key') or saved.get('plugin_config'):raise ValueError('Teste visual nao usa contas existentes.')
                def local_download(item,target,progress,stop):
                    source=artifacts/item['name']
                    if hashlib.sha256(source.read_bytes()).hexdigest()!=item['sha256']:raise ValueError('Artefato de teste divergente.')
                    shutil.copy2(source,target)
                with patch('core.distribution.download',side_effect=local_download):
                    ready=prepare(root,lambda *entry:events.put(entry),stop,fetch=lambda:release,shortcut_folder=root/'test-desktop')
                if ready[0].state().get('application_sha256')!=release['application']['sha256']:raise ValueError('A aplicacao instalada nao corresponde ao pacote testado.')
                validation={'version':release['version'],'artifacts':{key:release[key]['sha256'] for key in ('application','runtime','launcher')},'installer_opened':True,'application_opened':False}
            else:ready=prepare(root,lambda *entry:events.put(entry),stop)
            events.put(('_ready',ready,''))
        except Exception as error:events.put(('_error',str(error),''))
    def start():
        if stop.is_set(): return
        button.place_forget();threading.Thread(target=worker,daemon=True).start()
    def close():
        nonlocal closed
        if closed:return
        closed=True;stop.set();window.destroy()
    def tick():
        if closed:return
        surface.animate(time.monotonic()-started)
        while not events.empty():
            name,text,state=events.get_nowait()
            if name=='_ready': result['ready']=text;surface.notice.configure(text='Ambiente verificado. Abrindo DIEF JARVIS.');window.after(350,close)
            elif name=='_error':
                surface.notice.configure(text=text,fg='#ffb384');button.place(x=36,y=360,width=132,height=30)
            else:surface.update_status(name,text,state)
        window.after(50,tick)
    surface.canvas.tag_bind('close','<Button-1>',lambda _:close());window.bind('<Escape>',lambda _:close())
    if args.validate_artifacts:
        def capture():
            from PIL import ImageGrab
            folder=root/'validation';folder.mkdir(parents=True,exist_ok=True)
            window.update_idletasks()
            ImageGrab.grab(bbox=(window.winfo_rootx(),window.winfo_rooty(),window.winfo_rootx()+660,window.winfo_rooty()+440)).save(folder/'installer.png')
        window.after(800,capture)
    start();tick();window.mainloop()
    if 'ready' not in result:return 1
    installation,python,application,env=result['ready']
    if args.prepare_only:return 0
    ready_file=root/'sessions'/(uuid.uuid4().hex+'.ready');ready_file.parent.mkdir(exist_ok=True)
    env['DIEF_READY_FILE']=str(ready_file);env['DIEF_PREFLIGHT_COMPLETE']='1'
    if validation:env['DIEF_VALIDATION']='1'
    log=root/'logs';log.mkdir(exist_ok=True)
    with (log/'application.log').open('ab') as stream:
        from core.installer_process import spawn,close_tree,detach_tree
        command=[str(python),str(application/'main.py')]
        process=spawn(command,cwd=application,env=env,
            stdout=stream,stderr=stream,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        deadline=time.monotonic()+120
        while process.poll() is None and not ready_file.exists() and time.monotonic()<deadline:time.sleep(.2)
        grace=time.monotonic()+3
        while ready_file.exists() and process.poll() is None and time.monotonic()<grace:time.sleep(.2)
        if ready_file.exists() and process.poll() is None:
            detach_tree(process)
            installation.confirm();ready_file.unlink(missing_ok=True)
            if validation:
                from core.distribution import atomic_json
                validation['application_opened']=True;atomic_json(root/'validation.json',validation)
        else:
            close_tree(process)
            installation.rollback()
            ctypes.windll.user32.MessageBoxW(None,'A abertura nao foi concluida. A versao anterior foi preservada. Abra novamente; o registro esta na pasta logs.','DIEF JARVIS',0x10)
            return 1
        code=process.wait()
        if validation:
            from core.distribution import atomic_json
            validation['exit_code']=code;validation['application_opened']=not bool(code)
            atomic_json(root/'validation.json',validation)
        if code:
            installation.rollback()
            ctypes.windll.user32.MessageBoxW(None,'O Jarvis encerrou inesperadamente. A versao anterior foi preservada; consulte a pasta logs.','DIEF JARVIS',0x10)
            return 1
        from core.launcher_update import schedule
        schedule(installation)
    if mutex:ctypes.windll.kernel32.CloseHandle(ctypes.c_void_p(mutex))
    return 0


if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception as error:
        if os.name=='nt':ctypes.windll.user32.MessageBoxW(None,str(error),'DIEF JARVIS',0x10)
        else:raise
