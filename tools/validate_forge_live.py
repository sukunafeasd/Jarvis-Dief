"""Explicit live smoke test, confined to a new FORJA project."""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

def check():
    from core.forge import Runtime
    from core.forge_validation import validate_candidate
    runtime=Runtime(turn_timeout=180)
    try:
        state=runtime.connect()
        report={'connected':state.get('connected'),'models':len(state.get('models',[]))}
        if not state.get('connected'):return {**report,'ok':False,'error':'Conecte a conta antes deste teste.'}
        result=runtime.command('create',name='Verificacao FORJA',prompt=(
            'Crie somente index.html neste projeto: uma previa simples de um cubo 3D verde '
            'girando continuamente em fundo preto, usando ./vendor/three.module.js e seu '
            'three.core.js local. Camera enquadrada, resize correto, luz branca e verde. '
            'Sem rede, sem instalacao, sem ferramentas administrativas. Use apply_patch '
            'para criar o arquivo; nao leia arquivos fora deste projeto. Responda em '
            'portugues com o resultado real. Mantenha o codigo pequeno.'))
        report['accepted']=result.get('accepted')
        deadline=time.monotonic()+200
        while time.monotonic()<deadline:
            state=runtime.snapshot()
            if state.get('phase') in ('ready','error'):break
            time.sleep(1)
        report.update(phase=state.get('phase'),generation_verified=state.get('generation_verified'),
                      project_id=(state.get('project') or {}).get('id'),
                      process_security=state.get('process_security'))
        if state.get('candidate_preview_url'):
            evidence=validate_candidate(state['candidate_preview_url'])
            report['renderer']=evidence
            result=runtime.command('validate_preview',project_id=state['project']['id'],revision=state['candidate_revision'],candidate_url=state['candidate_preview_url'],evidence=evidence)
            report['preview_validated']=result.get('accepted')
        if state.get('error'):report['error']=state['error']
        if not report.get('generation_verified'):
            report['activities']=state.get('activities',[])[-5:]
        report['ok']=bool(report.get('generation_verified') and report.get('preview_validated'))
        if state.get('phase')=='running':runtime.command('cancel')
        return report
    finally:runtime.close()

if __name__=='__main__':
    if '--generate' not in sys.argv:raise SystemExit('Este teste exige --generate e uma conta conectada.')
    try:report=check()
    except Exception as error:report={'ok':False,'error_type':type(error).__name__}
    print(json.dumps(report,ensure_ascii=False))
    raise SystemExit(0 if report.get('ok') else 1)
