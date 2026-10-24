"""Dispatch must preserve evidence, including absence of confirmation."""
import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from core.action_loader import ActionRecord, ActionRegistry
from core.plugin_loader import PluginRecord, PluginRegistry
from core.action_outcome import assess, normalize_dispatch_result
from core.application_context import ApplicationContext


class DispatchEvidenceTests(unittest.TestCase):
    def registries(self, handler):
        return (
            ActionRegistry({'sample': ActionRecord(name='sample', valid=True, handler=handler)}, Mock()),
            PluginRegistry({'sample': PluginRecord(name='sample', valid=True, run=handler)}, Mock()),
        )

    def setUp(self):
        self.enabled = patch('core.plugin_loader.get_plugin_enabled', return_value=True)
        self.enabled.start()
        self.addCleanup(self.enabled.stop)

    def test_empty_result_is_not_success(self):
        for value in (None, '', '  '):
            for registry in self.registries(Mock(return_value=value)):
                with self.subTest(value=value, registry=type(registry).__name__):
                    result = json.loads(registry.run('sample', {}))
                    self.assertEqual(result['error_code'], 'missing_result')
                    self.assertEqual(assess(result)['state'], 'uncertain')

    def test_existing_results_are_preserved_even_when_falsy(self):
        for value in (False, 0, [], {}, {'ok': False, 'error': 'fixture'},
                      {'ok': True, 'state': 'running', 'job_id': 'j1'}, 'legacy result'):
            for registry in self.registries(Mock(return_value=value)):
                self.assertIs(registry.run('sample', {}), value)

    def test_unknown_action_did_not_start(self):
        handler = Mock()
        for registry in self.registries(handler):
            result = json.loads(registry.run('missing', {}))
            self.assertEqual(assess(result)['state'], 'failed')
            self.assertFalse(result['execution_started'])
        handler.assert_not_called()

    def test_invalid_arguments_cannot_enter_handler(self):
        handler = Mock()
        for registry in self.registries(handler):
            for args in (None, [], 'query', 2):
                result = json.loads(registry.run('sample', args))
                self.assertEqual(result['error_code'], 'invalid_arguments')
                self.assertFalse(result['uncertain'])
        handler.assert_not_called()

    def test_disabled_plugin_cannot_execute(self):
        handler = Mock()
        registry = self.registries(handler)[1]
        with patch('core.plugin_loader.get_plugin_enabled', return_value=False):
            result = json.loads(registry.run('sample', {}))
        self.assertEqual(result['error_code'], 'disabled')
        self.assertFalse(result['execution_started'])
        handler.assert_not_called()

    def test_crash_after_effect_does_not_authorize_blind_repeat(self):
        effects = []
        def handler(parameters):
            effects.append('effect')
            raise TimeoutError('private synthetic request payload')
        for registry in self.registries(handler):
            with patch('core.action_loader.traceback.print_exc'), patch('core.plugin_loader.traceback.print_exc'):
                result = json.loads(registry.run('sample', {'action': 'send'}))
            self.assertEqual(assess(result)['state'], 'uncertain')
            self.assertEqual(result['exception_type'], 'TimeoutError')
            self.assertNotIn('private synthetic', json.dumps(result))
            context = ApplicationContext()
            context.record_tool_result('sample', {'action': 'send'}, result)
            self.assertTrue(context.tool_retry_check('sample', {'action': 'send'}))
            context.observe_user('O que aconteceu?')
            self.assertTrue(context.tool_retry_check('sample', {'action': 'send'}))
            self.assertEqual(context.snapshot()['unresolved_operations'][0]['last_observed_outcome'], 'uncertain')
            self.assertFalse(context.tool_retry_check('sample', {'action': 'status'}))
        self.assertEqual(len(effects), 2)

    def test_incompatible_signature_is_not_execution(self):
        effects = []
        def handler(parameters, required_dependency):
            effects.append(parameters)
        for registry in self.registries(handler):
            result = json.loads(registry.run('sample', {}))
            self.assertEqual(result['error_code'], 'invalid_handler_contract')
            self.assertFalse(result['execution_started'])
            self.assertEqual(assess(result)['state'], 'failed')
        self.assertEqual(effects, [])

    def test_missing_result_stays_structured_across_dispatch_layers(self):
        first = normalize_dispatch_result(None)
        self.assertEqual(normalize_dispatch_result(first), first)
        self.assertEqual(assess(json.loads(first))['state'], 'uncertain')


class HostDispatchEvidenceTests(unittest.IsolatedAsyncioTestCase):
    async def test_host_preserves_false_result(self):
        from main import JarvisLive
        assistant = JarvisLive.__new__(JarvisLive)
        assistant._is_speaking = False
        assistant.ui = SimpleNamespace(set_state=Mock())
        assistant.speak = Mock()
        assistant._application_context = ApplicationContext()
        assistant._action_registry = ActionRegistry({
            'sample': ActionRecord(name='sample', valid=True, handler=Mock(return_value=False))}, Mock())
        assistant._plugin_registry = PluginRegistry({}, Mock())
        response = await assistant._execute_tool_body(
            SimpleNamespace(name='sample', args={}, id='fixture'))
        self.assertIs(response.response['result'], False)

    async def test_shutdown_is_pending_not_finished(self):
        from main import JarvisLive
        assistant = JarvisLive.__new__(JarvisLive)
        assistant._is_speaking = False
        assistant.ui = SimpleNamespace(set_state=Mock(), write_log=Mock())
        assistant._application_context = ApplicationContext()
        assistant._action_registry = ActionRegistry({}, Mock())
        assistant._plugin_registry = PluginRegistry({}, Mock())
        # Do not run the real shutdown task in this isolated regression.
        with patch('main.asyncio.create_task', side_effect=lambda coroutine: coroutine.close()):
            response = await assistant._execute_tool_body(
                SimpleNamespace(name='shutdown_jarvis', args={}, id='fixture'))
        self.assertEqual(assess(response.response['result'])['state'], 'pending')

    async def test_host_does_not_replace_missing_plugin_result_with_success(self):
        from main import JarvisLive
        assistant = JarvisLive.__new__(JarvisLive)
        assistant._is_speaking = False
        assistant.ui = SimpleNamespace(set_state=Mock())
        assistant.speak = Mock()
        assistant._application_context = ApplicationContext()
        assistant._action_registry = ActionRegistry({}, Mock())
        handler = Mock(return_value=None)
        assistant._plugin_registry = PluginRegistry({
            'sample': PluginRecord(name='sample', valid=True, run=handler)}, Mock())
        with patch('core.plugin_loader.get_plugin_enabled', return_value=True):
            response = await assistant._execute_tool_body(
                SimpleNamespace(name='sample', args={}, id='fixture'))
        result = json.loads(response.response['result'])
        self.assertEqual(assess(result)['state'], 'uncertain')
        handler.assert_called_once()

    async def test_host_unknown_tool_reports_not_started(self):
        from main import JarvisLive
        assistant = JarvisLive.__new__(JarvisLive)
        assistant._is_speaking = False
        assistant.ui = SimpleNamespace(set_state=Mock())
        assistant._application_context = ApplicationContext()
        assistant._action_registry = ActionRegistry({}, Mock())
        assistant._plugin_registry = PluginRegistry({}, Mock())
        response = await assistant._execute_tool_body(
            SimpleNamespace(name='missing', args={}, id='fixture'))
        result = json.loads(response.response['result'])
        self.assertEqual(assess(result)['state'], 'failed')
        self.assertFalse(result['execution_started'])


if __name__ == '__main__':
    unittest.main()
