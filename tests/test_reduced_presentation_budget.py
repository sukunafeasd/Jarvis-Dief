"""Offline draw budgets for settled reduced-motion projections."""
import tempfile
from pathlib import Path
import unittest

import test_refresh_visual


class ReducedPresentationBudgetTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = test_refresh_visual.RefreshVisualTests.asyncSetUp
    asyncTearDown = test_refresh_visual.RefreshVisualTests.asyncTearDown

    async def load_projection(self, **changes):
        await self.page.route('**/*', lambda route: route.continue_()
                              if route.request.url.startswith(self.url + '/') else route.abort())
        await self.page.add_init_script('''
            window.gpuDraws = 0;
            for (const type of [window.WebGLRenderingContext, window.WebGL2RenderingContext]) {
              if (!type) continue;
              for (const name of ['drawArrays', 'drawElements', 'drawArraysInstanced', 'drawElementsInstanced']) {
                if (!Object.hasOwn(type.prototype, name)) continue;
                const original = type.prototype[name];
                type.prototype[name] = function(...args) {
                  window.gpuDraws++;
                  return original.apply(this, args);
                };
              }
            }
        ''')
        await self.page.goto(self.url + '/presentation.html')
        await self.page.wait_for_function('typeof window.updateCore === "function"')
        self.model = {'kind': 'tasks', 'presentationId': 'budget', 'motion': 'reduced',
                      'items': [{'title': 'Primeira tarefa'}, {'title': 'Segunda tarefa'}],
                      **changes}
        await self.page.evaluate('value => {updateCore(value); finishPresentation();}', self.model)
        await self.page.wait_for_function('window.gpuDraws > 0 && document.body.dataset.kind === "tasks"')
        await self.page.wait_for_timeout(350)

    async def draws(self):
        return await self.page.evaluate('window.gpuDraws')

    async def assert_settled(self):
        await self.page.wait_for_timeout(200)
        before = await self.draws()
        await self.page.wait_for_timeout(500)
        self.assertEqual(await self.draws(), before)

    async def test_settled_reduced_projection_stops_gpu_draws_and_redraws_updates(self):
        await self.load_projection()
        await self.assert_settled()
        before = await self.draws()
        self.model['items'][0]['title'] = 'Tarefa atualizada'
        await self.page.evaluate('value => {updateCore(value); finishPresentation();}', self.model)
        await self.page.wait_for_function('before => window.gpuDraws > before', arg=before)
        self.assertIn('Tarefa atualizada', await self.page.locator('#details').inner_text())
        await self.assert_settled()
        before = await self.draws()
        await self.page.set_viewport_size({'width': 640, 'height': 600})
        await self.page.wait_for_function('before => window.gpuDraws > before', arg=before)
        await self.assert_settled()
        with tempfile.TemporaryDirectory(prefix='dief-reduced-budget-') as folder:
            await self.page.screenshot(path=str(Path(folder) / 'reduced-projection.png'))
        self.assertEqual(self.errors, [])

    async def test_narration_visibility_and_normal_motion_keep_working(self):
        await self.load_projection()
        self.model.update(presentationId='narrated', narrationDriven=True)
        await self.page.evaluate('value => updateCore(value)', self.model)
        await self.page.evaluate('advancePresentation({presentationId:"narrated", elapsed:1, cues:["Segunda tarefa."]})')
        await self.page.wait_for_timeout(200)
        self.assertEqual(await self.page.locator('.selected').get_attribute('data-index'), '1')
        await self.page.evaluate('finishPresentation()')
        await self.assert_settled()
        await self.page.evaluate('updateCore({visible:false})')
        before = await self.draws()
        await self.page.wait_for_timeout(500)
        self.assertEqual(await self.draws(), before)
        await self.page.evaluate('updateCore({visible:true})')
        await self.page.wait_for_function('before => window.gpuDraws > before', arg=before)
        await self.assert_settled()
        self.model.update(motion='full', narrationDriven=False)
        await self.page.evaluate('value => updateCore(value)', self.model)
        await self.page.wait_for_timeout(250)
        before = await self.draws()
        await self.page.wait_for_timeout(250)
        self.assertGreater(await self.draws(), before)
        self.assertEqual(self.errors, [])

    async def test_live_metadata_and_media_preference_invalidate_static_projection(self):
        await self.load_projection()
        meter = {'kind': 'system', 'compact': True, 'rebuild': False,
                 'motion': 'reduced', 'cpu_percent': 10, 'ram_percent': 20,
                 'source': 'Consulta local', 'observed': '10:00'}
        await self.page.evaluate('value => {updateCore(value); finishPresentation();}', meter)
        await self.assert_settled()
        before = await self.draws()
        meter.update(cpu_percent=42, observed='10:01')
        await self.page.evaluate('value => updateCore(value)', meter)
        await self.page.wait_for_function('before => window.gpuDraws > before', arg=before)
        self.assertIn('42', await self.page.locator('#summary').inner_text())
        await self.assert_settled()
        await self.page.emulate_media(reduced_motion='reduce')
        del meter['motion']
        await self.page.evaluate('value => {updateCore(value); finishPresentation();}', meter)
        await self.assert_settled()
        before = await self.draws()
        await self.page.emulate_media(reduced_motion='no-preference')
        await self.page.wait_for_function('before => window.gpuDraws > before', arg=before)
        await self.page.wait_for_timeout(200)
        before = await self.draws()
        await self.page.wait_for_timeout(250)
        self.assertGreater(await self.draws(), before)
        await self.page.emulate_media(reduced_motion='reduce')
        await self.assert_settled()
        self.assertEqual(self.errors, [])
