"""Native WebEngine/settings validation with a disposable, disconnected profile."""
import json
from pathlib import Path
import sys
import tempfile
import os
from contextlib import ExitStack
from unittest.mock import patch
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
os.environ['DIEF_JARVIS_DATA_DIR']=tempfile.mkdtemp(prefix='dief-native-profile-')
import ui


def main():
    app=QApplication([sys.argv[0]]);app.setStyle('Fusion');app.setQuitOnLastWindowClosed(False)
    output=Path(tempfile.mkdtemp(prefix='dief-native-extensions-'));result={}
    with tempfile.TemporaryDirectory() as folder,ExitStack() as stack:
        root=Path(folder);config=root/'profile.json';config.write_text(json.dumps({'hud_style':'core','gemini_api_key':'synthetic-no-network','os_system':'windows','reduce_motion':False}))
        for target,value in [('ui.API_FILE',config),('memory.config_manager.CONFIG_FILE',config),('core.profile.CONFIG',config),('core.integration_tokens.ROOT',root),('core.gmail_connection.TOKEN',root/'gmail.bin'),('core.gmail_connection.CREDENTIALS',root/'oauth.json'),('core.whatsapp_web.PROFILE',root/'whatsapp'),('memory.memory_manager.MEMORY_PATH',root/'memory.json')]:stack.enter_context(patch(target,value))
        stack.enter_context(patch.object(ui.MainWindow,'_verify_saved_connections'))
        window=ui.MainWindow(str(ROOT/'core/face_model.obj'));window._ui_sounds.enabled=False
        from core.plugin_loader import discover_plugins
        registry=discover_plugins(ROOT/'plugins',set(),logger=lambda text:None)
        from core.extension_suite import CATALOG
        names=set(CATALOG)|{'skill_library','fish_audio','planet_knowledge'}
        window.get_plugins=lambda:[record for record in registry.list_for_ui() if record['name'] in names]
        window.get_plugin_settings=registry.settings_schemas
        window.showFullScreen()
        def planet():
            window._environment.command('terra');window._layout_scene();window._sync_environment()
        def capture():
            window.grab().save(str(output/'earth-native.png'))
            if window._space_view:window._space_view.page().runJavaScript('window.spaceDiagnostics()',lambda value:result.update(space=value))
            window._open_settings_tab('connections')
        def settings():
            hub=window._settings_hub;page=hub.connections_page
            hub.grab().save(str(output/'connections-accounts.png'))
            result['rows']=list(hub.connections_page.rows)
            result['skills']=len(page.skill_rows)
            page.categories.setCurrentIndex(1)
            QTimer.singleShot(400,native)
        def native():
            hub=window._settings_hub;hub.grab().save(str(output/'connections-native.png'))
            hub.connections_page.categories.setCurrentIndex(2);QTimer.singleShot(400,skills)
        def skills():
            hub=window._settings_hub;hub.grab().save(str(output/'connections-skills.png'))
            hub.open_plugin_settings('fish_audio');QTimer.singleShot(400,editor)
        def editor():
            hub=window._settings_hub;panel=hub._detail_overlay
            result['editor_visible']=panel.isVisible()
            hub.grab().save(str(output/'connection-editor.png'))
            panel._save_all();result['save_feedback']=bool(panel._status_labels['fish_audio'].text())
            panel.hide();QTimer.singleShot(400,reopen)
        def reopen():
            hub=window._settings_hub;hub.open_plugin_settings('fish_audio');QTimer.singleShot(400,finish)
        def finish():
            hub=window._settings_hub;result['reopened']=hub._detail_overlay.isVisible()
            hub.resize(900,700);QTimer.singleShot(400,compact)
        def compact():
            hub=window._settings_hub;hub.grab().save(str(output/'connection-editor-compact.png'))
            result['passed']=bool(result.get('space',{}).get('surfaceMaps',{}).get('earth')) and result.get('space',{}).get('drawCalls',0)>10 and len(result['rows'])>=12 and result['skills']>=27 and result['editor_visible'] and result['reopened'] and result['save_feedback']
            print(json.dumps({**result,'screenshots':str(output)},ensure_ascii=False),flush=True)
            hub.close();hub.deleteLater();window.close();window.deleteLater()
            QTimer.singleShot(300,lambda:app.exit(0 if result['passed'] else 1))
        QTimer.singleShot(9000,planet);QTimer.singleShot(14000,capture);QTimer.singleShot(16000,settings)
        return app.exec()


if __name__=='__main__':sys.exit(main())
