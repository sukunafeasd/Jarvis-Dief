"""Confirmacao de abertura limitada ao diretorio da instalacao gerenciada."""
import os
from pathlib import Path


def confirm_window(filename):
    root=os.environ.get('DIEF_MANAGED_ROOT')
    if not root:return False
    folder=(Path(root)/'sessions').resolve();path=Path(filename).resolve()
    if path.parent!=folder or path.suffix!='.ready':return False
    path.touch(exist_ok=False)
    return True
