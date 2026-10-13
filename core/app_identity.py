"""Identidade nativa antes de criar janelas; nao depende de Qt."""
import ctypes
import os
from pathlib import Path

APP_ID='DIEF.JARVIS.Desktop'
NAME='DIEF JARVIS'


def register_windows_identity():
    if os.name!='nt':return False
    return ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)==0


def brand_tk_window(window):
    register_windows_identity()
    icon=Path(__file__).resolve().parents[1]/'config/dief-jarvis.ico'
    if os.name=='nt' and icon.exists():
        try:window.iconbitmap(str(icon))
        except Exception:pass


def brand_shortcut(path):
    if os.name!='nt':return False
    from win32com.propsys import propsys,pscon
    from win32com.shell import shellcon
    store=propsys.SHGetPropertyStoreFromParsingName(str(path),None,shellcon.GPS_READWRITE,propsys.IID_IPropertyStore)
    store.SetValue(pscon.PKEY_AppUserModel_ID,propsys.PROPVARIANTType(APP_ID));store.Commit()
    return True
