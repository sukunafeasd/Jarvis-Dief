"""Real native startup with isolated data, no assistant/provider session."""
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from contextlib import ExitStack
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--setup',action='store_true')
    parser.add_argument('--windowed',action='store_true');args=parser.parse_args()
    output=Path(tempfile.mkdtemp(prefix='dief-native-opening-'))
    os.environ['DIEF_JARVIS_DATA_DIR']=str(output/'data')
    os.environ.pop('QT_QPA_PLATFORM',None)
    from PyQt6.QtWidgets import QApplication
    import ui
    app=QApplication([sys.argv[0]]);app.setQuitOnLastWindowClosed(False);app.setStyle('Fusion')
    print('Native opening: application ready',flush=True)
    errors=[]
    def exception(kind,value,tb):
        import traceback
        errors.append(str(value));traceback.print_exception(kind,value,tb)
    sys.excepthook=exception
    config=output/'profile.json'
    settings={'hud_style':'core','reduce_motion':False,'panel_sounds_enabled':False}
    if not args.setup:settings.update(gemini_api_key='synthetic-no-provider',os_system='windows')
    config.write_text(json.dumps(settings))

    def wait(predicate,seconds):
        end=time.monotonic()+seconds
        while time.monotonic()<end:
            app.processEvents()
            if predicate():return True
            time.sleep(.005)
        return False

    def evaluate(view,expression):
        result=[]
        view.page().runJavaScript(expression,result.append)
        if not wait(lambda:bool(result),3):raise TimeoutError('WebEngine diagnostics callback')
        return result[0]

    records=[];checks=[]
    def check(name,value):checks.append({'name':name,'passed':bool(value)})
    with ExitStack() as stack:
        stack.enter_context(patch.object(ui,'API_FILE',config))
        stack.enter_context(patch('memory.config_manager.CONFIG_FILE',config))
        stack.enter_context(patch.object(ui.MainWindow,'_verify_saved_connections'))
        print('Native opening: creating window',flush=True)
        window=ui.MainWindow(str(ROOT/'core/face_model.obj'))
        print('Native opening: window ready',flush=True)
        window._ui_sounds.enabled=False
        window.resize(1280,800)
        window.show() if args.windowed else window.showFullScreen()
        start=time.monotonic();last_shot=-1;first_visible=None;entrance_id=None
        try:
            while time.monotonic()-start<35:
                app.processEvents()
                core=window.hud._spatial_core;space=window._space_view
                record={'seconds':round(time.monotonic()-start,3),'started':window._environment.started,
                    'veil':window._opening_veil.isVisible(),'layoutReady':window._scene_layout_ready}
                if core and core._loaded:record['core']=evaluate(core,'window.hologramDiagnostics?.()')
                if space and space._loaded:record['world']=evaluate(space,'({space:window.spaceDiagnostics?.(),planet:window.ultronDiagnostics?.(),error:document.body.dataset.error})')
                records.append(record)
                if window._environment.entrance:
                    if entrance_id is None:entrance_id=dict(window._environment.entrance)
                    check('same_entrance',entrance_id==window._environment.entrance)
                if time.monotonic()-start-last_shot>.25:
                    window.grab().save(str(output/f'frame-{len(records):03d}.png'));last_shot=time.monotonic()-start
                if record['started'] and not record['veil'] and first_visible is None:
                    first_visible=record
                    window.grab().save(str(output/'first-real-scene.png'))
                    check('first_real_core',record.get('core',{}).get('coreVisible'))
                    world=record.get('world') or {};planet=world.get('planet') or {};solar=world.get('space') or {}
                    check('first_scene_complete',planet.get('frames',0)>0 and solar.get('pendingMaps')==0 and solar.get('solarVisible'))
                    check('first_scene_still_distant',record.get('core',{}).get('travel',0)>20)
                if args.setup and record['seconds']>8:
                    check('setup_does_not_start',not record['started'] and window._overlay.isVisible() and not window._center_split.isVisible());break
                if first_visible and (record.get('core') or {}).get('travel')==0:
                    window.grab().save(str(output/'arrival.png'));break
                time.sleep(.025)
            if not args.setup:
                check('scene_revealed',first_visible is not None)
                travelling=[r for r in records if (r.get('core') or {}).get('coreVisible') and r['started']]
                check('arrival_completed',bool(travelling) and travelling[-1]['core']['travel']==0)
                planets=[r['world']['planet'] for r in travelling if (r.get('world') or {}).get('planet')]
                check('planet_world_fixed',bool(planets) and all(p['worldPosition']==planets[0]['worldPosition'] and p['worldScale']==planets[0]['worldScale'] for p in planets))
                check('planet_camera_travel',bool(planets) and planets[0]['camera'][2]-planets[-1]['camera'][2]>18)
                check('no_core_swap',bool(travelling) and len({r['core']['geometries'] for r in travelling})==1)
            check('no_callback_errors',not errors)
        finally:
            window.close();app.processEvents()
    passed=bool(checks) and all(c['passed'] for c in checks)
    (output/'report.json').write_text(json.dumps({'passed':passed,'checks':checks,'errors':errors,'records':records},indent=2))
    print(json.dumps({'passed':passed,'checks':[c for c in checks if c['name']!='same_entrance'],'output':str(output)}))
    return 0 if passed else 1


if __name__=='__main__':sys.exit(main())
