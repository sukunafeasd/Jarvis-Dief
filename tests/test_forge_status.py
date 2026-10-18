import unittest
from types import SimpleNamespace
from unittest.mock import Mock
from core.forge_status import project_snapshot,summary

class StatusTests(unittest.TestCase):
    def test_late_ultron_snapshot_does_not_change_forge_widgets(self):
        from ui import MainWindow
        token=object()
        owner=SimpleNamespace(_closed_for_shutdown=False,_ultron_polling=token,_ultron_payload=None,
                              _forge_controller=SimpleNamespace(active=True),
                              _ultron_timer=Mock(),_ultron_clock=Mock())
        MainWindow._show_ultron(owner,{'poll_token':token,'state':{'phase':'idle'}})
        self.assertFalse(owner._ultron_polling)

    def test_retryable_validation_is_not_cached(self):
        from core.forge_controller import ForgeController
        key=('project','revision','http://127.0.0.1:1234/candidate')
        owner=SimpleNamespace(phase='ready',generation=1,_validating=key,_validated_revisions=set(),
            _snapshot={'project':{'id':'project'},'candidate_revision':'revision','candidate_preview_url':key[2]})
        ForgeController._validated(owner,{'key':key,'revision':'revision','result':{'accepted':False,'retryable':True}})
        self.assertEqual(owner._validated_revisions,set());self.assertIsNone(owner._validating)

    def test_obsolete_validation_does_not_cache_or_touch_new_project(self):
        from core.forge_controller import ForgeController
        owner=SimpleNamespace(phase='ready',generation=1,_validating=('new','revision','new-url'),_validated_revisions=set(),
            _snapshot={'project':{'id':'new'},'candidate_revision':'revision','candidate_preview_url':'new-url'})
        ForgeController._validated(owner,{'key':('old','revision','old-url'),'revision':'revision','result':{'accepted':True}})
        self.assertEqual(owner._validated_revisions,set());self.assertEqual(owner._validating,('new','revision','new-url'))
    def test_status_questions_never_start_another_creation(self):
        from core.forge_commands import command_for
        for text in ('Jarvis, qual o progresso?','como ta ficando','terminou','o que aconteceu'):
            self.assertEqual(command_for(text)['action'],'status')
    def test_raw_commands_and_fragments_are_not_displayed(self):
        state={'phase':'running','authenticated':True,'project':{'name':'Projeto'},'activities':[
            {'title':'Command execution','detail':'cmd --secret something','status':'running'}]}
        result=project_snapshot(state)
        self.assertNotIn('cmd',str(result));self.assertNotIn('--secret',str(result))
        self.assertEqual(len(result['activities']),1)

    def test_completed_files_are_not_false_render_success(self):
        status=summary({'phase':'idle','generation_verified':True,'preview_validation':'pending'})
        self.assertEqual(status['title'],'Conferindo a previa')
        status=summary({'phase':'idle','generation_verified':True,'preview_error':'Imagem vazia'})
        self.assertEqual(status['status'],'failed')

    def test_preview_is_ready_only_after_validation(self):
        status=summary({'phase':'ready','preview_validation':'passed','preview_url':'http://127.0.0.1/a'})
        self.assertEqual(status['title'],'Previa pronta')
