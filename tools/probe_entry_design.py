"""Render entry states with synthetic data; never requests administrator access."""
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
output = Path(sys.argv[1])
output.mkdir(parents=True, exist_ok=True)

import tkinter as tk
from PIL import ImageGrab
from core.fui_bootstrap import BootstrapSurface

root = tk.Tk()
root.overrideredirect(True)
root.geometry('840x580+40+40')
surface = BootstrapSurface(root, names=('Atualizações','Dependências','Arquivos','Áudio','IA','Conexões'))
surface.update_status('Atualizações', 'Versão local disponível para iniciar', 'ok')
surface.update_status('Dependências', 'Conferindo a integridade dos componentes instalados', 'working')
root.update()
time.sleep(.3)
ImageGrab.grab(bbox=(40,40,880,620)).save(output/'startup.png')
surface.update_status('Dependências', 'Não foi possível concluir o download. Sua instalação anterior foi preservada.', 'error')
surface.notice.configure(text='Verifique sua conexão e tente novamente. Nenhum dado pessoal foi removido.',fg='#ffb384')
button=tk.Button(root,text='Tentar novamente',bg='#075393',fg='#edfaff',relief='flat')
button.place(**surface.retry_position)
root.update()
time.sleep(.3)
ImageGrab.grab(bbox=(40,40,880,620)).save(output/'startup-error.png')
root.destroy()

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PyQt6.QtWidgets import QApplication
from core.elevation_dialog import ElevationDialog
app=QApplication([])
dialog=ElevationDialog(lambda:False,reduced=True)
dialog.show()
app.processEvents()
dialog.grab().save(str(output/'admin.png'))
dialog.resize(580,560)
dialog.elevate()
app.processEvents()
dialog.grab().save(str(output/'admin-retry-small.png'))
dialog.close()
print(output)
