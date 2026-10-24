"""Synthetic Spectro marking regressions; no desktop provider is opened."""
import json
import time
import unittest
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import Mock,patch

from actions import spectro_control as action
from core.action_loader import ActionRegistry,_validate
from core.spectro_commands import request
from core.spectro_observer import Observer
from core import spectro_perception as perception
from core import windows_accessibility as accessibility


class MarkingRouting(unittest.TestCase):
    def test_named_foreground_requests_reach_registered_handler(self):
        record=_validate(action,'spectro_control.py')
        self.assertTrue(record.valid)
        registry=ActionRegistry({record.name:record},Mock())
        player=SimpleNamespace(control_interface=Mock(return_value={'ok':True,'completed':False}))
        for phrase,shape in [('marque o icone Salvar na aba em primeiro plano','outline'),
                             ('pode destacar o botao Salvar nesta janela ativa','outline'),
                             ('circule o objeto Salvar','circle')]:
            with self.subTest(phrase=phrase):
                operation,settings=request(phrase,True)
                self.assertEqual(settings,{'query':'salvar','shape':shape})
                result=json.loads(registry.run(record.name,{'operation':operation,**settings},{'player':player}))
                self.assertTrue(result['ok']);self.assertFalse(result['completed'])
                player.control_interface.assert_called_with('spectro','highlight',json.dumps(settings))
        self.assertIn('query',registry.get_tool_declarations()[0]['parameters']['properties'])

    def test_noncommands_and_inactive_mode_do_not_mark(self):
        for phrase in ('nao marque o icone Salvar','como marcar o icone Salvar',
                       'e se voce marcar o icone Salvar','marque todos os objetos na aba'):
            self.assertIsNone(request(phrase,True))
        self.assertIsNone(request('marque o icone Salvar',False))

    def observer(self):
        store=Mock();store.read.return_value={'allowed_apps':[]}
        observer=Observer(store);observer.enabled=True
        observer.current={'ok':True,'handle':1,'process_id':2,'observed_at':time.time(),
                          'controls':[{'control_id':'real','name':'Configuracoes'}]}
        return observer

    def test_name_resolution_requires_unique_current_evidence(self):
        observer=self.observer()
        with patch.object(perception,'foreground',return_value={'ok':True,'handle':1,'process_id':2}):
            observer.highlight(query='CONFIGURACOES')
            self.assertEqual(observer.target,'real');self.assertIsNone(observer.target_result)
            for controls in ([],[{'control_id':'x','name':'Configuracoes'},{'control_id':'y','name':'Configuracoes'}]):
                observer.current['controls']=controls
                with self.assertRaises(ValueError):observer.highlight(query='Configuracoes')
                self.assertEqual(observer.target,'real')

    def test_paused_or_sensitive_context_never_resolves_target(self):
        observer=self.observer();observer.enabled=False
        with patch.object(perception,'foreground') as foreground:
            with self.assertRaises(ValueError):observer.highlight(query='Configuracoes')
            foreground.assert_not_called()
        observer.enabled=True
        with patch.object(perception,'foreground',return_value={'ok':False,'handle':1,'process_id':2}):
            with self.assertRaises(ValueError):observer.highlight(query='Configuracoes')
        self.assertIsNone(observer.target)

    def test_rejected_highlight_preserves_existing_style_and_drawing_guard(self):
        from core.spectro import SpectroController
        controller=SimpleNamespace(observer=Mock(),annotations=Mock(),_drawing_window=(1,2),_target_color='#ffffff')
        controller.observer.highlight.side_effect=ValueError('ambiguous')
        with self.assertRaises(ValueError):
            SpectroController._perception_command(controller,'highlight',{'query':'Save','color':'vermelho'})
        self.assertEqual(controller._drawing_window,(1,2));self.assertEqual(controller._target_color,'#ffffff')
        controller.annotations.clear.assert_not_called()

    def test_bad_annotation_color_does_not_clear_visible_layer(self):
        from core.spectro_annotations import Annotations
        annotations=Annotations(Mock());annotations.clear=Mock()
        with patch('core.spectro_annotations.logical_target') as locate:
            with self.assertRaises(ValueError):annotations.show_target([1,2,3,4],color='invalid')
        annotations.clear.assert_not_called();locate.assert_not_called()


class NestedForegroundControls(unittest.TestCase):
    def test_nested_target_is_discovered_and_revalidated_with_same_depth(self):
        state={'ok':True,'handle':7,'process_id':12,'app':'fixture.exe'}
        window=Mock();window.handle=7;window.process_id.return_value=12;window.window_text.return_value='Fixture'
        control=Mock();control.element_info=SimpleNamespace(name='Save',runtime_id=(1,2),automation_id='save',
            control_type='Button',element=SimpleNamespace(CurrentIsPassword=False))
        control.rectangle.return_value=SimpleNamespace(left=10,top=20,width=lambda:30,height=lambda:40)
        window.iter_descendants.side_effect=lambda depth:iter([control] if depth>=9 else [])
        root=Mock();root.window.return_value.wrapper_object.return_value=window
        @contextmanager
        def desktop():yield root
        with patch.object(accessibility,'desktop',desktop),patch.dict(accessibility._observations,{},clear=True), \
             patch.object(perception,'foreground',return_value=state) as foreground:
            observed=perception.inspect_foreground({'fixture.exe'})
            token=observed['controls'][0]['control_id']
            self.assertEqual(observed['limits']['depth'],12)
            self.assertEqual(perception.target_rect(token,{'fixture.exe'})['rect'],[10,20,30,40])
            window.process_id.return_value=99
            with self.assertRaises(ValueError):perception.target_rect(token,{'fixture.exe'})
            window.process_id.return_value=12
            foreground.side_effect=[state,{**state,'process_id':99}]
            with self.assertRaises(ValueError):perception.target_rect(token,{'fixture.exe'})


if __name__=='__main__':unittest.main()
