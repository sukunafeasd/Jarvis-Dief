import json
import unittest
from pathlib import Path
from unittest.mock import patch
from core import resource_policy,resource_manual,connection_states
from core.plugin_loader import discover_plugins


class PolicyTests(unittest.TestCase):
    def test_local_availability_is_dependency_checked_not_fake_connection(self):
        with patch.object(resource_policy.importlib.util,'find_spec',return_value=None):
            result=resource_policy.local_status('office_resources')
        self.assertFalse(result['local_available']);self.assertFalse(result['account_required'])
        plugin={'valid':True,'enabled':True}
        self.assertEqual(connection_states.resolve('plugin:office_resources',result,plugin=plugin),'error')
        result=resource_policy.local_status('task_execution')
        self.assertTrue(result['local_available'])
        self.assertEqual(connection_states.resolve('plugin:task_execution',result,plugin=plugin),'available')

    def test_checklist_has_all_32_without_claiming_pending_work_connected(self):
        result=resource_manual.catalog()
        self.assertEqual([item['number'] for item in result['items']],list(range(1,33)))
        self.assertTrue(any(item['implementation']=='partial' for item in result['items']))
        self.assertTrue(all(item['connection_verified'] is False for item in result['items']))
        for item in result['items']:self.assertIn(item['tool'],resource_manual.GUIDES)

    def test_every_plugin_has_manual_and_described_arguments_without_metadata_mutation(self):
        registry=discover_plugins(Path(__file__).resolve().parents[1]/'plugins',set(),logger=lambda _:None)
        with patch('core.plugin_loader.get_plugin_enabled',return_value=True):
            declarations=registry.get_tool_declarations()
            for declaration in declarations:
                self.assertIn(declaration['name'],resource_manual.GUIDES)
                self.assertIn('resource_diagnostics guide',declaration['description'])
                for key,schema in declaration['parameters']['properties'].items():
                    if key in resource_manual.PARAMETER_HELP:self.assertTrue(schema.get('description'),(declaration['name'],key))
            first=next(item for item in declarations if item['name']=='file_library')
            first['parameters']['properties']['action']['enum'].append('invented')
            self.assertNotIn('invented',registry._plugins['file_library'].parameters['properties']['action']['enum'])
        with self.assertRaises(ValueError):resource_manual.guide('invented_tool')

    def test_manual_examples_match_real_plugin_action_enums(self):
        registry=discover_plugins(Path(__file__).resolve().parents[1]/'plugins',set(),logger=lambda _:None)
        for name,record in registry._plugins.items():
            guide=resource_manual.guide(name)
            example=guide['example']
            self.assertFalse(guide['example_is_executable'])
            self.assertIn(example['action'],record.parameters['properties']['action']['enum'],name)

    def test_outlook_does_not_reuse_cache_for_wrong_app_or_account(self):
        from core import outlook_service
        stored={'cache':'fixture','account':'first@example.com','client_id':'old-app'}
        with patch.object(outlook_service.tokens,'read',return_value=stored),patch.object(outlook_service,'configuration',return_value={'client_id':'new-app'}):
            self.assertFalse(outlook_service.status()['connected'])
        with patch.object(outlook_service.tokens,'read',return_value=stored),patch.object(outlook_service,'configuration',return_value={'client_id':'old-app','expected_email':'other@example.com'}):
            self.assertFalse(outlook_service.status()['connected'])

    def test_spotify_wrong_account_does_not_replace_previous_token(self):
        from unittest.mock import Mock
        from core import spotify_service
        manager=Mock();manager.get_access_token.return_value='fixture';manager.cache_handler.get_cached_token.return_value={'refresh_token':'fixture'}
        with patch.object(spotify_service,'auth',return_value=manager),patch.object(spotify_service,'config',return_value={'client_id':'fixture','expected_account_id':'expected'}),patch('spotipy.Spotify') as api,patch.object(spotify_service.tokens,'write') as write:
            api.return_value.current_user.return_value={'id':'wrong','display_name':'Wrong'}
            self.assertFalse(spotify_service.connect()[0]);write.assert_not_called()
            manager.get_access_token.assert_called_once_with(check_cache=False)

    def test_spotify_correct_account_is_committed_after_profile_check(self):
        from unittest.mock import Mock
        from core import spotify_service
        manager=Mock();manager.get_access_token.return_value='fixture';manager.cache_handler.get_cached_token.return_value={'refresh_token':'fixture'}
        with patch.object(spotify_service,'auth',return_value=manager),patch.object(spotify_service,'config',return_value={'client_id':'fixture','expected_account_id':'expected'}),patch('spotipy.Spotify') as api,patch.object(spotify_service.tokens,'write') as write:
            api.return_value.current_user.return_value={'id':'expected','display_name':'Right'}
            self.assertTrue(spotify_service.connect()[0])
            self.assertEqual(write.call_args.args[1]['jarvis_account_id'],'expected')
