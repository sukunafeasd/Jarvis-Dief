"""Human-facing installation of fixed curated packages, never arbitrary input."""
import os
from pathlib import Path
import subprocess
import sys
from core.extension_suite import ROOT,status,research_python


def install(name):
    commands=[]
    if name=='playwright_mcp':commands=[[sys.executable,str(ROOT/'tools/provision_browser_runtime.py')]]
    elif name=='windows_mcp':commands=[[sys.executable,'-m','pip','install','uv>=0.8,<1'],[sys.executable,'-m','uv','tool','install','--python','3.13','windows-mcp==0.8.5']]
    elif name=='deep_research':commands=[[sys.executable,'-m','pip','install','uv>=0.8,<1'],[sys.executable,'-m','uv','venv','--python','3.12',str(research_python().parents[1])],[sys.executable,'-m','uv','pip','install','--python',str(research_python()),'gpt-researcher==0.16.1']]
    else:
        package={'markitdown':'markitdown[docx,pdf,pptx,xlsx]>=0.1,<1','qdrant_memory':'qdrant-client[fastembed]>=1.14,<2','local_transcription':'faster-whisper>=1.1,<2'}.get(name)
        if not package:raise ValueError('Nao ha instalador para esta conta; use Conectar.')
        commands=[[sys.executable,'-m','pip','install',package]]
    for command in commands:
        result=subprocess.run(command,capture_output=True,text=True,timeout=900,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        if result.returncode:return False,'Instalacao nao concluiu. Confira internet, espaco e documentacao da ferramenta.'
    value=status(name)
    return bool(value['installed']),'Instalacao concluida; use Testar para verificar. Contas continuam exigindo autorizacao.'
