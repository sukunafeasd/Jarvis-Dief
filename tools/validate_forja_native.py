"""Real native FORJA QA, isolated data and fixture runtime; no Live or accounts.

Run with the project's Python on a Windows desktop. Outputs report.json, native
PNG frames, and sequence.gif in a temporary directory. Exit 1 means a contract
failed, not permission to change production modules.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
from contextlib import ExitStack
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class MockRuntime:
    def __init__(self, snapshot):
        self.value = snapshot
        self.calls = []
        self.closed = False

    def snapshot(self):
        return copy.deepcopy(self.value)

    def command(self, action, **kwargs):
        self.calls.append({'action': action, **kwargs})
        return {'ok': True}

    def close(self):
        self.closed = True


FIXTURE = '''<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1">
<style>html,body{margin:0;background:#000;overflow:hidden}canvas{display:block}</style></head>
<body><canvas id="canvas"></canvas><script>
const canvas=document.querySelector('canvas'),ctx=canvas.getContext('2d');let frames=0;
let parentAccess=false;try{parent.document.body.dataset.fixtureBreach='yes';parentAccess=true}catch(e){}
const qtAccess=typeof qt!=='undefined'||typeof QWebChannel!=='undefined';
function draw(t){canvas.width=innerWidth;canvas.height=innerHeight;ctx.fillStyle='#000';ctx.fillRect(0,0,innerWidth,innerHeight);
ctx.strokeStyle='#00ff88';ctx.lineWidth=4;ctx.beginPath();ctx.ellipse(innerWidth/2,innerHeight/2,Math.min(innerWidth,innerHeight)*.28,55+Math.sin(t/450)*24,.25,0,Math.PI*2);ctx.stroke();
frames++;requestAnimationFrame(draw)}requestAnimationFrame(draw);
addEventListener('message',e=>{if(e.data==='fixture-probe')parent.postMessage({type:'fixture-proof',parentAccess,qtAccess,frames},'*')});
</script></body></html>'''


def main():
    if os.name != 'nt' or os.environ.get('QT_QPA_PLATFORM') == 'offscreen':
        print('Native validation requires a Windows desktop, not offscreen Qt.', flush=True)
        return 2
    output = Path(tempfile.mkdtemp(prefix='dief-forja-native-'))
    os.environ['DIEF_JARVIS_DATA_DIR'] = str(output / 'data')
    # Set the override before importing any module that resolves user storage.
    from PyQt6.QtCore import QTimer, Qt, QPoint
    from PyQt6.QtTest import QTest
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEngineUrlRequestInterceptor
    from PIL import Image, ImageChops
    import ui
    from core.forge.preview import PreviewServer

    app = QApplication.instance() or QApplication([sys.argv[0]])
    app.setQuitOnLastWindowClosed(False)
    app.setStyle('Fusion')
    report = {'checks': [], 'trace': [], 'exceptions': [], 'output': str(output), 'profile': str(output / 'data')}
    previous_hook = sys.excepthook
    sys.excepthook = lambda kind, value, tb: report['exceptions'].append(f'{kind.__name__}: {value}')
    server = PreviewServer()
    fixture = output / 'fixture'
    fixture.mkdir()
    artifact = fixture / 'artifact.html'
    artifact.write_text(FIXTURE, encoding='utf-8')
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    url = server.publish(fixture, {'artifact.html': digest}, 'artifact.html')
    report['fixture'] = {'sha256': digest, 'server': 'PreviewServer', 'port': server.server.server_port}

    class LocalOnly(QWebEngineUrlRequestInterceptor):
        def interceptRequest(self, info):
            target = info.requestUrl()
            if target.scheme() in ('file', 'qrc', 'data', 'blob', 'about'):
                return
            if target.scheme() == 'http' and target.host() == '127.0.0.1' and target.port() == server.server.server_port:
                return
            info.block(True)

    interceptor = LocalOnly()
    profile = QWebEngineProfile.defaultProfile()
    profile.setUrlRequestInterceptor(interceptor)
    profile.setCachePath(str(output / 'web-cache'))
    profile.setPersistentStoragePath(str(output / 'web-storage'))

    def check(name, ok, detail=None):
        record = {'name': name, 'passed': bool(ok), 'detail': detail}
        report['checks'].append(record)
        print(json.dumps(record, ensure_ascii=True), flush=True)

    def wait(predicate, timeout=3):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            app.processEvents()
            if predicate():
                return True
            QTest.qWait(15)
        return bool(predicate())

    def js(view, expression, timeout=2):
        if view is None:
            return None
        result = []
        view.page().runJavaScript(expression, lambda value: result.append(value))
        return result[0] if wait(lambda: bool(result), timeout) else None

    frames = []
    window = None
    observer = None
    try:
        # Verify read-only immutable publication through its actual handler.
        with urlopen(url, timeout=2) as response:
            check('fixture_hash', hashlib.sha256(response.read()).hexdigest() == digest)
            check('fixture_sandbox_header', 'sandbox allow-scripts' in response.headers.get('Content-Security-Policy', ''))
        try:
            urlopen(Request(url, data=b'no writes', method='POST'), timeout=2)
            check('fixture_read_only', False)
        except HTTPError as error:
            check('fixture_read_only', error.code == 501, error.code)

        config = output / 'profile.json'
        settings = {'hud_style': 'core', 'reduce_motion': False, 'mute_panel_sounds': True, 'os_system': 'windows'}
        config.write_text(json.dumps(settings), encoding='utf-8')
        with ExitStack() as stack:
            for target, value in [('ui.API_FILE', config), ('memory.config_manager.CONFIG_FILE', config),
                                  ('core.profile.CONFIG', config), ('core.integration_tokens.ROOT', output / 'data'),
                                  ('core.gmail_connection.TOKEN', output / 'data/gmail.bin'),
                                  ('core.gmail_connection.CREDENTIALS', output / 'data/oauth.json'),
                                  ('core.whatsapp_web.PROFILE', output / 'data/whatsapp'),
                                  ('memory.memory_manager.MEMORY_PATH', output / 'data/memory.json')]:
                stack.enter_context(patch(target, value))
            stack.enter_context(patch.object(ui.MainWindow, '_check_config', return_value=True))
            stack.enter_context(patch.object(ui.MainWindow, '_verify_saved_connections'))
            stack.enter_context(patch('core.ui_sounds.SoundDirector.play'))
            stack.enter_context(patch('core.ui_sounds.SoundDirector.scene'))
            stack.enter_context(patch('core.forge.Runtime', side_effect=AssertionError('Real runtime forbidden in native QA')))
            window = ui.MainWindow(str(ROOT / 'core/face_model.obj'))
            window._ui_sounds.enabled = False
            runtime = MockRuntime({'phase': 'validating', 'authenticated': False, 'project': {'name': 'Fixture nativa'},
                'activities': [{'id': 'fixture', 'title': 'File changes', 'detail': 'artifact.html (fixture)', 'status': 'done'}],
                'preview_url': url, 'preview_version': digest})
            window._forge_runtime = runtime
            commands = []
            window.on_forge_command = lambda value: commands.append(value)
            window.showFullScreen()
            boot = wait(lambda: window.hud._spatial_core is not None and window.hud._spatial_core._ready
                        and window._space_view is not None and window._space_view._ready
                        and window._opening_veil.released, 25)
            check('native_boot', boot)
            report['screen'] = {'geometry': app.primaryScreen().geometry().getRect(), 'window': window.size().width()}
            if not boot:
                raise RuntimeError('Native renderers did not pass health checks')
            QTest.qWait(5000)
            core = window.hud._spatial_core
            window._pin_data({'kind': 'weather', 'title': 'Fixture clima', 'temperature': 23, 'city': 'Teste'})
            window._pin_data({'kind': 'calendar', 'title': 'Fixture agenda', 'items': [{'title': 'Teste local'}]})
            window._content_panel.hide()
            window._layout_scene()
            QTest.qWait(300)
            saved_pins = copy.deepcopy(window._pin_store.load())
            pin_visibility = {key: pin['widget'].isVisible() for key, pin in window._pin_previews.items()}
            original_geometry = window._center_split.geometry().getRect()
            ordinary = {name: getattr(window, name).isVisible() for name in ('_floating_controls','_title_lbl','_clock_lbl','_date_lbl')}
            check('pins_fixture_persisted', len(saved_pins) == 2, pin_visibility)
            core_start = js(core, 'window.forgeTransitionDiagnostics()')
            observations = {'black': [], 'light': [], 'ready': [], 'core_geometry': []}

            def capture(label):
                path = output / f'{len(frames):04d}-{label}.png'
                window._scene_stage.grab().save(str(path))
                frames.append(path)
                with Image.open(path) as img:
                    extrema = img.convert('RGB').getextrema()
                    return {'frame': path.name, 'extrema': extrema, 'black': all(pair == (0, 0) for pair in extrema)}

            in_flight = set()
            def sample_view(view, role):
                if view is None or role in in_flight:
                    return
                in_flight.add(role)
                def received(value):
                    in_flight.discard(role)
                    if not isinstance(value, dict):
                        return
                    value['role'] = role
                    value['native'] = window._forge_controller.phase
                    value['at'] = round(time.monotonic() - started, 3)
                    report['trace'].append(value)
                    if role == 'core' and value.get('phase') == 'entering_core' and not observations['core_geometry']:
                        observations['core_geometry'].append({'core': core.geometry().getRect(), 'hud': window.hud.rect().getRect(),
                            'stage': window._scene_stage.rect().getRect(), 'split': window._center_split.geometry().getRect(),
                            'diagnostics': value, 'pixels': capture('travelling')})
                    if role == 'forge' and value.get('phase') == 'panel_emerging' and value.get('lightOpacity', 0) > .05 and not observations['light']:
                        observations['light'].append(capture('light'))
                    if role == 'forge' and value.get('phase') == 'ready' and not observations['ready']:
                        observations['ready'].append(capture('ready'))
                expression = ('({phase:window.forgeTransitionPhase,diag:window.forgeTransitionDiagnostics?.(),error:document.body.dataset.error})'
                    if role == 'core' else '({phase:window.forgeScenePhase,ready:window.forgeReady,hidden:document.hidden,diag:window.forgeDiagnostics?.(),lightOpacity:Number(getComputedStyle(document.getElementById("entranceLight")).opacity)})')
                view.page().runJavaScript(expression, received)

            started = time.monotonic()
            def observe():
                controller = window._forge_controller
                if controller:
                    if controller.phase == 'blackout' and controller.view.isVisible() and time.monotonic() >= controller._black_until - .12 and not observations['black']:
                        observations['black'].append(capture('blackout'))
                    sample_view(core, 'core')
                    sample_view(controller.view, 'forge')
            observer = QTimer()
            observer.setInterval(35)
            observer.timeout.connect(observe)
            observer.start()

            def request(action):
                packet = {'action': action, 'done': threading.Event()}
                window._apply_forge_request(packet)
                return packet

            def completed(packet, timeout):
                return wait(packet['done'].is_set, timeout)

            window._update_neural_memory({'requestId':'before-forge','pending':True})
            window._update_neural_memory({'requestId':'before-forge','active':True,'awaitingTopic':True,'items':[],'depth':'quick'})
            check('neural_fixture_visible_before_entry',wait(lambda:(js(core,'window.neuralMemoryDiagnostics()') or {}).get('progress',0)>=.99,6))
            entering = request('enter')
            completed(entering, 28)
            wait(lambda: bool(observations['ready']), 1)
            check('enter_request_ready', entering.get('result', {}).get('ok') and entering.get('result', {}).get('phase') == 'ready', entering.get('result'))
            controller = window._forge_controller
            check('neural_settled_before_forge',window._neural_request is None and not (js(core,'window.neuralMemoryDiagnostics()') or {}).get('active'))
            report['observations'] = observations
            check('all_black_stage', bool(observations['black']) and observations['black'][0]['black'], observations['black'])
            check('white_light_panel_sequence', bool(observations['light']) and bool(observations['ready']), observations)
            geometry = observations['core_geometry'][0] if observations['core_geometry'] else {}
            check('full_stage_actual_core', bool(geometry) and geometry['core'][2:] == geometry['stage'][2:], geometry)

            if controller.phase == 'ready':
                wait(lambda: bool(js(controller.view, 'window.forgeDiagnostics()?.previewActive')), 5)
                snapshot_diag = js(controller.view, '({diag:window.forgeDiagnostics(),text:document.getElementById("stepsContainer").innerText,sandbox:document.querySelector("iframe")?.getAttribute("sandbox")})')
                check('snapshot_fixture_projection', snapshot_diag and 'artifact.html' not in snapshot_diag['text'] and snapshot_diag['diag']['activities'] == 1, snapshot_diag)
                js(controller.view, '''window.fixtureProof=null;window.fixtureMessages=[];addEventListener('message',e=>{window.fixtureMessages.push({type:e.data?.type,sameSource:e.source===document.querySelector('iframe')?.contentWindow});if(e.data?.type==='fixture-proof')window.fixtureProof=e.data});''')
                def probe():
                    js(controller.view, "document.querySelector('iframe')?.contentWindow.postMessage('fixture-probe','*')")
                    proof=js(controller.view, 'window.fixtureProof')
                    return bool(proof and proof.get('frames',0)>0)
                wait(probe, 4)
                proof = js(controller.view, 'window.fixtureProof')
                check('artifact_no_qt_or_parent_access', proof and not proof['qtAccess'] and not proof['parentAccess'] and proof['frames'] > 0 and snapshot_diag['sandbox'] == 'allow-scripts', proof)
                first = capture('preview-a'); QTest.qWait(300); second = capture('preview-b')
                with Image.open(output / first['frame']) as a, Image.open(output / second['frame']) as b:
                    check('fixture_pixels_animate', ImageChops.difference(a.convert('RGB'), b.convert('RGB')).getbbox() is not None)
                check('pins_hidden_in_forge', all(not pin['widget'].isVisible() for pin in window._pin_previews.values()))
                js(controller.view, 'document.getElementById("forgePrompt").focus()')
                controller.view.setFocus()
                focused = app.focusWidget() or controller.view.focusProxy() or controller.view
                before = window.isFullScreen()
                QTest.keyClick(focused, Qt.Key.Key_F11)
                wait(lambda: window.isFullScreen() != before, 3)
                check('f11_focused_view', window.isFullScreen() != before)
                QTest.qWait(250)
                focused = app.focusWidget() or controller.view
                QTest.keyClick(focused, Qt.Key.Key_F11)
                wait(lambda: window.isFullScreen() == before, 3)
                check('f11_restore_and_resize', window.isFullScreen() == before and controller.view.geometry() == window._scene_stage.rect())
                js(controller.view, 'document.getElementById("forgePrompt").value="Fixture comando";document.getElementById("promptForm").requestSubmit()')
                wait(lambda: bool(commands), 2)
                check('native_command_hash', bool(commands) and commands[-1] == {'action':'prompt','prompt':'Fixture comando'}, commands)
                exiting = request('exit'); completed(exiting, 15)
                check('exit_request_normal', exiting.get('result', {}).get('ok') and controller.phase == 'normal', exiting.get('result'))
                QTest.qWait(800)
                check('pins_restored_persistent', window._pin_store.load() == saved_pins and all(window._pin_previews[key]['widget'].isVisible() == value for key, value in pin_visibility.items()))
                check('native_geometry_restored', window._center_split.geometry().getRect() == original_geometry, {'before': original_geometry,'after': window._center_split.geometry().getRect()})
                check('ordinary_visibility_restored', all(getattr(window, name).isVisible() == value for name, value in ordinary.items()))
                check('core_health_after_exit', not core.failed and js(core, 'window.forgeTransitionPhase') == 'normal')
                check('preview_disposed_after_exit', not (js(controller.view, 'window.forgeDiagnostics()') or {}).get('previewActive'))

                settings['reduce_motion'] = True
                config.write_text(json.dumps(settings), encoding='utf-8')
                QTest.qWait(1200)
                again = request('enter'); completed(again, 6)
                check('repeat_reduced_entry', again.get('result', {}).get('ok') and controller.phase == 'ready', again.get('result'))
                repeat_diag = js(controller.view, 'window.forgeDiagnostics()')
                check('repeat_snapshot_and_preview', repeat_diag and repeat_diag.get('previewActive') and repeat_diag.get('activities') == 1, repeat_diag)
                end = request('exit'); completed(end, 6)
                check('repeat_reduced_exit', end.get('result', {}).get('ok') and controller.phase == 'normal', end.get('result'))
                recovery_entry=request('enter');completed(recovery_entry,6)
                from main import JarvisLive
                from types import SimpleNamespace
                assistant=JarvisLive.__new__(JarvisLive);assistant._loop=None;assistant._forge_mode=True
                assistant.ui=SimpleNamespace(_win=window)
                window.on_forge_scene_failure=assistant._on_forge_scene_failure
                controller._command_serial=9
                controller._renderer_failed()
                check('renderer_failure_restores_routing',controller.phase=='normal' and not assistant._forge_mode)
                recovered=request('enter');completed(recovered,8)
                check('failed_view_reloads',recovered.get('result',{}).get('ok') and controller.phase=='ready' and controller._command_serial==-1)
                previous_commands=len(commands)
                js(controller.view,'document.getElementById("forgePrompt").value="Fixture recuperada";document.getElementById("promptForm").requestSubmit()')
                check('first_command_after_recovery_accepted',wait(lambda:len(commands)>previous_commands,2) and commands[-1]=={'action':'prompt','prompt':'Fixture recuperada'})
                recovery_exit=request('exit');completed(recovery_exit,6)
                check('recovery_returns_normally',recovery_exit.get('result',{}).get('ok') and controller.phase=='normal')
            else:
                check('native_scenarios_blocked_by_entry', False, {'phase': controller.phase, 'core': js(core, 'window.forgeTransitionDiagnostics()'), 'forge': js(controller.view, 'window.forgeDiagnostics()')})

            # Cancel while preparing/travelling, including outstanding ready callbacks.
            settings['reduce_motion'] = False
            config.write_text(json.dumps(settings), encoding='utf-8')
            QTest.qWait(1200)
            cancel_entry = request('enter')
            QTest.qWait(450)
            cancel_exit = request('exit')
            completed(cancel_exit, 15)
            check('timed_cancel_events', cancel_entry['done'].is_set() and cancel_entry.get('result', {}).get('cancelled')
                  and cancel_exit.get('result', {}).get('ok') and controller.phase == 'normal', {'entry': cancel_entry.get('result'),'exit': cancel_exit.get('result')})
            QTest.qWait(1000)
            check('cancel_no_late_callbacks', controller.phase == 'normal' and js(core, 'window.forgeTransitionPhase') == 'normal', js(core, 'window.forgeTransitionDiagnostics()'))
            check('cancel_pins_restored', window._pin_store.load() == saved_pins and all(window._pin_previews[key]['widget'].isVisible() == value for key,value in pin_visibility.items()))
            report['runtime_calls'] = runtime.calls
            report['initial_core'] = core_start
            capture('final-restored')
            observer.stop()
            window.close()
            QTest.qWait(300)
            window.deleteLater()
            app.processEvents()
    except Exception as error:
        report['exceptions'].append(f'{type(error).__name__}: {error}')
        check('harness_completed', False, str(error))
    finally:
        if observer:
            observer.stop()
        if window:
            window.close()
            app.processEvents()
        server.close()
        sys.excepthook = previous_hook
        profile.setUrlRequestInterceptor(None)
        if frames:
            images = []
            for path in frames:
                with Image.open(path) as img:
                    thumb = img.convert('RGB'); thumb.thumbnail((960, 540)); images.append(thumb.copy())
            images[0].save(output / 'sequence.gif', save_all=True, append_images=images[1:], duration=500, loop=0)
        report['passed'] = bool(report['checks']) and all(record['passed'] for record in report['checks']) and not report['exceptions']
        (output / 'report.json').write_text(json.dumps(report, indent=2, ensure_ascii=True), encoding='utf-8')
        print(json.dumps({'passed': report['passed'], 'report': str(output / 'report.json'), 'output': str(output)}), flush=True)
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
