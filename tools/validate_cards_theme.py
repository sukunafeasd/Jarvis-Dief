"""Native visual QA with disposable profiles and synthetic data only."""
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch
from contextlib import ExitStack
from PyQt6.QtCore import QTimer,Qt,qInstallMessageHandler
from PyQt6.QtWidgets import QApplication
from PyQt6.QtTest import QTest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import ui


def main():
    qInstallMessageHandler(lambda kind,context,message:print('Qt: '+message,file=sys.stderr,flush=True))
    app=QApplication([sys.argv[0]]);app.setStyle('Fusion')
    app.setQuitOnLastWindowClosed(False)
    output=ROOT/'validation/free-pins-theme';output.mkdir(parents=True,exist_ok=True)
    result={};failure=[]
    with tempfile.TemporaryDirectory() as folder,ExitStack() as stack:
        root=Path(folder);config=root/'profile.json'
        config.write_text(json.dumps({'hud_style':'core','gemini_api_key':'synthetic-no-network-test','os_system':'windows'}))
        for target,value in [('ui.API_FILE',config),('memory.config_manager.CONFIG_FILE',config),
            ('core.profile.CONFIG',config),('core.integration_tokens.ROOT',root),
            ('core.gmail_connection.TOKEN',root/'gmail.bin'),('core.gmail_connection.CREDENTIALS',root/'oauth.json'),
            ('core.whatsapp_web.PROFILE',root/'whatsapp'),('memory.memory_manager.MEMORY_PATH',root/'memory.json')]:
            stack.enter_context(patch(target,value))
        stack.enter_context(patch.object(ui.MainWindow,'_verify_saved_connections'))
        window=ui.MainWindow(str(ROOT/'core/face_model.obj'));window._ui_sounds.enabled=False
        window.resize(1200,800);window.showFullScreen();window.activateWindow()
        weather={'kind':'weather','temperature':19,'city':'Cidade de teste','condition':'Chuva leve','code':61,'rain':78,'wind':14,'humidity':82,'narrationDriven':False}
        cases=[weather,{'kind':'tasks','count':3,'title':'Tarefas','items':[{'title':'Preparar apresentacao'},{'title':'Revisar planejamento'}]},
            {'kind':'calendar','title':'Agenda','items':[{'title':'Reuniao de projeto','time':'14:00'},{'title':'Estudo','time':'16:00'}]},
            {'kind':'gmail','title':'E-mails','items':[{'title':'Equipe de projeto','detail':'Revisao de demonstracao'}]},
            {'kind':'whatsapp','title':'Mensagens','items':[{'title':'Contato de teste','detail':'Conversa de demonstracao'}]},
            {'kind':'system','title':'Sistema','cpu_percent':32,'ram_percent':68,'gpu_percent':41}]
        def command(action,value='',setting=''):
            request={'action':action,'value':value,'setting':setting,'done':__import__('threading').Event()}
            window._apply_interface_request(request)
            if not request.get('result',{}).get('ok'):failure.append(request.get('result'))
        def capture(name):window.grab().save(str(output/(name+'.png')))
        def weather_view():window._show_manifestation(weather)
        def pins():
            capture('weather-projection')
            for data in cases:window._pin_data({**data,'narrationDriven':False})
            window._content_panel.hide();window._layout_scene()
        def test_core_key():
            capture('six-pins')
            result['pins_ready']=all(p['view'] and p['view']._ready for p in window._pin_previews.values())
            core=window.hud._spatial_core
            target=core.focusProxy() or core if core else window.hud
            target.setFocus();QTest.keyClick(target,Qt.Key.Key_F11)
            QTest.qWait(200);result['core_f11_exit']=not window.isFullScreen() and window.width()<window.screen().availableGeometry().width()
            QTest.keyClick(target,Qt.Key.Key_F11);QTest.qWait(200);result['core_f11_enter']=window.isFullScreen()
            command('move_pin','','row');QTest.qWait(200);capture('pins-row')
        def column():
            command('move_pin','','column');QTest.qWait(200);capture('pins-column')
            window._open_settings_tab('profile')
        def settings():
            hub=window._settings_hub;hub.grab().save(str(output/'settings-profile.png'))
            hub.activateWindow();hub.name.setFocus();QTest.keyClick(hub.name,Qt.Key.Key_F11);QTest.qWait(200)
            result['settings_f11_exit']=not hub.isFullScreen()
            QTest.keyClick(hub.name,Qt.Key.Key_F11);QTest.qWait(200);result['settings_f11_enter']=hub.isFullScreen()
            hub.close()
            result['saved_pins']=len(window._pin_store.load())
            result['errors']=failure;result['passed']=all(v is True for k,v in result.items() if k not in ('saved_pins','errors')) and result['saved_pins']==6 and not failure
            (output/'result.json').write_text(json.dumps(result,indent=2))
            print(json.dumps(result),flush=True)
            hub.deleteLater();window.close();window.deleteLater()
            QTimer.singleShot(300,lambda:app.exit(0 if result['passed'] else 1))
        QTimer.singleShot(10000,weather_view);QTimer.singleShot(14000,pins)
        QTimer.singleShot(26000,test_core_key);QTimer.singleShot(30000,column);QTimer.singleShot(34000,settings)
        return app.exec()


if __name__=='__main__':sys.exit(main())
