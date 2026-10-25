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


def recovery_message(installation):
    try:
        restored=installation.rollback()
    except Exception as error:
        from core.update_diagnostics import record_failure
        record_failure(installation.root,'rollback',error)
        return 'A recuperacao automatica nao foi concluida. Nao apague seus dados; consulte os registros na pasta logs.'
    if restored:
        return 'A versao anterior foi restaurada. Abra novamente; os registros estao na pasta logs.'
    return 'Nao ha uma versao anterior disponivel para restaurar. Seus dados nao foram apagados; consulte a pasta logs.'


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
    if not destination.exists():
        temporary=root/('launcher-initial-'+uuid.uuid4().hex+'.tmp')
        try:
            shutil.copy2(sys.executable,temporary)
            os.replace(temporary,destination)
        finally:temporary.unlink(missing_ok=True)
    shortcut=(Path(shortcut_folder) if shortcut_folder else root)/'DIEF JARVIS.lnk'
    if shortcut_folder:Path(shortcut_folder).mkdir(parents=True,exist_ok=True)
    # This helper receives paths as arguments; it never interpolates them as commands.
    import base64
    values=[str(shortcut),str(destination),str(root),str(root/'data/config/dief-jarvis.ico')]
    assignments=';'.join('$p'+str(i)+'=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String("'+base64.b64encode(value.encode()).decode()+'"))' for i,value in enumerate(values))
    script=assignments+';$w=New-Object -ComObject WScript.Shell;'+('' if shortcut_folder else "$p0=[IO.Path]::Combine($w.SpecialFolders('Desktop'),'DIEF JARVIS.lnk');")+' $s=$w.CreateShortcut($p0); $s.TargetPath=$p1; $s.WorkingDirectory=$p2; $s.IconLocation=$p3; $s.Save()'
    subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-EncodedCommand',base64.b64encode(script.encode('utf-16le')).decode()],
        creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),check=True,capture_output=True)


def bounded_release(fetch,stop,timeout=4):
    """An established installation need not wait for a stalled release server."""
    result=queue.Queue(maxsize=1)
    def query():
        try:result.put((True,fetch()))
        except Exception as error:result.put((False,error))
    threading.Thread(target=query,daemon=True,name='ReleaseLookup').start()
    deadline=time.monotonic()+timeout
    while True:
        if stop.is_set():raise InterruptedError('Consulta cancelada.')
        remaining=deadline-time.monotonic()
        if remaining<=0:raise TimeoutError('Consulta de atualizacao demorou; usando instalacao atual.')
        try:ok,value=result.get(timeout=min(.1,remaining))
        except queue.Empty:continue
        if not ok:raise value
        return value


def prepare(root, progress, stop, fetch=latest_release,shortcut_folder=None,approve_update=None):
    if os.name=='nt' and getattr(sys,'frozen',False):ctypes.windll.kernel32.SetDllDirectoryW(None)
    installation=Installation(root);state=installation.state()
    progress('Atualizações','Verificando a ultima versao','working')
    try:
        release=bounded_release(fetch,stop) if fetch is latest_release and state.get('current') and not state.get('pending') else fetch()
    except InterruptedError:raise
    except Exception as error:
        from core.update_diagnostics import record_failure
        record_failure(root,'lookup',error,state.get('current'))
        if not state.get('current'): raise RuntimeError('Nao foi possivel obter a versao oficial. Verifique a internet e tente novamente.')
        progress('Atualizações','Nao foi possivel verificar. Versao instalada preservada','warning')
        release=None
    if release:
        from core.update_status import release_status
        status,message=release_status(state,release)
        progress('Atualizações',message,'warning' if status=='rejected' else 'working' if status in {'available','first_install'} else 'ok')
        should_install=status in {'available','first_install'}
        if status in {'available','rejected'} and approve_update is not None:
            offered={**release,'retry_rejected':True} if status=='rejected' else release
            should_install=approve_update(offered)
            if stop.is_set():raise InterruptedError('Atualizacao cancelada.')
            if not should_install:
                progress('Atualizações','Atualizacao adiada. Versao atual preservada','warning')
        if not should_install:
            application=installation.application(state['current'])
            if status=='current' and state['current']==release['version']:
                try:
                    installation.ensure_launcher(release,progress,stop)
                except InterruptedError:
                    raise
                except Exception as error:
                    from core.update_diagnostics import record_failure
                    record_failure(root,'launcher_repair',error,current=state['current'],target=release['version'])
                    progress('Atualizações','Reparo do inicializador adiado. Versao atual preservada','warning')
        else:
            try:
                if status=='rejected':
                    application=installation.install(release,progress,stop,retry_rejected=True)
                else:
                    application=installation.install(release,progress,stop)
            except InterruptedError:raise
            except Exception as error:
                state=installation.state()
                from core.update_diagnostics import record_failure
                record_failure(root,'install',error,state.get('current'),release['version'])
                if not state.get('current'):raise
                application=installation.application(state['current'])
                progress('Atualizações','Atualizacao nao concluida. Versao anterior preservada','warning')
            else:
                progress('Atualizações','Versao '+installation.state()['current']+' preparada para verificacao','ok')
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


def local_release(artifacts):
    """Return a signed package from an explicit local folder.

    This is deliberately opt-in (``--local-artifacts``) and is used only to
    repair the same person's installed copy before a public release exists.
    The release manifest is still signature- and hash-verified; arbitrary
    folders are never treated as application updates.
    """
    from core.distribution import verified_manifest
    artifacts=Path(artifacts).resolve()
    body=verified_manifest(json.loads((artifacts/'release.json').read_text(encoding='utf-8')))
    for key in ('application','runtime','launcher'):
        item=body[key];source=(artifacts/item['name']).resolve()
        if source.parent!=artifacts or not source.is_file():
            raise ValueError('Artefato local ausente ou fora da pasta selecionada.')
        if source.stat().st_size!=item['size']:
            raise ValueError('Tamanho do artefato local divergente.')
        import hashlib
        if hashlib.sha256(source.read_bytes()).hexdigest()!=item['sha256']:
            raise ValueError('Integridade do artefato local nao confirmada.')
        item['local_path']=str(source)
    return body


def local_download(item,target,progress,stop):
    """Copy a verified local artifact with the same cancellation semantics."""
    import hashlib
    source=Path(item['local_path'])
    digest=hashlib.sha256();written=0
    try:
        with source.open('rb') as incoming,Path(target).open('xb') as output:
            while chunk:=incoming.read(256*1024):
                if stop.is_set():raise InterruptedError('Instalacao cancelada.')
                written+=len(chunk);digest.update(chunk);output.write(chunk)
                progress(f'Copiando {written*100//item["size"]}%')
        if written!=item['size'] or digest.hexdigest()!=item['sha256']:
            raise ValueError('Integridade da copia local nao confirmada.')
    except Exception:
        Path(target).unlink(missing_ok=True)
        raise


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path)
    parser.add_argument('--prepare-only',action='store_true');parser.add_argument('--validate-artifacts',type=Path)
    parser.add_argument('--local-artifacts',type=Path)
    parser.add_argument('--update-version')
    parser.add_argument('--launcher-probe')
    args=parser.parse_args()
    if args.validate_artifacts and not args.root:raise ValueError('O teste exige uma pasta isolada explicita.')
    root=(args.root or Path(os.environ.get('LOCALAPPDATA',str(Path.home())))/'DIEF JARVIS').resolve()
    if args.launcher_probe:
        from core.launcher_probe import run
        return run(root,args.launcher_probe)
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
    window.overrideredirect(True);window.geometry(f'840x580+{max(0,(window.winfo_screenwidth()-840)//2)}+{max(0,(window.winfo_screenheight()-580)//2)}')
    surface=BootstrapSurface(window,names=('Atualizações','Dependências','Arquivos','Áudio','IA','Conexões'))
    surface.canvas.create_text(808,70,text='v'+VERSION,fill='#a3f0ff',font=('Segoe UI',10),anchor='e')
    events=queue.Queue();stop=threading.Event();started=time.monotonic();result={};closed=False
    validation=None
    button=tk.Button(window,text='Tentar novamente',command=lambda:start(),bg='#233348',fg='#edfaff',relief='flat')
    decision=threading.Event();choice={}
    def choose_update(accepted):
        choice['accepted']=accepted
        install_button.place_forget();later_button.place_forget();decision.set()
    install_button=tk.Button(window,text='Instalar atualizacao',command=lambda:choose_update(True),bg='#123d54',fg='#edfaff',relief='flat')
    later_button=tk.Button(window,text='Continuar sem atualizar',command=lambda:choose_update(False),bg='#233348',fg='#edfaff',relief='flat')
    def approve_update(release):
        retry=bool(release.get('retry_rejected'))
        if args.update_version==release['version'] and not retry:return True
        decision.clear();choice.clear();events.put(('_update_available',release['version'],'retry' if retry else ''))
        while not decision.wait(.1):
            if stop.is_set():raise InterruptedError('Atualizacao cancelada.')
        return choice.get('accepted',False)
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
                def validation_download(item,target,progress,stop):
                    source=artifacts/item['name']
                    if hashlib.sha256(source.read_bytes()).hexdigest()!=item['sha256']:raise ValueError('Artefato de teste divergente.')
                    shutil.copy2(source,target)
                with patch('core.distribution.download',side_effect=validation_download):
                    ready=prepare(root,lambda *entry:events.put(entry),stop,fetch=lambda:release,shortcut_folder=root/'test-desktop')
                if ready[0].state().get('application_sha256')!=release['application']['sha256']:raise ValueError('A aplicacao instalada nao corresponde ao pacote testado.')
                validation={'version':release['version'],'artifacts':{key:release[key]['sha256'] for key in ('application','runtime','launcher')},'installer_opened':True,'application_opened':False}
            elif args.local_artifacts:
                from unittest.mock import patch
                release=local_release(args.local_artifacts)
                with patch('core.distribution.download',side_effect=local_download):
                    ready=prepare(root,lambda *entry:events.put(entry),stop,fetch=lambda:release)
            else:ready=prepare(root,lambda *entry:events.put(entry),stop,approve_update=approve_update)
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
                surface.notice.configure(text=text,fg='#ffb384');button.place(**surface.retry_position)
            elif name=='_update_available':
                surface.notice.configure(text=('A versao '+text+' falhou anteriormente. Tentar instalar novamente?' if state=='retry'
                    else 'Versao '+text+' disponivel. Seus dados e conexoes serao preservados.'))
                install_button.configure(text='Tentar instalar novamente' if state=='retry' else 'Instalar atualizacao')
                install_button.place(x=32,y=540,width=220,height=28)
                later_button.place(x=266,y=540,width=250,height=28)
            else:surface.update_status(name,text,state)
        window.after(50,tick)
    surface.canvas.tag_bind('close','<Button-1>',lambda _:close());window.bind('<Escape>',lambda _:close())
    if args.validate_artifacts:
        def capture():
            from PIL import ImageGrab
            folder=root/'validation';folder.mkdir(parents=True,exist_ok=True)
            window.update_idletasks()
            ImageGrab.grab(bbox=(window.winfo_rootx(),window.winfo_rooty(),window.winfo_rootx()+840,window.winfo_rooty()+580)).save(folder/'installer.png')
        window.after(800,capture)
    start();tick();window.mainloop()
    if 'ready' not in result:return 1
    installation,python,application,env=result['ready']
    if args.prepare_only:return 0
    ready_file=root/'sessions'/(uuid.uuid4().hex+'.ready');ready_file.parent.mkdir(exist_ok=True)
    env['DIEF_READY_FILE']=str(ready_file);env['DIEF_PREFLIGHT_COMPLETE']='1'
    update_request=ready_file.with_suffix('.update-request.json')
    env['DIEF_UPDATE_REQUEST']=str(update_request)
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
            message=recovery_message(installation)
            ctypes.windll.user32.MessageBoxW(None,'A abertura nao foi concluida. '+message,'DIEF JARVIS',0x10)
            return 1
        code=process.wait()
        if validation:
            from core.distribution import atomic_json
            validation['exit_code']=code;validation['application_opened']=not bool(code)
            atomic_json(root/'validation.json',validation)
        if code:
            message=recovery_message(installation)
            ctypes.windll.user32.MessageBoxW(None,'O Jarvis encerrou inesperadamente. '+message,'DIEF JARVIS',0x10)
            return 1
        from core.launcher_update import schedule
        restart_version=None
        if update_request.exists():
            try:
                from core.distribution import version
                requested=json.loads(update_request.read_text(encoding='utf-8'))['version']
                if version(requested)>version(installation.state()['current']):restart_version=requested
            except (ValueError,TypeError,KeyError,OSError):pass
            finally:update_request.unlink(missing_ok=True)
        schedule(installation,restart_version=restart_version)
    if mutex:ctypes.windll.kernel32.CloseHandle(ctypes.c_void_p(mutex))
    return 0


if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception as error:
        if os.name=='nt':ctypes.windll.user32.MessageBoxW(None,str(error),'DIEF JARVIS',0x10)
        else:raise
