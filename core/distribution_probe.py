"""Verificacao inicial em processo separado, com eventos estruturados."""
import json
import threading
from core.startup import check_startup


def progress(*entry):print(json.dumps(entry,ensure_ascii=True),flush=True)


if __name__=='__main__':
    try:ok=check_startup(progress,threading.Event(),install=False)
    except Exception as error:
        progress('Arquivos','Verificacao interrompida: '+type(error).__name__,'error');ok=False
    raise SystemExit(0 if ok else 1)
