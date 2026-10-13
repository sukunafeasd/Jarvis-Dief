"""Primeira execucao sem contas; nunca substitui configuracoes existentes."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def initialize(root=ROOT):
    folder=Path(root)/'config';folder.mkdir(parents=True,exist_ok=True)
    destination=folder/'api_keys.json'
    if destination.exists():return False
    template=json.loads((folder/'defaults.json').read_text(encoding='utf-8'))
    try:
        with destination.open('x',encoding='utf-8') as file:
            json.dump(template,file,ensure_ascii=False,indent=2)
    except FileExistsError:return False
    return True
