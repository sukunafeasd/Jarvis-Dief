"""Explicit Windows elevation gate before accounts, installers or audio start."""
import ctypes
import os
from pathlib import Path
import subprocess
import sys


def is_admin():
    if os.name != 'nt':
        return True
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except OSError:
        return False


def restart_elevated():
    arguments = sys.argv[1:] if getattr(sys, 'frozen', False) else sys.argv
    executable = sys.executable
    if not getattr(sys, 'frozen', False):
        pythonw = Path(executable).with_name('pythonw.exe')
        if pythonw.exists():
            executable = str(pythonw)
        arguments = [str(Path(sys.argv[0]).resolve()), *sys.argv[1:]]
    result = ctypes.windll.shell32.ShellExecuteW(
        None, 'runas', executable, subprocess.list2cmdline(arguments),
        str(Path(sys.executable if getattr(sys, 'frozen', False) else sys.argv[0]).resolve().parent), 1)
    return result > 32


def require_admin():
    if is_admin():
        return True
    from core.startup import visual_motion_reduced
    reduced=visual_motion_reduced()
    try:
        from PyQt6.QtWidgets import QApplication
        from core.elevation_dialog import ElevationDialog
        app=QApplication.instance() or QApplication([])
        from core.branding import initialize_application
        initialize_application(app)
        dialog=ElevationDialog(restart_elevated,reduced=reduced)
        dialog.exec()
        return False
    except ImportError:
        pass
    import tkinter as tk
    import time
    from core.fui_bootstrap import BootstrapSurface
    root = tk.Tk()
    from core.app_identity import brand_tk_window
    brand_tk_window(root)
    root.title('DIEF JARVIS')
    root.configure(bg='#050d12')
    root.resizable(False, False)
    width, height = 660, 440
    root.geometry(f'{width}x{height}+{max(0,(root.winfo_screenwidth()-width)//2)}+{max(0,(root.winfo_screenheight()-height)//2)}')
    surface=BootstrapSurface(root,width,height,mode='admin',reduced=reduced);notice=surface.notice
    notice.configure(text='Reinicie e confirme a solicitação do Windows para continuar.',wraplength=width-80)
    started=time.monotonic();after_id=None;closed=False
    def close():
        nonlocal closed
        if closed:return
        closed=True
        if after_id is not None:root.after_cancel(after_id)
        root.destroy()
    def restart():
        if restart_elevated():
            close()
        else:
            notice.configure(text='A elevação não foi autorizada. Tente novamente ou feche o Jarvis.')
    button=tk.Button(root, text='Reiniciar como administrador', command=restart, bg='#54242e', fg='#edfaff',
              activebackground='#743342',activeforeground='#ffffff',highlightbackground='#ff5660',highlightthickness=1,
              relief='flat', padx=18, pady=10, font=('Segoe UI',11))
    surface.canvas.create_window(width/2,377,window=button,width=width-80,height=40)
    def tick():
        nonlocal after_id
        if closed:return
        if not surface.motion_reduced and root.state()!='iconic' and root.winfo_ismapped():surface.animate(time.monotonic()-started)
        after_id=root.after(60,tick)
    surface.canvas.tag_bind('close','<Button-1>',lambda event:close())
    root.protocol('WM_DELETE_WINDOW',close);root.bind('<Escape>',lambda event:close())
    tick()
    root.mainloop()
    return False
