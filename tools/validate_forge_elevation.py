"""Read-only handshake from an elevated host; never starts a model turn."""
import argparse
import ctypes
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

def check():
    from core.forge import Runtime
    from core.forge.transport import AppServer
    diagnostics=[]
    class DiagnosticServer(AppServer):
        async def start(self):
            try:return await super().start()
            except Exception as error:
                while error:
                    diagnostics.append({'type':type(error).__name__,'message':str(error)[:500]})
                    error=error.__cause__
                raise
    if not ctypes.windll.shell32.IsUserAnAdmin():return {'ok':False,'error':'Host de teste nao elevado.'}
    runtime=Runtime(transport_factory=DiagnosticServer)
    try:
        state=runtime.connect()
        security=state.get('process_security') or {}
        return {'ok':bool(state.get('transport')=='ready' and security.get('host_elevated')
                         and security.get('child_elevated') is False),
                'connected':state.get('connected'),'sandbox':state.get('sandbox',{}).get('readiness'),
                'security':security,'error':state.get('error'),'diagnostics':diagnostics}
    except Exception as error:return {'ok':False,'error_type':type(error).__name__,'error':str(error)[:500]}
    finally:runtime.close()

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);args=parser.parse_args()
    output=Path(args.output).resolve();output.relative_to(Path(tempfile.gettempdir()).resolve())
    output.write_text(json.dumps(check(),ensure_ascii=False),encoding='utf-8')
