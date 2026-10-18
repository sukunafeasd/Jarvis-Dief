"""Fixed Windows operations and reversible, narrowly scoped cleanup."""
import ctypes
import hashlib
import json
import os
from pathlib import Path
import subprocess
import threading
import time
import uuid

TEMP_ROOT=Path.home()/'AppData/Local/Temp'
MAX_CLEAN_FILES=100
MIN_AGE=7*24*3600
WINDOWS_ACTIONS={'defender_update','security_max','integrity_verify','windows_repair'}


def administrator():
    try:return os.name=='nt' and bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (AttributeError,OSError):return False


def desktop_path():
    if os.name!='nt':return Path.home()/'Desktop'
    from ctypes import wintypes
    import uuid as ids
    guid=(ctypes.c_byte*16).from_buffer_copy(ids.UUID('B4BFCC3A-DB2C-424C-B029-7FE99A87C641').bytes_le)
    shell=ctypes.WinDLL('shell32');shell.SHGetKnownFolderPath.argtypes=[ctypes.c_void_p,wintypes.DWORD,wintypes.HANDLE,ctypes.POINTER(ctypes.c_void_p)]
    output=ctypes.c_void_p()
    if shell.SHGetKnownFolderPath(ctypes.byref(guid),0,None,ctypes.byref(output))!=0:raise ValueError('Area de trabalho indisponivel.')
    try:return Path(ctypes.wstring_at(output))
    finally:
        ole=ctypes.WinDLL('ole32');ole.CoTaskMemFree.argtypes=[ctypes.c_void_p];ole.CoTaskMemFree(output)


def cleanup_snapshot(service):
    root=service.canonical_path(TEMP_ROOT);service.check_chain(root)
    if not root.is_dir():raise ValueError('Pasta temporaria indisponivel.')
    files=[];total=0
    with os.scandir(root) as entries:
        for count,entry in enumerate(entries):
            if count>=5000:break
            path=Path(entry.path)
            if path.suffix.lower() not in {'.tmp','.temp'} or service.excluded(Path(path.name)) or not entry.is_file(follow_symlinks=False):continue
            if service.linked(path):continue
            info=path.stat(follow_symlinks=False)
            if info.st_nlink!=1 or info.st_size>service.MAX_FILE or time.time()-info.st_mtime<MIN_AGE:continue
            if len(files)>=MAX_CLEAN_FILES or total+info.st_size>service.MAX_TOTAL:break
            content=service.read_bounded(path);total+=len(content);files.append((Path(path.name),content))
    files.sort(key=lambda item:item[0].as_posix())
    return files,service.snapshot_fingerprint(files)


def prepare(service,action):
    if service.STATE['phase']=='idle':raise ValueError('Ative o protocolo ULTRON primeiro.')
    if action=='cleanup_temp':
        files,fingerprint=cleanup_snapshot(service)
        if not files:raise ValueError('Nenhum temporario elegivel com mais de sete dias foi encontrado.')
        return {'args':None,'fingerprint':fingerprint,'details':{'file_count':len(files),'bytes':sum(len(c) for _,c in files),
            'scope':'Somente arquivos .tmp/.temp da pasta temporaria deste usuario, com mais de sete dias, sem links; copia recuperavel antes da remocao. Documentos, programas, downloads, registro e politicas ficam intactos.'}}
    if action not in WINDOWS_ACTIONS:raise ValueError('Acao nao registrada.')
    if not administrator():raise ValueError('Esta sessao nao e administradora. A operacao exige abrir o Jarvis como administrador; nao contorno a confirmacao do Windows.')
    if any(item['state'] in {'running','uncertain'} for item in service.OPERATIONS):raise ValueError('Uma operacao esta em andamento ou precisa de verificacao.')
    scopes={
        'defender_update':'Atualizar as assinaturas do Microsoft Defender; nao alterar as politicas de protecao.',
        'security_max':'Atualizar as assinaturas e executar varredura completa no Defender. O Defender pode colocar ameacas em quarentena. Nao modificar politicas, exclusoes ou firewall.',
        'integrity_verify':'Verificar arquivos protegidos com SFC /verifyonly e imagem do Windows com DISM /ScanHealth; sem reparar arquivos.',
        'windows_repair':'Executar DISM /RestoreHealth e SFC /scannow. Pode baixar componentes do Windows Update e substituir arquivos protegidos corrompidos. Nao ha rollback automatico; pode exigir reinicializacao, que nao sera feita automaticamente.'}
    if action in {'defender_update','security_max'}:
        summary=service.powershell_summary('defender')
        if not summary or not summary['enabled']:raise ValueError('O Microsoft Defender esta indisponivel; nao habilito nem altero politicas automaticamente.')
    return {'args':None,'fingerprint':None,'details':{'scope':scopes[action],'requires_administrator':True}}


def commands(service,action):
    system=Path(os.environ.get('SystemRoot','C:/Windows'))/'System32'
    prefix=[str(service.POWERSHELL),'-NoLogo','-NoProfile','-NonInteractive','-Command']
    return {
        'defender_update':[('Assinaturas do Defender',prefix+['Update-MpSignature -ErrorAction Stop'])],
        'security_max':[('Assinaturas do Defender',prefix+['Update-MpSignature -ErrorAction Stop']),('Varredura completa',prefix+['Start-MpScan -ScanType FullScan -ErrorAction Stop'])],
        'integrity_verify':[('Integridade dos arquivos',[str(system/'sfc.exe'),'/verifyonly']),('Integridade da imagem',[str(system/'dism.exe'),'/Online','/Cleanup-Image','/ScanHealth','/English'])],
        'windows_repair':[('Recuperacao da imagem',[str(system/'dism.exe'),'/Online','/Cleanup-Image','/RestoreHealth','/English']),('Recuperacao dos arquivos',[str(system/'sfc.exe'),'/scannow'])]
    }[action]


def windows_operation(service,record):
    try:
        if not administrator():raise ValueError('Administrador necessario.')
        steps=commands(service,record['action']);record['total']=len(steps);record['completed']=0
        for label,args in steps:
            record['message']=label+' em andamento; o Windows nao fornece percentual confiavel nesta interface.'
            subprocess.run(args,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=3600,check=True,
                creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            record['completed']+=1
        record.update(state='completed',message='Comandos concluidos pelo Windows. O resultado deve ser revisado; isso nao comprova ausencia de malware nem recuperacao de todos os problemas.')
    except subprocess.TimeoutExpired:
        record.update(state='uncertain',message='Acompanhamento excedeu o prazo. O Windows pode continuar trabalhando. Nao repita a operacao antes de conferir seu estado.')
    except (OSError,ValueError,subprocess.SubprocessError):
        record.update(state='failed',message='O Windows nao confirmou a operacao. Etapas anteriores podem ter sido executadas; verifique antes de repetir.')
    finally:record['finished_at']=service.now()


def launch(service,action):
    if not administrator() or service.STATE['phase']=='idle' or any(item['state'] in {'running','uncertain'} for item in service.OPERATIONS):raise ValueError('Operacao indisponivel nesta sessao.')
    record={'id':uuid.uuid4().hex,'action':action,'state':'running','started_at':service.now(),'message':'Preparando operacao confirmada.'}
    service.OPERATIONS.append(record);del service.OPERATIONS[:-20]
    threading.Thread(target=windows_operation,args=(service,record),daemon=True,name='UltronWindows').start()
    return {'operation_id':record['id'],'state':'running'}


def cleanup(service,expected):
    if os.name!='nt':raise ValueError('Limpeza com handles fixados exige Windows.')
    files,fingerprint=cleanup_snapshot(service);service.require_snapshot(fingerprint,expected)
    from ctypes import wintypes
    backup_id=uuid.uuid4().hex;opened=[];cleaned=0;removed_bytes=0
    with service.ConfinedWriter(TEMP_ROOT) as source,service.ConfinedWriter(service.DATA) as destination:
        api=source.windows.api
        api.ReadFile.argtypes=[wintypes.HANDLE,ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(wintypes.DWORD),ctypes.c_void_p]
        api.ReadFile.restype=wintypes.BOOL
        api.SetFileInformationByHandle.argtypes=[wintypes.HANDLE,ctypes.c_int,ctypes.c_void_p,wintypes.DWORD]
        api.SetFileInformationByHandle.restype=wintypes.BOOL
        try:
            # Keep all source handles open, without write/delete sharing, until
            # the recovery copy is published and deletion is done by handle.
            for relative,content in files:
                path=service.canonical_path(TEMP_ROOT)/relative
                handle=api.CreateFileW(str(path),0x80010080,1,None,3,0x00200080,None)
                if handle==ctypes.c_void_p(-1).value:raise ctypes.WinError(ctypes.get_last_error())
                opened.append((handle,relative,content));source.windows.verify(handle,path,False)
                if time.time()-path.stat(follow_symlinks=False).st_mtime<MIN_AGE:raise ValueError('Arquivo mudou desde a preparacao.')
                buffer=ctypes.create_string_buffer(len(content)+1);read=wintypes.DWORD()
                if not api.ReadFile(handle,buffer,len(content)+1,ctypes.byref(read),None):raise ctypes.WinError(ctypes.get_last_error())
                if read.value!=len(content) or buffer.raw[:read.value]!=content:raise ValueError('Arquivo mudou desde a aprovacao.')
            destination.directory('backups/'+backup_id,exclusive=True);manifest={'id':backup_id,'created_at':service.now(),'kind':'cleanup','files':[]}
            for handle,relative,content in opened:
                destination.write('backups/'+backup_id+'/files/'+relative.as_posix(),content)
                manifest['files'].append({'path':relative.as_posix(),'size':len(content),'sha256':hashlib.sha256(content).hexdigest()})
            destination.write('backups/'+backup_id+'/manifest.json',json.dumps(manifest).encode())
            failure=False
            for handle,relative,content in opened:
                if not delete_handle(api,handle):
                    failure=True;break
                cleaned+=1;removed_bytes+=len(content)
            return {'state':'partial' if failure else 'completed','cleaned_files':cleaned,'bytes':removed_bytes,'backup_id':backup_id,
                    'message':'Limpeza limitada concluida.' if not failure else 'Limpeza parcial; a copia de recuperacao foi preservada.'}
        finally:
            for handle,_,_ in opened:source.windows.close(handle)


def delete_handle(api,handle):
    disposition=ctypes.c_ubyte(1)
    return bool(api.SetFileInformationByHandle(handle,4,ctypes.byref(disposition),ctypes.sizeof(disposition)))
