"""Exercise the native Qt host with isolated local records, never provider APIs."""
import json
import asyncio
import argparse
import os
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import patch,Mock
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--projects',action='store_true');args=parser.parse_args()
    output=Path(tempfile.mkdtemp(prefix='dief-neural-native-'))
    os.environ['DIEF_JARVIS_DATA_DIR']=str(output/'data')
    from PyQt6.QtWidgets import QApplication
    import ui
    import main as jarvis_main
    from core import conversation_memory
    from memory import memory_manager as memory
    app=QApplication([sys.argv[0]]);app.setStyle('Fusion')
    config=output/'profile.json'
    config.write_text(json.dumps({'gemini_api_key':'synthetic-no-provider','os_system':'windows','hud_style':'core','reduce_motion':False,'panel_sounds_enabled':False}))
    errors=[]
    def exception(kind,value,tb):
        import traceback
        errors.append(str(value));traceback.print_exception(kind,value,tb)
    sys.excepthook=exception

    def wait(predicate,seconds=20):
        end=time.monotonic()+seconds
        while time.monotonic()<end:
            app.processEvents()
            if predicate():return True
            time.sleep(.01)
        return False

    def evaluate(view,expression):
        result=[];view.page().runJavaScript(expression,result.append)
        if not wait(lambda:bool(result),3):raise TimeoutError('Native renderer callback')
        return result[0]

    def green_pixels_visible(window):
        image=window.grab().toImage();green=blue=0
        for y in range(int(image.height()*.25),int(image.height()*.65),16):
            for x in range(int(image.width()*.36),int(image.width()*.64),16):
                pixel=image.pixelColor(x,y);green+=pixel.green();blue+=pixel.blue()
        return green>blue*1.15

    checks={}
    with patch.object(ui,'API_FILE',config),patch('memory.config_manager.CONFIG_FILE',config),patch.object(ui.MainWindow,'_verify_saved_connections'),patch.object(memory,'MEMORY_PATH',output/'memory.json'):
        facts={
            'forja_biblioteca':'Decidimos que a Forja deve manter uma biblioteca local de projetos.',
            'forja_motor':'Planejamos usar o motor Codex para criar os projetos dentro da Forja.',
            'forja_salvar':'Combinamos que os projetos da Forja podem ser salvos na pasta escolhida.'}
        for key,value in facts.items():memory.remember(key,value,'projects')
        memory.remember('spotify','Prefiro Spotify minimizado ao iniciar o programa.','preferences')
        memory.remember('agenda','As tarefas devem ficar na agenda local.','notes')
        phrase='Jarvis, lembra do que planejamos para a Forja?'
        if args.projects:
            from core.forge.files import ProjectStore
            from core import forge_project_lookup
            project_root=output/'forge';store=ProjectStore(project_root)
            for name in ('Site pessoal iniciado','Dashboard de teste','Portfolio local'):store.create(name)
            original_lookup=forge_project_lookup.lookup
            lookup_patch=patch.object(forge_project_lookup,'lookup',side_effect=lambda:original_lookup(project_root))
            lookup_patch.start()
            phrase='Jarvis, tinha algum projeto na Forja que eu tinha comecado?'
        conversation_memory.record('user',phrase,'native-current-question')
        window=ui.MainWindow(str(ROOT/'core/face_model.obj'));window.resize(1280,850);window.show()
        window._ui_sounds.enabled=False
        ui.C.PRI='#a020f0'
        try:
            checks['host_ready']=wait(lambda:window._environment.started and window.hud._spatial_core and window.hud._spatial_core._ready,30)
            if not checks['host_ready']:raise RuntimeError('Native host did not become ready')
            view=window.hud._spatial_core
            checks['camera_arrived']=wait(lambda:evaluate(view,'window.hologramDiagnostics?.().travel')==0,20)
            window.grab().save(str(output/'main-hologram.png'))
            formation_started=time.monotonic()
            owner=jarvis_main.JarvisLive.__new__(jarvis_main.JarvisLive)
            owner._forge_mode=False;owner._manual_rest=False;owner.session=None
            owner._response_epoch=1;owner._last_user_speech=time.monotonic();owner._fish_voice=Mock()
            owner.ui=SimpleNamespace(_win=window,show_neural_memory=window._neural_sig.emit,write_log=window._log_sig.emit,
                                     ultron_user_context=lambda:{'serial':1,'text':phrase})
            checks['exact_phrase_routed']=asyncio.run(owner._route_protocol_user_once(phrase)) is True
            spoken=' '.join(call.args[0] for call in owner._fish_voice.feed.call_args_list)
            checks['speech_announces_search_and_uses_evidence']=(('Vou verificar' in spoken and 'Site pessoal' in spoken) if args.projects else ('Vou consultar' in spoken and 'biblioteca' in spoken)) and 'ativar' not in spoken
            checks['records_delivered']=wait(lambda:evaluate(view,'window.neuralMemoryDiagnostics?.()').get('items')==3,10)
            initial=evaluate(view,'window.neuralMemoryDiagnostics?.()')
            checks['gradual_start']=0<=initial['progress']<.6
            for stage in (.25,.45,.65):
                wait(lambda:evaluate(view,'window.neuralMemoryDiagnostics?.()')['progress']>=stage,8)
                window.grab().save(str(output/f'transition-{stage}.png'))
            checks['no_torn_surfaces']=evaluate(view,'window.neuralMemoryDiagnostics?.().deformedSurfaces')==0
            checks['full_formation']=wait(lambda:evaluate(view,'window.neuralMemoryDiagnostics?.()')['progress']>=.99,12)
            checks['cortex_normals_face_outward']=evaluate(view,'window.neuralMemoryDiagnostics?.().cortexAlignment')>.5
            formation_seconds=round(time.monotonic()-formation_started,3)
            checks['formation_under_nine_seconds']=formation_seconds<9
            checks['matches_live_core_color']=evaluate(view,'document.body.dataset.neuralColor')==ui.C.PRI
            checks['real_fragments']=evaluate(view,'[...document.querySelectorAll(".neural-fragment")].filter(e=>!e.hidden).map(e=>e.textContent)')
            checks['all_three_visible']=len(checks['real_fragments'])==3
            checks['question_not_presented']=all(phrase not in fragment for fragment in checks['real_fragments'])
            checks['unrelated_topics_absent']=all('Spotify' not in fragment and 'agenda' not in fragment for fragment in checks['real_fragments']) and 'Spotify' not in spoken and 'agenda' not in spoken
            if args.projects:checks['project_manifests_not_chat']=all('Projetos locais da Forja' in fragment for fragment in checks['real_fragments'])
            window.grab().save(str(output/'native-neural.png'))
            # Real renderer, synthetic voice level: verify light and evidence focus.
            evaluate(view,"window.__normalUpdate=window.updateCore;window.updateCore=v=>window.__normalUpdate({...v,phase:'speaking',level:.65});window.updateCore({visible:true});")
            checks['voice_light_reacts']=wait(lambda:evaluate(view,'window.neuralMemoryDiagnostics?.().voice')>.4,3)
            text='Portfolio local iniciado' if args.projects else 'A biblioteca local permite salvar projetos'
            evaluate(view,'window.narrateNeuralMemory('+json.dumps(text)+')')
            checks['narration_focuses_evidence']=evaluate(view,'window.neuralMemoryDiagnostics?.().focus')>=0
            evaluate(view,"window.narrateNeuralMemory('O Spotify esta aberto');")
            checks['unrelated_narration_clears_focus']=evaluate(view,'window.neuralMemoryDiagnostics?.().focus')==-1
            evaluate(view,'window.updateCore=window.__normalUpdate;window.updateCore({phase:"idle",level:0});')
            checks['voice_light_releases']=wait(lambda:evaluate(view,'window.neuralMemoryDiagnostics?.().voice')<.05,3)
            with patch.object(ui.C,'PRI','#58ff95'):
                checks['theme_changes_live']=wait(lambda:evaluate(view,'document.body.dataset.neuralColor')=='#58ff95',2)
                checks['theme_changes_rendered_pixels']=wait(lambda:green_pixels_visible(window),3)
                window.grab().save(str(output/'native-neural-recolored.png'))
            snapshot=window.interface_snapshot()
            checks['runtime_observed']=snapshot['neural_memory']['observed']
            window._cancel_neural_memory()
            checks['cancel_hides_fragments']=wait(lambda:evaluate(view,'[...document.querySelectorAll(".neural-fragment")].every(e=>e.hidden)'),3)
            checks['returned_to_core']=wait(lambda:evaluate(view,'window.neuralMemoryDiagnostics?.()')['progress']==0,10)
            owner._fish_voice.reset_mock()
            phrase='Jarvis, eu quero que tu vai para aquele modo onde tu consegue puxar as lembrancas, etc, antigas.'
            checks['ambiguous_command_routed']=asyncio.run(owner._route_protocol_user_once(phrase)) is True
            spoken=' '.join(call.args[0] for call in owner._fish_voice.feed.call_args_list)
            checks['asks_subject_in_voice_queue']='Qual assunto' in spoken
            checks['awaiting_subject_forms_brain']=wait(lambda:evaluate(view,'window.neuralMemoryDiagnostics?.()')['progress']>=.99,10)
            diagnostic=evaluate(view,'window.neuralMemoryDiagnostics?.()')
            checks['awaiting_has_no_fake_fragments']=diagnostic['awaitingTopic'] and diagnostic['items']==0
            checks['awaiting_status_visible']=evaluate(view,'Boolean(document.querySelector(".neural-status:not([hidden])"))') is True
            window.grab().save(str(output/'awaiting-subject.png'))
            owner._fish_voice.reset_mock();phrase='sobre a Forja'
            checks['subject_answer_routed']=asyncio.run(owner._route_protocol_user_once(phrase)) is True
            checks['subject_answer_uses_real_records']=wait(lambda:evaluate(view,'window.neuralMemoryDiagnostics?.()')['items']==3,10)
            checks['clarification_ends_on_answer']=evaluate(view,'window.neuralMemoryDiagnostics?.().awaitingTopic') is False
            spoken=' '.join(call.args[0] for call in owner._fish_voice.feed.call_args_list)
            checks['followup_relevant_speech']='biblioteca' in spoken and 'Spotify' not in spoken and 'agenda' not in spoken
            window._cancel_neural_memory()
            checks['followup_returns_to_core']=wait(lambda:evaluate(view,'window.neuralMemoryDiagnostics?.()')['progress']==0,10)
            phrase='Quero que voce busque na lembranca algo sobre musica que eu falei.'
            checks['no_results_voice_request_routed']=asyncio.run(owner._route_protocol_user_once(phrase)) is True
            checks['no_results_still_forms_brain']=wait(lambda:evaluate(view,'window.neuralMemoryDiagnostics?.()')['progress']>=.99,10)
            diagnostic=evaluate(view,'window.neuralMemoryDiagnostics?.()')
            checks['no_results_has_honest_status']=diagnostic['outcome']=='empty' and diagnostic['items']==0 and evaluate(view,'document.querySelector(".neural-status")?.textContent')=='Nenhuma lembranca relevante encontrada'
            window.grab().save(str(output/'no-results-brain.png'))
            checks['no_results_returns_automatically']=wait(lambda:evaluate(view,'window.neuralMemoryDiagnostics?.()')['progress']==0,12)
            evaluate(view,"window.__fullCoreUpdate=window.updateCore;window.updateCore=value=>window.__fullCoreUpdate({...value,motion:'reduced',phase:'idle'});window.updateCore({motion:'reduced',phase:'idle',visible:true});window.updateNeuralMemory({requestId:'reduced-outcome',pending:true});window.updateNeuralMemory({requestId:'reduced-outcome',active:true,items:[],outcome:'empty',depth:'quick'});")
            checks['reduced_outcome_forms_without_motion']=evaluate(view,'window.neuralMemoryDiagnostics?.().progress')==1 and evaluate(view,'document.body.dataset.motion')=='reduced'
            checks['reduced_outcome_expires_without_state_updates']=wait(lambda:evaluate(view,'window.neuralMemoryDiagnostics?.()')['progress']==0,12)
            checks['repeated_retrieval_keeps_gpu_resources']=evaluate(view,"(()=>{const before=hologramDiagnostics();for(let i=0;i<12;i++){updateNeuralMemory({requestId:'cycle-'+i,pending:true});updateNeuralMemory({requestId:'cycle-'+i,active:true,outcome:'empty',items:[],depth:'quick'});cancelNeuralMemory();}const after=hologramDiagnostics();return before.geometries===after.geometries&&before.textures===after.textures&&!neuralMemoryDiagnostics().active;})()") is True
            checks['no_callback_errors']=not errors
        finally:
            if args.projects:lookup_patch.stop()
            window.close();app.processEvents()
    passed=all(value is True for key,value in checks.items() if key!='real_fragments')
    report={'passed':passed,'checks':checks,'formation_seconds':formation_seconds,'errors':errors,'output':str(output)}
    (output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps(report,ensure_ascii=False),flush=True)
    return 0 if passed else 1

if __name__=='__main__':sys.exit(main())
