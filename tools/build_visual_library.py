"""Gera o indice local da biblioteca; nenhuma malha externa e baixada."""
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from core import visual_library as library

if __name__=='__main__':
    path=ROOT/'core/spatial/assets/visual-library.json'
    payload={'overview':library.overview(),'icons':list(library.ICONS.values()),'phrases':list(library.PHRASE_BANK.values())}
    path.write_text(json.dumps(payload,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    print(len(payload['icons']),'receitas e',len(payload['phrases']),'frases:',path)
