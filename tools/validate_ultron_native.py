"""Real Qt/WebEngine bridge with synthetic readings and an isolated profile."""
import json
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch
from contextlib import ExitStack
from types import SimpleNamespace
import copy

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
DATA=Path(tempfile.mkdtemp(prefix='dief-ultron-native-'))
os.environ['DIEF_JARVIS_DATA_DIR']=str(DATA/'data')
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
import ui

def main():
    config=DATA/'profile.json';config.write_text(json.dumps({'hud_style':'core','reduce_motion':False,'gemini_api_key':'synthetic-no-network-test','os_system':'windows'}))
    app=QApplication([sys.argv[0]])
    with ExitStack() as stack:
        stack.enter_context(patch.object(ui,'API_FILE',config));stack.enter_context(patch('memory.config_manager.CONFIG_FILE',config))
        stack.enter_context(patch.object(ui.MainWindow,'_verify_saved_connections'))
        window=ui.MainWindow(str(ROOT/'core/face_model.obj'));window._ui_sounds.enabled=False;window.resize(1280,800);window.show()
        records={};failed=[]
        poll_test='--poll' in sys.argv
        def narrate():
            window._narrate_presentation({'text':'CPU em 17 por cento. Memoria em 43 por cento. Disco em 52 por cento.','at':0})
            window._advance_presentation(.5)
            for index in range(20):QTimer.singleShot((index+1)*160,lambda:window._advance_presentation(.16))
        def completed(state):
            records['completion_callbacks']=records.get('completion_callbacks',0)+1
            window._show_ultron({'state':state,'result':{'mode':'diagnostic'}})
            narrate()
        window.on_ultron_ready=completed
        def activate():
            try:
                window._space_view.page().runJavaScript('window.ultronDiagnostics?.()',lambda data:records.update(before=data))
                state={'phase':'active','snapshot_serial':1,'last_user_turn':1,'scan':{'running':False,'progress':100,'stage':'complete','finished_at':'synthetic-completion'},'telemetry':{'cpu_percent':17,'memory_percent':43,'disk_percent':52},'findings':[]}
                if poll_test:
                    def snapshot():
                        state['snapshot_serial']+=1
                        return copy.deepcopy(state)
                    window._ultron_runtime=SimpleNamespace(snapshot=snapshot,close=lambda:None)
                    first={**state,'phase':'scanning','scan':{'running':True,'progress':14.3,'stage':'defender'}}
                    window._show_ultron({'state':first,'result':{'mode':'activation'}})
                else:
                    window._show_ultron({'state':state,'result':{'mode':'diagnostic'}})
                    narrate()
            except Exception as error:failed.append(str(error))
        def capture():
            window.grab().save(str(DATA/'active.png'))
            records['core_hidden']=not window._center_split.isVisible()
            if window._space_view:
                window._space_view.page().runJavaScript('({planet:window.ultronDiagnostics?.(),space:window.spaceDiagnostics?.(),projection:document.getElementById("ultron-projection").innerText,error:document.body.dataset.ultronError})',lambda data:records.update(bridge=data))
        def restore():
            window._show_ultron({'state':{'phase':'idle'},'result':{'mode':'deactivation'}})
        def finish():
            records['core_restored']=window._center_split.isVisible()
            bridge=records.get('bridge') or {}
            planet=bridge.get('planet') or {};before=records.get('before') or {};after=records.get('after') or {}
            camera=planet.get('camera') or [0,0,99]
            records['focus_verified']=camera[2]<-5 and abs(camera[2]-bridge.get('space',{}).get('camera',{}).get('z',99))<.001
            records['world_fixed']=planet.get('worldPosition')==before.get('worldPosition')==after.get('worldPosition')
            records['camera_returned']=abs((after.get('camera') or [0,0,99])[2]-3)<.001
            records['poll_completed']=not poll_test or (records.get('completion_callbacks')==1 and (window._ultron_payload or {}).get('state',{}).get('phase')=='idle')
            valid=records.get('core_hidden') and records['core_restored'] and records['focus_verified'] and records['world_fixed'] and records['camera_returned'] and planet.get('phase')=='active' and '17%' in bridge.get('projection','') and 'CPU em 17 por cento.' in bridge.get('projection','') and not bridge.get('error') and not failed
            valid=valid and records['poll_completed']
            print(json.dumps({'passed':bool(valid),'records':records,'errors':failed,'output':str(DATA)}),flush=True)
            window.close();QTimer.singleShot(100,lambda:app.exit(0 if valid else 1))
        def returned():
            window._space_view.page().runJavaScript('window.ultronDiagnostics?.()',lambda data:records.update(after=data))
        QTimer.singleShot(10000,activate);QTimer.singleShot(14000,capture);QTimer.singleShot(16000,restore);QTimer.singleShot(19000,returned);QTimer.singleShot(20000,finish)
        return app.exec()

if __name__=='__main__':sys.exit(main())
