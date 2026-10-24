import json
import unittest
from unittest.mock import Mock, patch
from core.application_context import ApplicationContext
from core.reference_resolver import resolve_selection
from actions.memory_control import memory_control


class ReferenceGrounding(unittest.TestCase):
    def setUp(self):
        self.context=ApplicationContext()
        self.context.record_collection('tasks',[{'id':'old','title':'Cached'}])
        self.player=Mock()

    def test_failed_inspection_never_falls_back_to_stale_list(self):
        for result in ({'ok':False,'error':'Timeout'},{},None,[],False,'unavailable'):
            with self.subTest(result=result):
                self.player.control_interface.return_value=result
                with self.assertRaises(ValueError):resolve_selection('tasks',1,self.context,self.player)

    def test_visible_selection_is_retained_for_followup(self):
        self.player.control_interface.return_value={'ok':True,'screen':{
            'presentation':{'visible':True,'kind':'tasks'},
            'references':[{'domain':'tasks','position':1,'id':'visible','title':'Current'}]}}
        self.assertEqual(resolve_selection('tasks',1,self.context,self.player)['id'],'visible')
        self.assertEqual(self.context.selection('tasks')['id'],'visible')

    def test_malformed_scene_does_not_select_cached_target(self):
        for screen in (None,{'presentation':None},
                       {'presentation':{'visible':True,'kind':'tasks'},'references':None},
                       {'presentation':{'visible':True,'kind':'tasks'},'references':[None,{'position':True,'domain':'tasks','id':'wrong'}]}):
            with self.subTest(screen=screen):
                self.player.control_interface.return_value={'ok':True,'screen':screen}
                with self.assertRaises(ValueError):resolve_selection('tasks',1,self.context,self.player)

    def test_hidden_presentation_still_uses_consulted_list(self):
        self.player.control_interface.return_value={'ok':True,'screen':{'presentation':{'visible':False}}}
        self.assertEqual(resolve_selection('tasks',1,self.context,self.player)['id'],'old')

    def test_malformed_visible_id_is_not_retained_as_selection(self):
        for identifier in ('', '  ', True, {}, []):
            with self.subTest(identifier=identifier):
                self.player.control_interface.return_value={'ok':True,'screen':{
                    'presentation':{'visible':True,'kind':'tasks'},
                    'references':[{'domain':'tasks','position':1,'id':identifier}]}}
                with self.assertRaises(ValueError):resolve_selection('tasks',1,self.context,self.player)
                self.assertNotIn('tasks',self.context.snapshot()['selections'])

    def test_alias_collection_remembers_visible_contact(self):
        self.player.control_interface.return_value={'ok':True,'screen':{
            'presentation':{'visible':True,'kind':'whatsapp'},
            'references':[{'domain':'whatsapp','position':1,'id':'Alice'}]}}
        resolve_selection('whatsapp',1,self.context,self.player,'whatsapp_chats')
        self.assertEqual(self.context.selection('whatsapp_chats')['contact'],'Alice')

    def test_explicit_memory_id_cannot_be_replaced_by_other_selection(self):
        records=[{'id':'facts/one','detail':'First'},{'id':'facts/two','detail':'Second'}]
        self.context.record_collection('memory',records)
        with patch('actions.memory_control.load_memory',return_value={}), patch('actions.memory_control.ranked_memory_records',return_value=records):
            result=json.loads(memory_control({'action':'read','id':'facts/two','selection':1},session_memory=self.context))
        self.assertFalse(result['ok'])
        self.assertIn('nao correspondem',result['error'])


if __name__=='__main__':unittest.main()
