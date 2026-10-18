import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from core import google_services as google
from core import windows_autostart as startup
from core.live_pins import specification


class BirthdayTests(unittest.TestCase):
    def test_default_excludes_automatic_birthdays_not_custom_events(self):
        api = Mock()
        api.events.return_value.list.return_value.execute.return_value = {
            'items': [{'id':'birthday','eventType':'birthday'},
                      {'id':'trip','eventType':'fromGmail'},
                      {'id':'party','summary':'Aniversario da empresa'}],
            'nextPageToken': 'next'}
        with patch.object(google, 'service', return_value=api):
            result = google.calendar({'action':'list'})
        types = api.events.return_value.list.call_args.kwargs['eventTypes']
        self.assertNotIn('birthday', types)
        self.assertIn('fromGmail', types)
        self.assertEqual([item['id'] for item in result['items']], ['trip','party'])
        self.assertFalse(result['complete'])
        self.assertEqual(result['next_page_token'], 'next')

    def test_explicit_birthdays_survive_pin_specification(self):
        api = Mock()
        api.events.return_value.list.return_value.execute.return_value = {
            'items':[{'id':'birthday','eventType':'birthday'}]}
        spec = specification({'kind':'calendar','refresh':{
            'provider':'google_calendar','parameters':{'action':'list','include_birthdays':True}}})
        with patch.object(google, 'service', return_value=api):
            result = google.calendar(spec['parameters'])
        self.assertNotIn('eventTypes', api.events.return_value.list.call_args.kwargs)
        self.assertEqual(result['items'][0]['id'], 'birthday')


def fixture_task(sid):
    action = SimpleNamespace(Type=0, Arguments='', Path=str(startup.PROJECT/'DIEF JARVIS.exe'),
                             WorkingDirectory=str(startup.PROJECT))
    trigger = SimpleNamespace(Type=9, UserId=sid, Enabled=True)
    return SimpleNamespace(Name=startup.task_name(sid), Enabled=True, Definition=SimpleNamespace(
        Principal=SimpleNamespace(UserId=sid, LogonType=3, RunLevel=1),
        Actions=SimpleNamespace(Count=1, Item=lambda index:action),
        Triggers=SimpleNamespace(Count=1, Item=lambda index:trigger)))


class AutostartTests(unittest.TestCase):
    def test_profile_reports_verified_state_not_optimistic_success(self):
        from core.settings_hub import SettingsHub
        hub = SimpleNamespace(autostart=Mock(), autostart_notice=Mock(), window=Mock())
        with patch.object(startup, 'set_enabled', side_effect=PermissionError), \
                patch.object(startup, 'enabled', return_value=True):
            SettingsHub._set_windows_autostart(hub, False)
        hub.autostart.setChecked.assert_called_once_with(True)
        self.assertIn('Não consegui', hub.autostart_notice.setText.call_args.args[0])

    def test_profile_can_disable_verified_task(self):
        from core.settings_hub import SettingsHub
        hub = SimpleNamespace(autostart=Mock(), autostart_notice=Mock(), window=Mock())
        with patch.object(startup, 'set_enabled') as register, \
                patch.object(startup, 'enabled', return_value=False):
            SettingsHub._set_windows_autostart(hub, False)
        register.assert_called_once_with(False)
        hub.autostart.setChecked.assert_called_once_with(False)
        self.assertIn('desativado', hub.autostart_notice.setText.call_args.args[0])

    def test_windows_can_return_account_name_instead_of_sid(self):
        sid = 'S-1-5-21-123'
        task = fixture_task(sid)
        task.Definition.Principal.UserId = 'PC\\example'
        task.Definition.Triggers.Item(1).UserId = 'PC\\example'
        with patch('win32security.LookupAccountName', return_value=('opaque-sid','PC',1)), \
                patch('win32security.ConvertSidToStringSid', return_value=sid):
            self.assertTrue(startup.matches(task, sid))

    def test_managed_installation_uses_launcher_outside_version_folder(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            with patch.object(startup, 'PROJECT', root/'versions'/'1.0.0'), \
                    patch.dict(startup.os.environ, {'DIEF_MANAGED_ROOT':str(root)}):
                self.assertEqual(startup.launch_root(), root)

    def test_unrelated_managed_root_is_refused(self):
        with tempfile.TemporaryDirectory() as temp, \
                patch.dict(startup.os.environ, {'DIEF_MANAGED_ROOT':temp}):
            with self.assertRaises(ValueError):
                startup.launch_root()

    def test_status_rejects_wrong_identity_arguments_or_unelevated_task(self):
        sid = 'S-1-5-21-123'
        task = fixture_task(sid)
        self.assertTrue(startup.matches(task, sid))
        task.Definition.Principal.RunLevel = 0
        self.assertFalse(startup.matches(task, sid))
        task.Definition.Principal.RunLevel = 1
        task.Definition.Actions.Item(1).Arguments = '--anything'
        self.assertFalse(startup.matches(task, sid))
        self.assertFalse(startup.matches(fixture_task(sid), 'S-1-5-21-456'))

    def test_registration_uses_current_user_interactive_highest_no_password(self):
        sid = 'S-1-5-21-123'
        service, folder = Mock(), Mock()
        folder.GetTasks.side_effect = [[], [fixture_task(sid)]]
        with tempfile.TemporaryDirectory() as temp, \
                patch.object(startup, 'PREFERENCE', Path(temp)/'autostart.json'), \
                patch('core.elevation.is_admin', return_value=True), \
                patch.object(startup, 'with_scheduler', side_effect=lambda callback: callback(service,folder,sid)), \
                patch.object(startup, 'remove_legacy') as legacy:
            startup.set_enabled(True)
            self.assertEqual(json.loads(startup.PREFERENCE.read_text()), {'enabled':True})
        definition = service.NewTask.return_value
        self.assertEqual(definition.Principal.UserId, sid)
        self.assertEqual(definition.Principal.LogonType, 3)
        self.assertEqual(definition.Principal.RunLevel, 1)
        self.assertEqual(definition.Triggers.Create.call_args.args, (9,))
        self.assertEqual(definition.Actions.Create.return_value.Path, str(startup.PROJECT/'DIEF JARVIS.exe'))
        self.assertEqual(definition.Settings.ExecutionTimeLimit, 'PT0S')
        self.assertFalse(definition.Settings.StopIfGoingOnBatteries)
        self.assertEqual(folder.RegisterTaskDefinition.call_args.args[-3:], (sid,None,3))
        legacy.assert_called_once()

    def test_unconfirmed_registration_does_not_remove_old_startup(self):
        service, folder = Mock(), Mock()
        folder.GetTasks.return_value = []
        with patch('core.elevation.is_admin', return_value=True), \
                patch.object(startup, 'with_scheduler', side_effect=lambda callback: callback(service,folder,'sid')), \
                patch.object(startup, 'atomic_write') as write, \
                patch.object(startup, 'remove_legacy') as legacy:
            with self.assertRaises(RuntimeError):
                startup.set_enabled(True)
        write.assert_not_called()
        legacy.assert_not_called()

    def test_disable_removes_only_owned_task_and_persists_opt_out(self):
        sid = 'S-1-5-21-123'
        folder = Mock()
        folder.GetTasks.side_effect = [[fixture_task(sid)], []]
        with tempfile.TemporaryDirectory() as temp, \
                patch.object(startup, 'PREFERENCE', Path(temp)/'autostart.json'), \
                patch('core.elevation.is_admin', return_value=True), \
                patch.object(startup, 'with_scheduler', side_effect=lambda callback: callback(Mock(),folder,sid)), \
                patch.object(startup, 'remove_legacy'):
            startup.set_enabled(False)
            self.assertFalse(json.loads(startup.PREFERENCE.read_text())['enabled'])
        folder.DeleteTask.assert_called_once_with(startup.task_name(sid), 0)

    def test_default_does_not_override_opt_out(self):
        with tempfile.TemporaryDirectory() as temp, \
                patch.object(startup, 'PREFERENCE', Path(temp)/'autostart.json'), \
                patch.dict(startup.os.environ, {}, clear=True), \
                patch.object(startup, 'set_enabled') as register:
            startup.PREFERENCE.write_text('{"enabled":false}')
            startup.ensure_default()
        register.assert_not_called()

    def test_non_admin_cannot_register_task(self):
        with patch('core.elevation.is_admin', return_value=False), \
                patch.object(startup, 'with_scheduler') as connect:
            with self.assertRaises(PermissionError):
                startup.set_enabled(True)
        connect.assert_not_called()
