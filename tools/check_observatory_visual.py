"""Exercise the complete observatory without accounts, microphone or model calls."""
import json
import os
import sys
import tempfile
from pathlib import Path


def main():
    project = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(project))
    with tempfile.TemporaryDirectory(prefix='dief-observatory-check-') as folder:
        os.environ['DIEF_JARVIS_DATA_DIR'] = folder
        settings = json.loads((project / 'config/defaults.json').read_text(encoding='utf-8'))
        settings.update(gemini_api_key='visual-validation-only', os_system='windows', hud_style='core', panel_sounds_muted=True)
        (Path(folder) / 'api_keys.json').write_text(json.dumps(settings), encoding='utf-8')
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtCore import QTimer
        import ui
        app = QApplication([str(__file__)])
        window = ui.MainWindow(str(project / 'core/face_model.obj'))
        window.resize(1280, 800)
        window.show()

        def check():
            core = window.hud._spatial_core
            space = window._space_view
            result = {'core_ready': bool(core and core._ready and not core.failed),
                'space_ready': bool(space and space._ready and not space.failed),
                'scene_started': window._environment.started,
                'header_visible': window._title_lbl.isVisible(),
                'fallback': bool(getattr(window, '_scene_fallback_active', False))}
            print(json.dumps(result), flush=True)
            window.grab().save(str(project / 'validation/observatory-restored.png'))
            window.close()
            app.quit()

        QTimer.singleShot(14000, check)
        app.exec()


if __name__ == '__main__':
    main()
