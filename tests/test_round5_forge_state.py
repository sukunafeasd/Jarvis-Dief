"""Generation outcomes survive rendering and project switches without live services."""
import asyncio
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from core.forge import Runtime
from core.forge_status import summary
from test_forge_backend import EVIDENCE, FakeServer


class ForgeStateTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory(prefix='forge-round5-')
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name) / 'forge'
        preview = Mock()
        preview.publish.side_effect = lambda root, files, entrypoint, **options: (
            'http://127.0.0.1:1234/' + root.name + '/' + entrypoint)
        self.preview = preview
        preview_patch = patch('core.forge.runtime.PreviewServer', return_value=preview)
        preview_patch.start()
        self.addCleanup(preview_patch.stop)
        vendor_patch = patch.object(Runtime, '_vendor_assets')
        vendor_patch.start()
        self.addCleanup(vendor_patch.stop)
        self.runtime = self.new_runtime()
        self.addCleanup(lambda: self.runtime.close())

    def new_runtime(self):
        return Runtime(data_root=self.root, executable='unused-mocked-codex',
                       transport_factory=FakeServer, request_timeout=1)

    def create(self):
        self.assertTrue(self.runtime.connect('apiKey', key='mock-only')['accepted'])
        self.assertTrue(self.runtime.command('create', prompt='Mock page')['accepted'])
        return FakeServer.instances[-1]

    def finish(self, fake, status='completed', message=None):
        async def complete():
            turn = {'id': fake.active, 'status': status}
            if message:
                turn['error'] = {'message': message}
            fake.active = None
            self.runtime._event('turn/completed', {'threadId': fake.thread_id, 'turn': turn})
            await asyncio.gather(*list(self.runtime.jobs))
        self.runtime._call(complete())

    def validate(self, evidence=None):
        state = self.runtime.snapshot()
        return self.runtime.command(
            'validate_preview', project_id=state['project']['id'],
            revision=state['project']['revision'], candidate_url=state['candidate_preview_url'],
            evidence=EVIDENCE if evidence is None else evidence)

    def assert_failed(self, message):
        state = self.runtime.snapshot()
        self.assertEqual(state['phase'], 'error')
        self.assertFalse(state['generation_verified'])
        self.assertEqual(state['error'], message)
        self.assertEqual(summary(state)['status'], 'failed')
        project = self.runtime.store.load(state['project']['id'])
        self.assertEqual(project['state'], 'error')
        return project

    def test_partial_render_cannot_complete_failed_or_interrupted_generation(self):
        for status in ('failed', 'interrupted'):
            with self.subTest(status=status):
                fake = self.create()
                page = fake.cwd / 'index.html'
                page.write_bytes(b'<html>Partial output</html>')
                self.finish(fake, status, 'Generation stopped')
                self.assert_failed('Generation stopped')
                self.assertTrue(self.validate()['accepted'])
                project = self.assert_failed('Generation stopped')
                self.assertEqual(project['generation_status'], status)
                self.assertEqual(self.runtime.snapshot()['preview_validation'], 'passed')
                self.assertEqual(page.read_bytes(), b'<html>Partial output</html>')

    def test_unchanged_stable_preview_does_not_hide_failed_followup(self):
        fake = self.create()
        (fake.cwd / 'index.html').write_bytes(b'<html>Stable output</html>')
        self.finish(fake)
        self.assertTrue(self.validate()['accepted'])
        self.assertTrue(self.runtime.command('steer', prompt='Mock adjustment')['accepted'])
        self.finish(fake, 'failed', 'Adjustment failed')
        self.assert_failed('Adjustment failed')
        self.assertEqual(self.runtime.snapshot()['preview_validation'], 'passed')

    def test_failed_renderer_check_does_not_hide_generation_failure(self):
        fake = self.create()
        (fake.cwd / 'index.html').write_bytes(b'<html>Partial</html>')
        self.finish(fake, 'failed', 'Generation failed')
        self.assertFalse(self.validate({**EVIDENCE, 'nonblank': False})['accepted'])
        self.assert_failed('Generation failed')
        self.assertEqual(self.runtime.snapshot()['preview_validation'], 'failed')

    def test_open_empty_project_clears_previous_success_and_errors(self):
        fake = self.create()
        (fake.cwd / 'index.html').write_bytes(b'<html>Completed A</html>')
        self.finish(fake)
        self.assertTrue(self.validate()['accepted'])
        target = self.runtime.store.create('Empty B')
        self.runtime._update(error='Old error', preview_error='Old render error',
                             project_error='Old restore error', turn_id='old-turn')
        self.assertTrue(self.runtime.command('open', project_id=target['id'])['accepted'])
        state = self.runtime.snapshot()
        self.assertEqual(state['project']['name'], 'Empty B')
        self.assertEqual(state['phase'], 'idle')
        self.assertFalse(state['generation_verified'])
        for key in ('error', 'preview_error', 'project_error', 'turn_id',
                    'preview_url', 'candidate_preview_url', 'candidate_revision'):
            self.assertIsNone(state[key], key)
        self.assertNotEqual(summary(state)['status'], 'completed')

    def test_open_legacy_validated_project_uses_target_metadata(self):
        fake = self.create()
        (fake.cwd / 'index.html').write_bytes(b'<html>Saved output</html>')
        self.finish(fake)
        self.assertTrue(self.validate()['accepted'])
        target = self.runtime.store.load(self.runtime.snapshot()['project']['id'])
        target.pop('generation_status')
        target.pop('generation_error')
        target['state'] = 'idle'
        self.runtime.store.write(target)
        self.runtime._update(phase='error', generation_verified=False, error='Other project failed',
                             preview_error='Other preview failed')
        self.assertTrue(self.runtime.command('open', project_id=target['id'])['accepted'])
        state = self.runtime.snapshot()
        self.assertEqual(state['phase'], 'ready')
        self.assertTrue(state['generation_verified'])
        self.assertIsNone(state['error'])
        self.assertIsNone(state['preview_error'])
        self.assertEqual(state['preview_validation'], 'passed')
        self.assertEqual(summary(state)['status'], 'completed')

    def test_open_completed_nonvisual_project_recovers_generation_outcome(self):
        fake = self.create()
        (fake.cwd / 'result.txt').write_bytes(b'Completed output')
        self.finish(fake)
        target = self.runtime.snapshot()['project']['id']
        self.runtime._update(generation_verified=False, phase='error', error='Stale failure')
        self.assertTrue(self.runtime.command('open', project_id=target)['accepted'])
        state = self.runtime.snapshot()
        self.assertEqual(state['phase'], 'idle')
        self.assertTrue(state['generation_verified'])
        self.assertIsNone(state['error'])
        self.assertEqual(summary(state)['status'], 'completed')

    def test_legacy_failed_project_keeps_failure_with_validated_preview(self):
        fake = self.create()
        (fake.cwd / 'index.html').write_bytes(b'<html>Old stable output</html>')
        self.finish(fake)
        self.assertTrue(self.validate()['accepted'])
        target = self.runtime.store.load(self.runtime.snapshot()['project']['id'])
        target.pop('generation_status')
        target.pop('generation_error')
        target['state'] = 'error'
        self.runtime.store.write(target)
        self.assertTrue(self.runtime.command('open', project_id=target['id'])['accepted'])
        self.assert_failed('O motor Codex nao concluiu a etapa.')
        self.assertEqual(self.runtime.snapshot()['preview_validation'], 'passed')

    def test_completed_project_restores_success_after_restart(self):
        fake = self.create()
        page = fake.cwd / 'index.html'
        page.write_bytes(b'<html>Persisted successful output</html>')
        self.finish(fake)
        self.assertTrue(self.validate()['accepted'])
        target = self.runtime.snapshot()['project']['id']
        self.runtime.close()
        self.runtime = self.new_runtime()
        self.assertTrue(self.runtime.snapshot()['generation_verified'])
        self.assertTrue(self.runtime.command('open', project_id=target)['accepted'])
        self.assertEqual(self.runtime.snapshot()['phase'], 'ready')
        self.assertIsNone(self.runtime.snapshot()['error'])
        self.assertEqual(page.read_bytes(), b'<html>Persisted successful output</html>')

    def test_failed_generation_survives_validated_preview_open_and_restart(self):
        fake = self.create()
        (fake.cwd / 'index.html').write_bytes(b'<html>Partial</html>')
        self.finish(fake, 'failed', 'Persisted failure')
        self.assertTrue(self.validate()['accepted'])
        target = self.runtime.snapshot()['project']['id']
        self.assertTrue(self.runtime.command('open', project_id=target)['accepted'])
        self.assert_failed('Persisted failure')
        self.runtime.close()
        self.runtime = self.new_runtime()
        self.assert_failed('Persisted failure')
        self.assertTrue(self.runtime.command('open', project_id=target)['accepted'])
        self.assert_failed('Persisted failure')

    def test_successful_retry_replaces_persisted_failure(self):
        fake = self.create()
        (fake.cwd / 'index.html').write_bytes(b'<html>Partial</html>')
        self.finish(fake, 'failed', 'First attempt failed')
        self.assertTrue(self.validate()['accepted'])
        self.assertTrue(self.runtime.command('steer', prompt='Retry')['accepted'])
        self.finish(fake)
        self.assertTrue(self.validate()['accepted'])
        state = self.runtime.snapshot()
        self.assertEqual(state['phase'], 'ready')
        self.assertTrue(state['generation_verified'])
        self.assertIsNone(state['error'])
        target = state['project']['id']
        self.assertTrue(self.runtime.command('open', project_id=target)['accepted'])
        self.assertTrue(self.runtime.snapshot()['generation_verified'])

    def restore_unresolved_project(self):
        fake = self.create()
        page = fake.cwd / 'index.html'
        page.write_bytes(b'<html>Last verified output</html>')
        self.finish(fake)
        self.assertTrue(self.validate()['accepted'])
        target = self.runtime.snapshot()['project']['id']
        self.runtime.close()
        # Simulate a saved followup whose final provider event was never received.
        project = self.runtime.store.load(target)
        project['generation_status'] = 'inProgress'
        project['state'] = 'idle'
        self.runtime.store.write(project)
        manifest = (self.root / 'projects' / target / 'manifest.json').read_bytes()
        self.runtime = self.new_runtime()
        return target, page, manifest

    def assert_unresolved(self):
        state = self.runtime.snapshot()
        self.assertEqual(state['phase'], 'recovering')
        self.assertFalse(state['generation_verified'])
        self.assertIsNone(state['error'])
        self.assertIsNone(self.runtime.active_turn)
        self.assertEqual(summary(state)['status'], 'waiting')
        project = self.runtime.store.load(state['project']['id'])
        self.assertEqual(project['generation_status'], 'inProgress')
        self.assertNotEqual(project['state'], 'ready')
        return state

    def test_restore_and_open_unresolved_generation_preserve_stable_preview(self):
        target, page, manifest = self.restore_unresolved_project()
        self.assert_unresolved()
        self.assertIsNone(self.runtime.client)
        self.assertEqual((self.root / 'projects' / target / 'manifest.json').read_bytes(), manifest)
        self.assertTrue(self.runtime.command('open', project_id=target)['accepted'])
        state = self.assert_unresolved()
        self.assertIsNotNone(state['preview_url'])
        self.assertEqual(state['preview_validation'], 'passed')
        self.assertIsNone(self.runtime.client)
        self.assertEqual(page.read_bytes(), b'<html>Last verified output</html>')

    def test_validating_old_stable_preview_cannot_resolve_generation(self):
        target, page, _ = self.restore_unresolved_project()
        self.assertTrue(self.runtime.command('open', project_id=target)['accepted'])
        stable = self.runtime.snapshot()['preview_url']
        self.assertFalse(self.validate({**EVIDENCE, 'nonblank': False})['accepted'])
        self.assert_unresolved()
        self.assertEqual(self.runtime.snapshot()['preview_url'], stable)
        self.assertTrue(self.validate()['accepted'])
        state = self.assert_unresolved()
        self.assertEqual(state['preview_url'], stable)
        self.assertEqual(state['preview_validation'], 'passed')
        self.assertEqual(page.read_bytes(), b'<html>Last verified output</html>')

    def test_unresolved_reconnect_does_not_rerun_and_active_turn_can_resolve(self):
        target, _, _ = self.restore_unresolved_project()
        self.assertTrue(self.runtime.command('open', project_id=target)['accepted'])
        self.assertTrue(self.runtime.connect('apiKey', key='mock-only')['accepted'])
        fake = FakeServer.instances[-1]
        self.assert_unresolved()
        self.assertFalse(any(method == 'turn/start' for method, _ in fake.calls))
        original = fake.request
        async def request(method, params):
            if method == 'thread/resume':
                fake.active = 'confirmed-active-turn'
                return {'thread': {'turns': [{'id': fake.active, 'status': 'inProgress'}]}}
            return await original(method, params)
        fake.request = request
        self.assertTrue(self.runtime.command('open', project_id=target)['accepted'])
        state = self.runtime.snapshot()
        self.assertEqual(state['phase'], 'running')
        self.assertFalse(state['generation_verified'])
        self.assertEqual(summary(state)['status'], 'running')
        self.finish(fake)
        self.assertEqual(self.runtime.snapshot()['phase'], 'ready')
        self.assertTrue(self.runtime.snapshot()['generation_verified'])

    def test_unresolved_generation_allows_explicit_user_run(self):
        target, _, _ = self.restore_unresolved_project()
        self.assertTrue(self.runtime.command('open', project_id=target)['accepted'])
        self.assertTrue(self.runtime.connect('apiKey', key='mock-only')['accepted'])
        fake = FakeServer.instances[-1]
        self.assert_unresolved()
        self.assertTrue(self.runtime.command('steer', prompt='Explicit user followup')['accepted'])
        self.assertEqual(self.runtime.snapshot()['phase'], 'running')
        self.assertEqual(sum(method == 'turn/start' for method, _ in fake.calls), 1)
        self.finish(fake, 'failed', 'Confirmed followup failure')
        self.assert_failed('Confirmed followup failure')


if __name__ == '__main__':
    unittest.main()
