"""Current-user interactive logon task; no passwords or UAC policy changes."""
import argparse
import json
import os
from pathlib import Path

from core.local_data import ROOT, atomic_write

PREFERENCE = ROOT / 'autostart.json'
PROJECT = Path(__file__).resolve().parent.parent


def launch_root():
    managed = os.environ.get('DIEF_MANAGED_ROOT')
    if not managed:
        return PROJECT
    root = Path(managed)
    if not root.is_absolute():
        raise ValueError('Pasta de instalacao invalida.')
    root = root.resolve()
    if PROJECT.resolve().parent.parent != root or PROJECT.resolve().parent.name != 'versions':
        raise ValueError('O codigo nao pertence a esta instalacao gerenciada.')
    return root


def with_scheduler(callback):
    import pythoncom
    import win32api
    import win32security
    from win32com.client import Dispatch
    pythoncom.CoInitialize()
    service = folder = None
    try:
        token = win32security.OpenProcessToken(win32api.GetCurrentProcess(), 8)
        try:
            sid = win32security.ConvertSidToStringSid(
                win32security.GetTokenInformation(token, win32security.TokenUser)[0])
        finally:
            token.Close()
        service = Dispatch('Schedule.Service')
        service.Connect()
        folder = service.GetFolder('\\')
        return callback(service, folder, sid)
    finally:
        folder = service = None
        pythoncom.CoUninitialize()


def task_name(sid):
    return 'DIEF-JARVIS-Logon-' + sid


def find_task(folder, sid):
    return next((task for task in folder.GetTasks(1) if task.Name == task_name(sid)), None)


def same_user(value, sid):
    if value == sid:
        return True
    import pywintypes
    import win32security
    try:
        account_sid = win32security.LookupAccountName(None, value)[0]
        return win32security.ConvertSidToStringSid(account_sid) == sid
    except pywintypes.error:
        return False


def matches(task, sid, root=None):
    root = launch_root() if root is None else root
    if task is None or not task.Enabled:
        return False
    definition = task.Definition
    principal = definition.Principal
    if not same_user(principal.UserId, sid) or principal.LogonType != 3 or principal.RunLevel != 1:
        return False
    if definition.Actions.Count != 1 or definition.Triggers.Count != 1:
        return False
    action, trigger = definition.Actions.Item(1), definition.Triggers.Item(1)
    return (action.Type == 0 and not action.Arguments
            and os.path.normcase(action.Path) == os.path.normcase(str(root / 'DIEF JARVIS.exe'))
            and os.path.normcase(action.WorkingDirectory) == os.path.normcase(str(root))
            and trigger.Type == 9 and same_user(trigger.UserId, sid) and trigger.Enabled)


def enabled():
    if os.name != 'nt':
        return False
    return with_scheduler(lambda service, folder, sid: matches(find_task(folder, sid), sid))


def remove_legacy():
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                           r'Software\Microsoft\Windows\CurrentVersion\Run',
                           0, winreg.KEY_SET_VALUE) as key:
            try:
                winreg.DeleteValue(key, 'JARVIS_AI')
            except FileNotFoundError:
                pass
    except FileNotFoundError:
        pass


def set_enabled(value):
    from core.elevation import is_admin
    if os.name != 'nt' or not is_admin():
        raise PermissionError('Confirme a permissao de administrador para configurar a inicializacao.')
    root = launch_root()
    executable = root / 'DIEF JARVIS.exe'
    if value and not executable.is_file():
        raise FileNotFoundError('O EXE do Jarvis nao foi encontrado nesta instalacao.')
    def configure(service, folder, sid):
        task = find_task(folder, sid)
        if value:
            definition = service.NewTask(0)
            definition.RegistrationInfo.Description = 'DIEF JARVIS: abertura elevada na entrada desta conta. Desativavel no perfil do Jarvis.'
            definition.Principal.UserId = sid
            definition.Principal.LogonType = 3  # Existing interactive token, never a saved password.
            definition.Principal.RunLevel = 1
            trigger = definition.Triggers.Create(9)
            trigger.UserId, trigger.Delay, trigger.Enabled = sid, 'PT15S', True
            action = definition.Actions.Create(0)
            action.Path, action.WorkingDirectory = str(executable), str(root)
            action.Arguments = ''
            settings = definition.Settings
            settings.Enabled = True
            settings.DisallowStartIfOnBatteries = False
            settings.StopIfGoingOnBatteries = False
            settings.ExecutionTimeLimit = 'PT0S'
            settings.MultipleInstances = 2
            settings.StartWhenAvailable = True
            folder.RegisterTaskDefinition(task_name(sid), definition, 6, sid, None, 3)
            if not matches(find_task(folder, sid), sid, root):
                raise RuntimeError('O Windows nao confirmou a tarefa de inicializacao elevada.')
        elif task is not None:
            folder.DeleteTask(task_name(sid), 0)
            if find_task(folder, sid) is not None:
                raise RuntimeError('O Windows nao confirmou a remocao da tarefa.')
    with_scheduler(configure)
    atomic_write(PREFERENCE, json.dumps({'enabled': bool(value)}).encode('utf-8'))
    remove_legacy()


def ensure_default():
    if os.name != 'nt' or os.environ.get('DIEF_VALIDATION') == '1' or os.environ.get('DIEF_JARVIS_DATA_DIR') or os.environ.get('QT_QPA_PLATFORM') == 'offscreen':
        return
    preference = json.loads(PREFERENCE.read_text(encoding='utf-8')) if PREFERENCE.exists() else {'enabled': True}
    if preference.get('enabled') is True:
        if not enabled():
            set_enabled(True)
        else:
            remove_legacy()
            if not PREFERENCE.exists():
                atomic_write(PREFERENCE, json.dumps({'enabled': True}).encode('utf-8'))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--enable', action='store_true')
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    try:
        set_enabled(args.enable)
        result = {'ok': True, 'enabled': enabled()}
    except Exception as error:
        result = {'ok': False, 'error': type(error).__name__, 'code': getattr(error, 'hresult', None)}
    atomic_write(args.report, json.dumps(result).encode('utf-8'))


if __name__ == '__main__':
    main()
