import base64
import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import Mock,patch
from core.application_context import ApplicationContext
from core.gmail_message import message_view
from core.reference_resolver import resolve_selection
from plugins import gmail_control,whatsapp_web
from actions.send_message import send_message
from actions import organizer,memory_control
from memory import memory_manager
import test_scene


def message(identifier='m2',body='Texto real de teste',next_offset=None):
    return {'id':identifier,'thread_id':'t2','subject':'Assunto de teste','from':'Remetente de teste','body':body,'body_next_offset':next_offset}


class MailWorkflows(unittest.TestCase):
    def test_default_is_all_and_next_keeps_original_query(self):
        context=ApplicationContext()
        with patch.object(gmail_control.gmail,'list_messages',side_effect=[{'ok':True,'messages':[message()],'next_page_token':'token'}, {'ok':True,'messages':[],'next_page_token':''}]) as api:
            self.assertTrue(json.loads(gmail_control.run({'action':'list'},session_memory=context))['ok'])
            self.assertEqual(api.call_args.args,('',20))
            self.assertTrue(json.loads(gmail_control.run({'action':'next','scope':'unread'},session_memory=context))['ok'])
            self.assertEqual(api.call_args.args,('',20,'token'))

    def test_selection_prefers_visible_panel_over_old_page(self):
        context=ApplicationContext();context.record_collection('gmail',[{'id':'old','subject':'Lista anterior'}])
        player=Mock();player.control_interface.return_value={'ok':True,'screen':{'presentation':{'kind':'gmail','visible':True},'references':[{'position':1,'id':'m2','domain':'gmail','title':'Atual'}]}}
        with patch.object(gmail_control.gmail,'read_message',return_value={'ok':True,'message':message()}) as api:
            self.assertTrue(json.loads(gmail_control.run({'action':'read','selection':1},session_memory=context,player=player))['ok'])
            api.assert_called_once_with('m2',20000)
        with patch.object(gmail_control.gmail,'read_message') as api:
            self.assertFalse(json.loads(gmail_control.run({'action':'read','selection':2},session_memory=context,player=player))['ok'])
            api.assert_not_called()

    def test_read_more_advances_and_does_not_invent_extra_chunk(self):
        context=ApplicationContext()
        player=Mock()
        with patch.object(gmail_control.gmail,'read_message',side_effect=[{'ok':True,'message':message(next_offset=20000)}, {'ok':True,'message':message(body='Continuação',next_offset=None)}]) as api:
            gmail_control.run({'action':'read','message_id':'m2'},session_memory=context)
            self.assertTrue(json.loads(gmail_control.run({'action':'read_more'},session_memory=context,player=player))['ok'])
            self.assertIn('Continuação',player.show_manifestation.call_args.args[0]['items'][0]['detail'])
            api.assert_called_with('m2',20000,20000)
            self.assertFalse(json.loads(gmail_control.run({'action':'read_more'},session_memory=context))['ok'])
            self.assertEqual(api.call_count,2)

    def test_thread_selection_mismatch_never_reads_another_conversation(self):
        context=ApplicationContext();context.record_collection('gmail',[message()])
        with patch.object(gmail_control.gmail,'read_thread') as api:
            result=json.loads(gmail_control.run({'action':'read_thread','selection':1,'thread_id':'other'},session_memory=context))
        self.assertFalse(result['ok']);api.assert_not_called()

    def test_empty_plain_alternative_falls_back_to_html(self):
        data=base64.urlsafe_b64encode(b'<p>Conteudo HTML real</p>').decode()
        result=message_view({'id':'m','payload':{'mimeType':'multipart/alternative','parts':[{'mimeType':'text/plain','body':{'data':''}}, {'mimeType':'text/html','body':{'data':data}}]}})
        self.assertEqual(result['body'],'Conteudo HTML real')

    def test_body_chunks_cover_full_content_without_repeating(self):
        text='A'*1000+'B'*600
        item={'id':'m','payload':{'mimeType':'text/plain','body':{'data':base64.urlsafe_b64encode(text.encode()).decode()}}}
        first=message_view(item,max_chars=1000);second=message_view(item,max_chars=1000,offset=first['body_next_offset'])
        self.assertEqual(first['body']+second['body'],text)
        self.assertTrue(first['body_truncated']);self.assertTrue(second['body_complete'])

    def test_missing_message_is_not_reported_as_oauth_failure(self):
        error=Exception();error.resp=Mock(status=404)
        with patch.object(gmail_control.gmail,'read_message',side_effect=error):
            result=json.loads(gmail_control.run({'action':'read','message_id':'m2'}))
        self.assertFalse(result['reconnect_required']);self.assertEqual(result['provider_status'],404)

    def test_thread_has_actual_page_offsets(self):
        from core import gmail_connection as gmail
        records=[{'id':'m'+str(i),'threadId':'t2','payload':{'mimeType':'text/plain','body':{'data':'YQ=='}}} for i in range(3)]
        with patch.object(gmail,'_service') as service:
            service.return_value.users.return_value.threads.return_value.get.return_value.execute.return_value={'id':'t2','messages':records}
            first=gmail.read_thread('t2',2);second=gmail.read_thread('t2',2,20000,first['next_offset'])
        self.assertEqual([m['id'] for m in first['messages']],['m0','m1'])
        self.assertEqual([m['id'] for m in second['messages']],['m2']);self.assertTrue(second['complete'])


class MessagingWorkflows(unittest.TestCase):
    def test_read_chat_uses_exact_contact_from_unread_list(self):
        context=ApplicationContext();context.record_collection('whatsapp_chats',[{'id':'Contato A','contact':'Contato A'}])
        with patch.object(whatsapp_web.transport,'call',return_value={'ok':True,'contact':'Contato A','messages':[]}) as transport:
            result=json.loads(whatsapp_web.run({'action':'read_chat','selection':1},session_memory=context))
        self.assertTrue(result['ok']);transport.assert_called_once_with('read_chat',receiver='Contato A',limit=10)

    def test_uncertain_send_is_structured_and_not_repeated(self):
        context=ApplicationContext();context.observe_user('Envie a mensagem de teste ao contato de teste')
        args={'platform':'wtts','receiver':'Contato de teste','message_text':'Mensagem de teste'}
        with patch('memory.config_manager.get_plugin_enabled',return_value=True),patch('core.whatsapp_web.transport.call',return_value={'ok':False,'uncertain':True,'stage':'confirmation','error':'Sem confirmação'}) as transport:
            first=json.loads(send_message(args,session_memory=context));second=json.loads(send_message(args,session_memory=context))
            self.assertTrue(first['uncertain']);self.assertTrue(second['duplicate_blocked']);self.assertEqual(transport.call_count,1)
            context.observe_user('Já conferi. Faça um novo envio da mensagem de teste.')
            send_message(args,session_memory=context);self.assertEqual(transport.call_count,2)

    def test_other_platform_never_uses_blind_legacy_send(self):
        with patch('actions.send_message._desktop_send') as blind:
            result=json.loads(send_message({'platform':'telegram','receiver':'Contato','message_text':'Texto'}))
        self.assertFalse(result['ok']);blind.assert_not_called()

    def test_expired_ordinal_never_opens_another_contact(self):
        clock=Mock(return_value=0);context=ApplicationContext(clock)
        context.record_collection('whatsapp_chats',[{'id':'A','contact':'A'}]);clock.return_value=601
        with patch.object(whatsapp_web.transport,'call') as transport:
            self.assertFalse(json.loads(whatsapp_web.run({'action':'read_chat','selection':1},session_memory=context))['ok'])
            transport.assert_not_called()


class LocalDataWorkflows(unittest.TestCase):
    def test_organizer_read_update_selection_and_complete_keep_actual_id(self):
        context=ApplicationContext()
        with tempfile.TemporaryDirectory() as folder,patch.object(organizer,'DATABASE',Path(folder)/'organizer.db'):
            created=json.loads(organizer.organizer_action({'domain':'tasks','action':'create','title':'Tarefa de teste'},session_memory=context))
            identity=created['data']['items'][0]['id']
            updated=json.loads(organizer.organizer_action({'domain':'tasks','action':'update','selection':1,'priority':'high'},session_memory=context))
            self.assertEqual(updated['data']['items'][0]['id'],identity);self.assertEqual(updated['data']['items'][0]['priority'],'high')
            read=json.loads(organizer.organizer_action({'domain':'tasks','action':'read','id':identity}))
            self.assertEqual(read['data']['items'][0]['title'],'Tarefa de teste')
            self.assertEqual(json.loads(organizer.organizer_action({'domain':'tasks','action':'complete','id':identity}))['data']['count'],0)

    def test_date_only_end_filter_includes_whole_day_and_bad_filter_does_not_write(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(organizer,'DATABASE',Path(folder)/'organizer.db'):
            organizer.organizer_action({'domain':'calendar','action':'create','title':'Reunião','date':'2026-10-12T14:00'})
            listed=json.loads(organizer.organizer_action({'domain':'calendar','action':'list','date_from':'2026-10-12','date_to':'2026-10-12'}))
            self.assertEqual(listed['data']['count'],1)
            invalid=json.loads(organizer.organizer_action({'domain':'tasks','action':'create','title':'Não criar','date_to':'invalid'}))
            self.assertFalse(invalid['ok']);self.assertEqual(json.loads(organizer.organizer_action({'domain':'tasks','action':'list'}))['data']['count'],0)

    def test_memory_concurrent_writes_and_paginated_structured_read(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(memory_manager,'MEMORY_PATH',Path(folder)/'memory.json'):
            with ThreadPoolExecutor(max_workers=8) as executor:
                list(executor.map(lambda i:memory_manager.update_memory({'notes':{'item_'+str(i):{'value':'Dado de teste '+str(i)}}}),range(30)))
            self.assertEqual(len(memory_manager.load_memory()['notes']),30)
            first=json.loads(memory_control.memory_control({'action':'list','limit':10}))
            second=json.loads(memory_control.memory_control({'action':'list','limit':10,'offset':first['next_offset']}))
            self.assertEqual(first['total'],30);self.assertFalse(first['complete'])
            self.assertFalse({item['id'] for item in first['items']} & {item['id'] for item in second['items']})
            detail=json.loads(memory_control.memory_control({'action':'read','id':first['items'][0]['id']}))
            self.assertTrue(detail['ok']);self.assertIn('Dado de teste',detail['items'][0]['detail'])

    def test_corrupt_memory_is_preserved_and_not_declared_empty(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(memory_manager,'MEMORY_PATH',Path(folder)/'memory.json'):
            memory_manager.MEMORY_PATH.write_text('{invalid',encoding='utf-8')
            before=memory_manager.MEMORY_PATH.read_bytes()
            with self.assertRaises(ValueError):memory_manager.update_memory({'notes':{'test':{'value':'Não sobrescrever'}}})
            self.assertFalse(json.loads(memory_control.memory_control({'action':'list'}))['ok'])
            self.assertEqual(before,memory_manager.MEMORY_PATH.read_bytes())

    def test_window_process_reuse_is_refused(self):
        from core.windows_accessibility import operate
        with patch('core.windows_accessibility.desktop') as desktop:
            window=desktop.return_value.__enter__.return_value.window.return_value.wrapper_object.return_value
            window.process_id.return_value=222
            result=operate({'action':'inspect','handle':4,'expected_process_id':111})
            self.assertFalse(result['ok']);window.descendants.assert_not_called()


class PanelWorkflows(unittest.TestCase):
    setUpClass=classmethod(test_scene.SceneTests.setUpClass.__func__)
    setUp=test_scene.SceneTests.setUp
    tearDown=test_scene.SceneTests.tearDown
    command=test_scene.SceneTests.command

    def test_references_have_domain_tool_bindings_and_legacy_text_inspects(self):
        self.window._show_manifestation({'kind':'tasks','title':'TAREFAS','items':[{'id':42,'title':'Tarefa de teste'}]})
        result=self.command('inspect')
        self.assertEqual(result['screen']['references'][0]['id'],42)
        self.assertEqual(result['screen']['references'][0]['tool'],'organizer')
        self.window._show_content('NOTÍCIAS','1. Texto legado de teste\nDetalhe')
        self.assertTrue(self.command('inspect')['ok'])
        self.assertIn('memory',self.command('catalog')['screen']['catalog']['domains'])

    def test_move_preview_and_close_preserve_other_pins(self):
        self.window._show_manifestation({'kind':'weather','title':'CLIMA','temperature':19})
        self.command('pin');self.window._show_manifestation({'kind':'calendar','title':'AGENDA','items':[{'id':9,'title':'Reunião'}]});self.command('pin')
        self.assertTrue(self.command('move_pin','weather','upper_right')['ok'])
        self.assertEqual(self.window._pin_previews['weather']['slot'],3)
        self.assertFalse(self.window._pin_previews['weather']['widget'].geometry().intersects(self.window._pin_previews['calendar']['widget'].geometry()))
        self.assertTrue(self.command('close')['ok']);self.assertEqual(len(self.window._pin_previews),2)

    def test_rest_is_idempotent_and_does_not_toggle_microphone(self):
        muted=self.window._muted
        self.assertTrue(self.command('rest','on')['ok']);self.assertTrue(self.window._resting)
        self.command('rest','on');self.assertTrue(self.window._resting)
        self.command('rest','off');self.assertFalse(self.window._resting)
        self.assertEqual(self.window._muted,muted)
