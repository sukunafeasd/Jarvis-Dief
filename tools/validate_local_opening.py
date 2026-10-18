"""Captura a janela real com WebEngine e perfil descartavel, sem iniciar a IA."""
import argparse
import json
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch
from contextlib import ExitStack
from PyQt6.QtCore import QTimer,qInstallMessageHandler
from PyQt6.QtWidgets import QApplication

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import ui


def main():
    qInstallMessageHandler(lambda kind,context,message:print('Qt: '+message,file=sys.stderr,flush=True))
    parser=argparse.ArgumentParser();parser.add_argument('--setup',action='store_true')
    parser.add_argument('--width',type=int,default=1920);parser.add_argument('--height',type=int,default=1080)
    parser.add_argument('--resize',action='store_true')
    args=parser.parse_args()
    app=QApplication([sys.argv[0]]);app.setStyle('Fusion')
    print('Aplicacao de teste criada.',flush=True)
    output=ROOT/'validation'/('local-setup' if args.setup else f'local-opening-{args.width}')
    output.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory() as directory:
        config=Path(directory)/'profile.json'
        settings={'hud_style':'core','reduce_motion':False}
        if not args.setup:settings.update(gemini_api_key='synthetic-no-network-test',os_system='windows')
        config.write_text(json.dumps(settings))
        with ExitStack() as stack:
            stack.enter_context(patch.object(ui,'API_FILE',config))
            stack.enter_context(patch('memory.config_manager.CONFIG_FILE',config))
            stack.enter_context(patch.object(ui.MainWindow,'_verify_saved_connections'))
            window=ui.MainWindow(str(ROOT/'core/face_model.obj'))
            print('Janela de teste criada.',flush=True)
            window._ui_sounds.enabled=False
            window.resize(args.width,args.height);window.showFullScreen()
            print('Janela de teste apresentada.',flush=True)
            started=time.monotonic();records=[];index=0
            if args.resize:
                QTimer.singleShot(7000,lambda:(window.showNormal(),window.resize(args.width,args.height)))
                QTimer.singleShot(9500,window.showFullScreen)
            def capture():
                nonlocal index
                seconds=round(time.monotonic()-started,3)
                stage=window._scene_stage.rect()
                record={'seconds':seconds,'stage':[stage.width(),stage.height()],
                    'started':window._environment.started,'core_hidden':not window._center_split.isVisible(),
                    'veil':bool(window._opening_veil and window._opening_veil.isVisible()),
                    'veil_size':[window._opening_veil.width(),window._opening_veil.height()] if window._opening_veil else None}
                if window._space_view:
                    record['space_loaded']=window._space_view._loaded
                    record['space_ready']=window._space_view._ready
                    record['space_failed']=window._space_view.failed
                    record['space_size']=[window._space_view.width(),window._space_view.height()]
                    window._space_view.page().runJavaScript('window.spaceDiagnostics&&window.spaceDiagnostics()',lambda value,r=record:r.update(space=value))
                core=window.hud._spatial_core
                if core:
                    record['core_loaded']=core._loaded
                    record['core_ready']=core._ready
                    record['core_failed']=core.failed
                    record['core_size']=[core.width(),core.height()]
                    core.page().runJavaScript('window.hologramDiagnostics&&window.hologramDiagnostics()',lambda value,r=record:r.update(core=value))
                records.append(record)
                window.grab().save(str(output/f'frame-{index:03d}.jpg'),'JPEG',85);index+=1
                if seconds<30:QTimer.singleShot(350,capture)
                else:
                    valid=all(r['veil_size']==r['stage'] for r in records if r['veil'])
                    valid=valid and all(r['space_size']==r['stage'] for r in records if 'space_size' in r)
                    if args.setup:valid=valid and all(r['core_hidden'] and not r['started'] for r in records)
                    else:
                        diagnostics=[r['core'] for r in records if isinstance(r.get('core'),dict)]
                        valid=valid and bool(diagnostics) and diagnostics[-1]['coreVisible'] and diagnostics[-1]['travel']==0
                    (output/'result.json').write_text(json.dumps({'passed':bool(valid),'records':records},indent=2))
                    print(json.dumps({'passed':bool(valid),'frames':len(records),'output':str(output)}),flush=True)
                    window.close();QTimer.singleShot(50,lambda:app.exit(0 if valid else 1))
            QTimer.singleShot(0,capture)
            code=app.exec()
            return code


if __name__=='__main__':sys.exit(main())
