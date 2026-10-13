"""Gera o selo local e atualiza apenas o atalho deste projeto."""
import argparse
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from core.branding import NAME, ICON, build_icon


def refresh_shortcut():
    from win32com.client import Dispatch
    shell=Dispatch('WScript.Shell')
    desktop=Path(shell.SpecialFolders('Desktop'))
    target=ROOT/'.venv'/'Scripts'/'pythonw.exe'
    if not target.exists():raise FileNotFoundError('Python do projeto não encontrado.')
    shortcut=shell.CreateShortcut(str(desktop/(NAME+'.lnk')))
    shortcut.TargetPath=str(target)
    shortcut.Arguments='"'+str(ROOT/'main.py')+'"'
    shortcut.WorkingDirectory=str(ROOT)
    shortcut.Description=NAME+' - Assistente pessoal'
    shortcut.IconLocation=str(ICON)+',0'
    shortcut.Save()
    from core.app_identity import brand_shortcut
    brand_shortcut(desktop/(NAME+'.lnk'))
    # Apenas o atalho legado comprovadamente ligado a este main.py e substituido.
    old=desktop/'J.A.R.V.I.S.lnk'
    if old.exists():
        previous=shell.CreateShortcut(str(old))
        if previous.Arguments.strip('"').casefold()==str(ROOT/'main.py').casefold():
            old.unlink()
    return desktop/(NAME+'.lnk')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description='Atualizar identidade do DIEF JARVIS')
    parser.add_argument('--shortcut',action='store_true')
    args=parser.parse_args()
    build_icon();print('Ícone criado:',ICON)
    if args.shortcut:print('Atalho atualizado:',refresh_shortcut())
