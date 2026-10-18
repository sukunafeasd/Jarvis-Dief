import unittest
from pathlib import Path
import test_refresh_visual

BASE = Path(__file__).resolve().parents[1]
OUTPUT = BASE / 'validation/reference-visual'


class ReferenceVisualTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = test_refresh_visual.RefreshVisualTests.asyncSetUp
    asyncTearDown = test_refresh_visual.RefreshVisualTests.asyncTearDown

    async def test_hud_glass_is_cached_and_respects_embedded_and_reduced_modes(self):
        from io import BytesIO
        from PIL import Image
        await self.page.set_viewport_size({'width': 540, 'height': 700})
        await self.page.goto(self.url + '/presentation.html')
        await self.page.wait_for_function('typeof window.updateCore === "function"')
        model = {'kind': 'weather', 'title': 'CLIMA', 'temperature': 23,
            'code': 61, 'condition': 'Chuva', 'motion': 'reduced', 'compact': True}
        await self.page.evaluate('m => window.updateCore(m)', model)
        await self.page.wait_for_timeout(2600)
        paints = await self.page.evaluate('Number(document.body.dataset.hudPaints)')
        self.assertIsInstance(paints, int)
        self.assertGreater(paints, 0)
        for value in range(20):
            await self.page.evaluate('m => window.updateCore(m)', {**model, 'temperature': value})
        await self.page.wait_for_timeout(1200)
        self.assertEqual(paints, await self.page.evaluate('Number(document.body.dataset.hudPaints)'))
        self.assertEqual(await self.page.locator('canvas').count(), 1)
        self.assertEqual(await self.page.evaluate('getComputedStyle(document.querySelector("main"),"::before").animationName'), 'none')
        image = Image.open(BytesIO(await self.page.screenshot())).convert('RGB')
        blue_edges = sum(b > 120 and b > r * 1.3 and g > r * 1.2
            for r, g, b in image.getdata())
        self.assertGreater(blue_edges, 200)
        await self.page.set_viewport_size({'width': 390, 'height': 560})
        await self.page.wait_for_timeout(250)
        self.assertGreater(await self.page.evaluate('Number(document.body.dataset.hudPaints)'), paints)
        await self.page.evaluate('m => window.updateCore(m)', {**model, 'framed': True})
        await self.page.wait_for_function('document.body.style.getPropertyValue("--hud-surface") === "none"')
        self.assertEqual(await self.page.evaluate('document.body.style.getPropertyValue("--hud-surface")'), 'none')
        self.assertEqual(await self.page.evaluate('getComputedStyle(document.body).backgroundImage'), 'none')
        for kind in ('news', 'status'):
            await self.page.evaluate('m => window.updateCore(m)', {'kind': kind, 'title': 'Teste', 'motion': 'reduced'})
            await self.page.wait_for_timeout(150)
            self.assertEqual(await self.page.evaluate('document.body.style.getPropertyValue("--hud-surface")'), 'none')
        self.assertEqual(self.errors, [])

    async def test_card_skin_preserves_geometry_and_data(self):
        OUTPUT.mkdir(parents=True, exist_ok=True)
        await self.page.goto(self.url + '/presentation.html')
        await self.page.wait_for_function('typeof window.updateCore === "function"')
        await self.page.evaluate("document.documentElement.style.background=\"#03070a url('./assets/deep-space.png') center/cover\"")
        models = [
            ('whatsapp', 1000, 420, {'kind': 'whatsapp', 'title': 'WHATSAPP - NAO LIDAS',
                'count': 3, 'items': [{'title': name, 'detail': 'Mensagem sintetica para validar o visual.'}
                    for name in ('Contato de teste A', 'Contato de teste B', 'Contato de teste C')]}),
            ('weather', 540, 700, {'kind': 'weather', 'title': 'CLIMA', 'city': 'Sao Paulo',
                'temperature': 23, 'humidity': 62, 'wind': 12, 'code': 2, 'condition': 'Parcialmente nublado'}),
            ('weather-pin', 320, 150, {'kind': 'weather', 'title': 'CLIMA', 'city': 'Sao Paulo',
                'temperature': 23, 'code': 61, 'condition': 'Chuva', 'compact': True}),
            ('calendar', 540, 700, {'kind': 'calendar', 'title': 'AGENDA', 'items': [
                {'title': 'Revisao do projeto', 'due': '2026-10-12T14:00', 'detail': 'Exemplo visual'},
                {'title': 'Estudo', 'due': '2026-10-12T16:00', 'detail': 'Exemplo visual'}]}),
            ('gmail', 1000, 420, {'kind': 'gmail', 'title': 'GMAIL - DEMONSTRACAO',
                'items': [{'title': 'Revisao do projeto', 'detail': 'Mensagem sintetica para teste.'}]}),
            ('system', 540, 700, {'kind': 'system', 'title': 'SISTEMA - DEMONSTRACAO',
                'cpu_percent': 32, 'ram_percent': 68, 'gpu_percent': 41, 'cpu_temp_c': 58}),
            ('tasks', 540, 700, {'kind': 'tasks', 'title': 'TAREFAS - DEMONSTRACAO',
                'count': 3, 'items': [{'title': 'Revisar projeto', 'priority': 'high'},
                    {'title': 'Estudo'}, {'title': 'Organizar materiais'}]}),
            ('whatsapp-small', 390, 560, {'kind': 'whatsapp', 'title': 'WHATSAPP',
                'items': [{'title': 'Contato de teste', 'detail': 'Mensagem sintetica para validar texto em tela estreita.'}]}),
        ]
        measure = """() => Object.fromEntries(['summary','symbol-space','details','metrics'].map(id => {
          const r=document.getElementById(id).getBoundingClientRect();
          return [id,[r.x,r.y,r.width,r.height]];
        }))"""
        for label, width, height, model in models:
            await self.page.set_viewport_size({'width': width, 'height': height})
            await self.page.evaluate('m => window.updateCore(m)', {**model, 'motion': 'reduced'})
            await self.page.wait_for_timeout(150)
            styled = await self.page.evaluate(measure)
            if await self.page.evaluate('document.body.dataset.surface')=='projection':
                # The new unframed layout deliberately moves symbols beside readable text.
                await self.page.wait_for_timeout(100)
                self.assertEqual(styled,await self.page.evaluate(measure),label+': labels must stay stable')
                if width>430:
                    symbol=styled['symbol-space'];summary=styled['summary']
                    self.assertLessEqual(symbol[0]+symbol[2],summary[0],label)
            else:
                # Card padding and compact icon size intentionally changed in the polish pass.
                await self.page.wait_for_timeout(120)
                self.assertEqual(styled,await self.page.evaluate(measure),label+': card layout must stay stable')
                for name,bounds in styled.items():
                    if bounds[2]>0 and bounds[3]>0:
                        self.assertGreaterEqual(bounds[0],0,label+': '+name)
                        self.assertLessEqual(bounds[0]+bounds[2],width,label+': '+name)
            self.assertFalse(await self.page.evaluate('document.documentElement.scrollWidth > innerWidth'))
            await self.page.wait_for_timeout(2400)
            await self.page.screenshot(path=str(OUTPUT / (label + '.png')))
        self.assertEqual(self.errors, [])

    async def test_embedded_news_and_status_keep_background_transparent(self):
        await self.page.goto(self.url + '/presentation.html')
        await self.page.wait_for_function('typeof window.updateCore === "function"')
        for kind in ('news', 'status'):
            await self.page.evaluate('m => window.updateCore(m)', {'kind': kind,
                'title': 'EXEMPLO', 'items': [{'title': 'Registro sintetico', 'detail': 'Teste'}],
                'motion': 'reduced'})
            background = await self.page.evaluate('getComputedStyle(document.body).backgroundColor')
            self.assertEqual(background, 'rgba(0, 0, 0, 0)')
        self.assertEqual(self.errors, [])

    async def test_red_core_material_motion_and_framing(self):
        from io import BytesIO
        from PIL import Image
        OUTPUT.mkdir(parents=True, exist_ok=True)
        await self.page.goto(self.url + '/index.html')
        self.page.on('console', lambda message: self.errors.append(message.text)
            if message.type == 'error' and 'Shader Error' in message.text else None)
        await self.page.wait_for_function('typeof window.hologramDiagnostics === "function"')
        await self.page.evaluate("document.body.style.background=\"#03070a url('./assets/deep-space.png') center/cover\"")
        await self.page.wait_for_timeout(1300)
        await self.page.evaluate("window.updateCore({phase:'speaking',color:'#ff303b',level:.25})")
        await self.page.wait_for_timeout(250)
        initial = await self.page.evaluate('window.hologramDiagnostics()')
        for phase in ('idle', 'listening', 'speaking', 'executing', 'sleeping'):
            await self.page.evaluate('s => window.updateCore(s)', {'phase': phase,
                'color': '#ff303b', 'level': .25 if phase in ('speaking', 'listening') else 0,
                'resting': phase == 'sleeping', 'motion': 'full'})
            await self.page.wait_for_timeout(1000)
            await self.page.screenshot(path=str(OUTPUT / ('core-' + phase + '.png')))
        await self.page.evaluate("window.updateCore({phase:'idle',resting:false,level:0})")
        await self.page.wait_for_timeout(1400)
        first = await self.page.locator('canvas').screenshot()
        await self.page.wait_for_timeout(400)
        self.assertNotEqual(first, await self.page.locator('canvas').screenshot())
        image = Image.open(BytesIO(first)).convert('RGBA')
        self.assertGreater(sum(r > g * 1.5 and r > b * 1.3 and a > 25
            for r, g, b, a in image.getdata()), 500)
        for width, height in ((640, 480), (390, 844)):
            await self.page.set_viewport_size({'width': width, 'height': height})
            await self.page.wait_for_timeout(500)
            await self.page.screenshot(path=str(OUTPUT / ('core-fit-' + str(width) + '.png')))
        final = await self.page.evaluate('window.hologramDiagnostics()')
        self.assertEqual((initial['geometries'], initial['textures']),
            (final['geometries'], final['textures']))
        self.assertLessEqual(final['drawCalls'], 55)
        self.assertEqual(self.errors, [])

    async def test_sparse_fact_symbols_are_decorative_and_motion_safe(self):
        OUTPUT.mkdir(parents=True, exist_ok=True)
        await self.page.set_viewport_size({'width': 540, 'height': 700})
        await self.page.goto(self.url + '/presentation.html')
        await self.page.wait_for_function('typeof window.updateCore === "function"')
        await self.page.evaluate("document.documentElement.style.background=\"#03070a url('./assets/deep-space.png') center/cover\"")
        for title, expected in (('Caminhada', 'steps'), ('Energia', 'energy'), ('Calorias', 'flame')):
            items = [{'title': 'Valor de teste', 'value': '28', 'detail': 'Apenas validacao visual'}]
            if expected == 'steps':
                items = [{'title': 'Distancia de teste', 'value': '0,13 km'},
                    {'title': 'Passos de teste', 'value': '2.483'},
                    {'title': 'Calorias de teste', 'value': '182 kcal'},
                    {'title': 'Tempo de teste', 'value': '28 min'}]
            model = {'kind': 'data', 'title': title, 'source': 'DADOS SINTETICOS DE TESTE',
                'items': items}
            await self.page.evaluate('m => window.updateCore(m)', model)
            await self.page.wait_for_timeout(2400)
            self.assertEqual(await self.page.evaluate('document.body.dataset.factSymbol'), expected)
            self.assertEqual(await self.page.evaluate('getComputedStyle(document.body).backgroundColor'), 'rgba(0, 0, 0, 0)')
            self.assertIn(items[0]['title'], await self.page.locator('#details').inner_text())
            first = await self.page.locator('canvas').screenshot()
            await self.page.wait_for_timeout(350)
            self.assertNotEqual(first, await self.page.locator('canvas').screenshot())
            await self.page.screenshot(path=str(OUTPUT / ('fact-' + expected + '.png')))
            await self.page.evaluate('m => window.updateCore(m)', {**model, 'motion': 'reduced'})
            await self.page.wait_for_timeout(100)
            first = await self.page.locator('canvas').screenshot()
            await self.page.wait_for_timeout(150)
            self.assertEqual(first, await self.page.locator('canvas').screenshot())
        await self.page.evaluate('m => window.updateCore(m)', {'kind': 'data', 'title': 'Energia',
            'items': [{'title': str(i), 'value': i} for i in range(8)], 'motion': 'reduced'})
        self.assertEqual(await self.page.evaluate('document.body.dataset.factSymbol'), '')
        self.assertEqual(self.errors, [])


class ReferenceSettingsTests(unittest.TestCase):
    def test_native_hud_frame_cache_and_workspace_controls(self):
        import os
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtTest import QTest
        from core.hud_glass import HudGlassFrame
        from core.workspace_panels import WorkspacePanel
        app = QApplication.instance() or QApplication([])
        OUTPUT.mkdir(parents=True, exist_ok=True)
        frame = HudGlassFrame(); frame.resize(320, 150); frame.show(); QTest.qWait(50)
        cached = frame._plate.cacheKey()
        frame.update(); QTest.qWait(50)
        self.assertEqual(cached, frame._plate.cacheKey())
        frame.grab().save(str(OUTPUT / 'native-pin-material.png'))
        frame.resize(390, 160); QTest.qWait(50)
        self.assertNotEqual(cached, frame._plate.cacheKey())
        panel = WorkspacePanel(None); panel.resize(520, 430); panel.show_panel(reduced=True)
        messages = []; panel.submitted.connect(messages.append)
        panel.input.setText('Mensagem de teste'); panel.send()
        self.assertEqual(messages, ['Mensagem de teste'])
        panel.add_line('DIEF JARVIS: conversa sintetica de validacao.')
        QTest.qWait(80); panel.grab().save(str(OUTPUT / 'terminal-material.png'))
        panel.close_panel(); panel.deleteLater(); frame.close(); frame.deleteLater(); app.processEvents()

    def test_native_settings_setup_and_admin_keep_controls(self):
        import os
        import json
        import tempfile
        from unittest.mock import patch
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtTest import QTest
        from core.settings_hub import SettingsHub
        from core.elevation_dialog import ElevationDialog
        import ui
        app = QApplication.instance() or QApplication([])
        app.setStyle('Fusion')
        OUTPUT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / 'profile.json'
            config.write_text(json.dumps({'user_name': 'Perfil de teste', 'city': 'Sao Paulo',
                'ui_color': '#ff303b', 'hud_style': 'core', 'reduce_motion': True}), encoding='utf-8')
            with patch.object(ui, 'API_FILE', config), patch('memory.config_manager.CONFIG_FILE', config), \
                 patch('core.profile.CONFIG', config), patch('core.integration_tokens.ROOT', Path(directory)), \
                 patch('core.gmail_connection._load_info', return_value={}), \
                 patch('core.gmail_connection.credential_client_id', return_value=''):
                window = ui.MainWindow(str(BASE / 'core/face_model.obj'))
                hub = SettingsHub(window, config, ui.C)
                try:
                    hub.show()
                    for width, height in ((1366, 768), (800, 600)):
                        hub.resize(width, height)
                        for page in ('profile', 'connections', 'appearance'):
                            if page not in hub.page_indices:
                                continue
                            hub.open_page(page)
                            QTest.qWait(500)
                            self.assertEqual(hub.tabs.count(), 6)
                            self.assertEqual(hub.navigation.count(), 6)
                            hub.grab().save(str(OUTPUT / ('settings-' + page + '-' + str(width) + '.png')))
                    setup = ui.SetupOverlay()
                    setup.resize(580, 420); setup.show(); QTest.qWait(100)
                    self.assertEqual(setup._key_input.echoMode(), ui.QLineEdit.EchoMode.Password)
                    setup.grab().save(str(OUTPUT / 'setup.png')); setup.close()
                    admin = ElevationDialog(lambda: False)
                    admin.show(); QTest.qWait(200)
                    self.assertTrue(admin.continue_button.isEnabled())
                    admin.grab().save(str(OUTPUT / 'admin.png')); admin.close()
                finally:
                    hub.close(); window.close(); hub.deleteLater(); window.deleteLater(); app.processEvents()


if __name__ == '__main__':
    unittest.main()
