import json
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import Mock,patch
from core import confirm,powershell_service as service
from core.system_knowledge import execution_guide
from core.application_context import ApplicationContext
from actions.computer_control import computer_control
from actions.code_helper import _run_file,_has_error
from types import SimpleNamespace


class ShellTests(unittest.TestCase):
    def setUp(self):
        self.patches=[patch.object(confirm,'_pending',None),patch.object(confirm,'_show_cb',Mock()),
            patch.object(confirm,'_hide_cb',Mock()),patch.object(confirm,'_log_cb',Mock()),patch.object(service,'_jobs',{})]
        for item in self.patches:item.start()

    def tearDown(self):
        for item in reversed(self.patches):item.stop()

    def test_real_hidden_shell_unicode_and_exit_status(self):
        result=service.run_script("Write-Output 'DIEF JARVIS ação local'",5)
        self.assertTrue(result['ok']);self.assertIn('ação local',result['stdout'])
        failed=service.run_script('exit 7',5)
        self.assertFalse(failed['ok']);self.assertEqual(failed['exit_code'],7)

    def test_real_timeout_and_output_limit(self):
        result=service.run_script('Start-Sleep -Seconds 5',1)
        self.assertFalse(result['ok']);self.assertTrue(result['uncertain'])
        result=service.run_script("Write-Output ('x' * 20000)",5)
        self.assertTrue(result['truncated']);self.assertLessEqual(len(result['stdout']),12000)

    def test_real_child_inherits_current_token_and_has_no_window(self):
        with patch.object(service.subprocess,'Popen',wraps=service.subprocess.Popen) as spawn:
            result=service.run_script("[Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)",5)
        self.assertTrue(result['ok'])
        self.assertEqual(result['stdout'].strip().lower(),str(service.is_admin()).lower())
        args=spawn.call_args.args[0]
        self.assertIn('-NonInteractive',args);self.assertIn('-NoProfile',args)
        self.assertEqual(spawn.call_args.kwargs['creationflags'],service.subprocess.CREATE_NO_WINDOW)

    def test_admin_execution_is_direct_without_confirmation(self):
        with patch.object(service,'is_admin',return_value=True),patch.object(service,'run_script',return_value={'ok':True,'stdout':'teste'}) as run,patch.object(confirm,'request') as request:
            result=service.execute('Get-Date')
            self.assertTrue(result['completed']);self.assertTrue(result['ok'])
            self.assertFalse(result['confirmation_required']);self.assertEqual(result['state'],'finished')
            run.assert_called_once_with('Get-Date',10,result['job_id']);request.assert_not_called()

    def test_history_read_does_not_reexecute_or_mutate_result(self):
        with patch.object(service,'is_admin',return_value=True),patch.object(service,'run_script',return_value={'ok':True,'stdout':'teste'}) as run:
            prepared=service.execute('Get-Date')
            prepared['result']['stdout']='alterado fora do histórico'
            self.assertEqual(service.result(prepared['job_id'])['result']['stdout'],'teste')
            read=service.result(prepared['job_id']);read['result']['stdout']='alterado'
            self.assertEqual(service.result(prepared['job_id'])['result']['stdout'],'teste')
            run.assert_called_once()

    def test_elevation_must_be_real_and_script_valid(self):
        with patch.object(service,'is_admin',return_value=False),patch.object(service,'run_script') as run:
            with self.assertRaises(ValueError):service.execute('Get-Date')
            run.assert_not_called()
        with patch.object(service,'is_admin',return_value=True):
            for command in ('',None,{},'x'*8193,'Get-Date\x00','Get-Date\u202e'):
                with self.assertRaises(ValueError):service.execute(command)

    def test_multiline_and_longer_commands_no_ui_no_second_permission(self):
        command="Write-Output 'ação'\n"+'# documento solicitado\n'*20+"\tGet-Date"
        with patch.object(confirm,'_show_cb',None),patch.object(service,'is_admin',return_value=True),patch.object(service,'run_script',return_value={'ok':True}) as run:
            result=service.execute(command,120)
            self.assertTrue(result['ok']);self.assertTrue(result['completed'])
            run.assert_called_once_with(command,120,result['job_id'])

    def test_pending_confirmation_cannot_be_replaced(self):
        first=Mock();second=Mock()
        confirm.request('first','Primeiro','Detalhe',first)
        self.assertNotIn('CONFIRMATION_PENDING',confirm.request('second','Segundo','Outro',second))
        confirm.resolve(True)
        until=time.monotonic()+2
        while not first.called and time.monotonic()<until:time.sleep(.01)
        first.assert_called_once();second.assert_not_called()

    def test_other_pending_confirmation_is_not_touched(self):
        first=Mock();confirm.request('first','Primeiro','Detalhe',first)
        with patch.object(service,'is_admin',return_value=True),patch.object(service,'run_script',return_value={'ok':True}) as run:
            self.assertTrue(service.execute('Get-Date')['ok']);run.assert_called_once()
        self.assertEqual(confirm.pending_title(),'Primeiro');first.assert_not_called()

    def test_failure_and_timeout_never_claim_success_or_retry(self):
        for outcome in ({'ok':False,'exit_code':7,'stderr':'teste'},
                        {'ok':False,'uncertain':True,'error':'Tempo esgotado'}):
            with patch.object(service,'is_admin',return_value=True),patch.object(service,'run_script',return_value=outcome) as run:
                result=service.execute('Get-Date')
                self.assertFalse(result['ok']);self.assertTrue(result['completed'])
                self.assertEqual(result['state'],'failed');self.assertEqual(result['result'],outcome)
                self.assertEqual(result['uncertain'],outcome.get('uncertain',False));run.assert_called_once()

    def test_closed_panel_does_not_prevent_execution_or_result(self):
        player=Mock();player.operation_event.side_effect=RuntimeError('painel fechado')
        with patch.object(service,'is_admin',return_value=True),patch.object(service,'run_script',return_value={'ok':True}) as run:
            result=service.execute('Get-Date',player=player)
            self.assertTrue(result['ok']);run.assert_called_once()

    def test_exception_is_recorded_without_retry(self):
        with patch.object(service,'is_admin',return_value=True),patch.object(service,'run_script',side_effect=RuntimeError('teste')) as run:
            result=service.execute('Get-Date')
            self.assertFalse(result['ok']);self.assertTrue(result['uncertain'])
            self.assertTrue(service.result(result['job_id'])['completed']);run.assert_called_once()

    def test_running_job_is_observable_and_history_is_bounded(self):
        observed=[]
        def run(command,timeout,identifier):
            observed.append(service.result(identifier))
            return {'ok':True}
        with patch.object(service,'is_admin',return_value=True),patch.object(service,'run_script',side_effect=run):
            for _ in range(25):service.execute('Get-Date')
        self.assertEqual(len(service._jobs),20)
        self.assertTrue(all(item['state']=='running' and not item['completed'] for item in observed))

    def test_busy_limit_does_not_discard_running_jobs(self):
        service._jobs.update({str(index):{'state':'running','result':None} for index in range(20)})
        with patch.object(service,'is_admin',return_value=True),patch.object(service,'run_script') as run:
            with self.assertRaises(ValueError):service.execute('Get-Date')
            run.assert_not_called()

    def test_status_and_tool_declaration_agree_on_direct_execution(self):
        from actions.powershell_control import TOOL,powershell_control
        with patch.object(service,'is_admin',return_value=True):
            result=json.loads(powershell_control({'action':'status'}))
        self.assertTrue(result['admin']);self.assertFalse(result['confirmation_required'])
        self.assertEqual(result['execution_mode'],'direct');self.assertTrue(result['hidden'])
        self.assertIn('SEM nova confirmação',TOOL['description'])
        guide=execution_guide('use powershell')
        self.assertIn('sem nova confirmação',guide['steps'])
        prompt=(Path(__file__).resolve().parents[1]/'core/prompt.txt').read_text(encoding='utf-8')
        self.assertIn('SEM outra confirmação',prompt)

    def test_action_dispatch_returns_immediate_outcome_not_permission_pending(self):
        from actions.powershell_control import powershell_control
        from core.action_loader import _call_handler
        from core.task_execution import ExecutionLedger
        with patch.object(service,'is_admin',return_value=True),patch.object(service,'run_script',return_value={'ok':True,'stdout':'teste'}) as run,patch.object(confirm,'request') as request:
            response=json.loads(_call_handler(powershell_control,{'action':'execute','command':'Get-Date'},{}))
        self.assertTrue(response['completed']);self.assertEqual(response['result']['stdout'],'teste')
        ledger=ExecutionLedger();ledger.record('powershell_control',response)
        self.assertEqual(ledger.events[-1]['evidence'],'tool_reported')
        request.assert_not_called();run.assert_called_once()

    def test_results_redact_common_key_patterns(self):
        self.assertEqual(service._redact('sk-'+'a'*24),'[credencial ocultada]')


class GuidanceAndLanguageTests(unittest.TestCase):
    def test_vision_coordinates_are_strict_bounded_and_scaled(self):
        from actions.computer_control import _screen_find
        image=Mock();image.size=(2000,1200)
        with patch('actions.computer_control._get_api_key',return_value='fake-test'),patch('actions.computer_control._require_pyautogui'),patch('actions.computer_control.pyautogui.size',return_value=(1000,600)),patch('actions.computer_control.pyautogui.screenshot',return_value=image),patch('core.gemini.call') as call:
            call.return_value=SimpleNamespace(text='1000,600')
            self.assertEqual(_screen_find('campo de busca'),(500,300))
            for text in ('-100,-100','3000,700','clique em 100,200','NOT_FOUND'):
                call.return_value=SimpleNamespace(text=text)
                self.assertIsNone(_screen_find('campo de busca'))
    def test_spotify_followup_and_panel_routes(self):
        context=ApplicationContext();context.select('spotify');context.observe_user('pesquisa uma musica aqui')
        guide=execution_guide(context.user_text,context,[{'name':'app_control'}])
        self.assertEqual(guide['suggested_tool'],'app_control');self.assertEqual(guide['app'],'spotify')
        self.assertFalse(guide['execution_started'])
        self.assertEqual(execution_guide('fixa isso no painel')['suggested_tool'],'interface_control')
        self.assertEqual(execution_guide('veja os emails completos')['suggested_tool'],'gmail_control')
        self.assertEqual(execution_guide('noticias de hoje')['suggested_tool'],'news_briefing')

    def test_unavailable_tool_is_not_reported_connected(self):
        guide=execution_guide('use powershell',declarations=[])
        self.assertEqual(guide['suggested_tool'],'powershell_control');self.assertFalse(guide['tool_available'])
        self.assertTrue(guide['needs_actual_observation'])

    def test_guidance_uses_current_request_not_old_transcript(self):
        context=ApplicationContext();context.select('spotify');context.observe_user('pesquise no excel')
        guide=execution_guide('pesquise no spotify',context,[{'name':'app_control'}])
        self.assertEqual(guide['app'],'spotify')
        self.assertEqual(execution_guide('temperatura da GPU')['suggested_tool'],'system_status')

    def test_personal_data_missing_is_not_invented(self):
        with patch('actions.computer_control._user_profile',return_value={}),patch('actions.computer_control._random_data') as random:
            result=json.loads(computer_control({'action':'user_data','field':'city'}))
            self.assertFalse(result['ok']);random.assert_not_called()

    def test_code_execution_uses_exit_code_not_words(self):
        with patch('actions.code_helper.subprocess.run',return_value=Mock(stdout='error e só um texto',stderr='Aviso informativo',returncode=0)):
            success=_run_file(Path('fixture.py'),[],5)
        self.assertFalse(_has_error(success))
        with patch('actions.code_helper.subprocess.run',return_value=Mock(stdout='',stderr='',returncode=4)):
            self.assertTrue(_has_error(_run_file(Path('fixture.py'),[],5)))

    def test_portuguese_protocol_preserves_runtime_tokens(self):
        text=(Path(__file__).resolve().parents[1]/'core/prompt.txt').read_text(encoding='utf-8')
        for token in ('{assistant_name}','{platform}','{capabilities}','{limits}'):self.assertIn(token,text)
        self.assertIn('[OBSERVAR, AGIR E VERIFICAR]',text)
        self.assertNotIn('obey the instruction',text)
