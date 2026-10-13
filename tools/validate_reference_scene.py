"""Capture the real Qt composition using isolated, synthetic visual data."""
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

os.environ['QT_QPA_PLATFORM'] = 'windows' if '--webgl' in sys.argv and os.name == 'nt' else 'offscreen'
if '--software' in sys.argv:
    os.environ['QTWEBENGINE_CHROMIUM_FLAGS'] = '--enable-unsafe-swiftshader --use-angle=swiftshader'
BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication
import ui

OUTPUT = BASE / 'validation/reference-visual'
OUTPUT.mkdir(parents=True, exist_ok=True)
models = [
    {'kind': 'weather', 'title': 'CLIMA', 'city': 'Sao Paulo', 'temperature': 23,
     'condition': 'Chuva', 'code': 61, 'rain': 80, 'wind': 12, 'humidity': 62,
     'source': 'DADOS SINTETICOS DE TESTE'},
    {'kind': 'whatsapp', 'title': 'WHATSAPP - NAO LIDAS', 'count': 3,
     'items': [{'title': 'Contato de teste ' + str(i), 'detail': 'Mensagem sintetica para validar o visual.'}
               for i in range(1, 4)], 'source': 'DADOS SINTETICOS DE TESTE'},
    {'kind': 'data', 'title': 'Caminhada', 'items': [
        {'title': 'Distancia', 'value': '0,13 km'}, {'title': 'Passos', 'value': '2.483'},
        {'title': 'Calorias', 'value': '182 kcal'}, {'title': 'Tempo', 'value': '28 min'}],
     'source': 'DADOS SINTETICOS DE TESTE'},
]

print('Starting isolated Qt visual capture.', flush=True)
app = QApplication([])
app.setStyle('Fusion')
with tempfile.TemporaryDirectory() as directory:
    config = Path(directory) / 'profile.json'
    config.write_text(json.dumps({'hud_style': 'core', 'ui_color': '#ff303b',
        'user_name': 'Perfil de teste'}), encoding='utf-8')
    with patch.object(ui, 'API_FILE', config), patch('memory.config_manager.CONFIG_FILE', config), \
         patch('core.profile.CONFIG', config), patch('core.integration_tokens.ROOT', Path(directory)):
        window = ui.MainWindow(str(BASE / 'core/face_model.obj'))
        print('Qt window created.', flush=True)
        window.resize(1600, 900); window.show()
        if window._overlay:
            window._overlay.hide()
        window.hud.hud_style = 'core'
        window._apply_state('SPEAKING')
        remaining = list(models)
        results = []

        def next_scene():
            if not remaining:
                print(json.dumps(results), flush=True)
                window.close(); app.quit(); return
            model = remaining.pop(0)
            print('Capturing ' + model['kind'] + '.', flush=True)
            window._show_manifestation({**model, 'narrationDriven': False})
            QTimer.singleShot(4500, lambda: capture(model))

        def capture(model):
            window.grab().save(str(OUTPUT / ('scene-' + model['kind'] + '.png')))
            if window._content_spatial:
                window._content_spatial.page().runJavaScript(
                    '({ready:document.body.dataset.ready,kind:document.body.dataset.kind})',
                    lambda result: captured(model, result))
            else:
                captured(model, {'fallback': True})

        def captured(model, result):
            results.append({'scene': model['kind'], 'renderer': result})
            next_scene()

        QTimer.singleShot(2000, next_scene)
        QTimer.singleShot(40000, app.quit)
        app.exec()
        window.close()
        if len(results) != len(models) or ('--webgl' in sys.argv and
                any(not row['renderer'].get('ready') for row in results)):
            raise SystemExit('Qt capture did not confirm every WebGL scene.')
