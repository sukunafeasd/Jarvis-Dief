import unittest
from unittest.mock import Mock
from PyQt6.QtCore import QUrl
import test_scene
import test_fui_screens


class InterfaceAuditTests(unittest.TestCase):
    setUpClass=classmethod(test_scene.SceneTests.setUpClass.__func__)
    setUp=test_fui_screens.AllSettingsPagesTests.setUp
    tearDown=test_fui_screens.AllSettingsPagesTests.tearDown
    command=test_scene.SceneTests.command

    def test_status_without_id_replaces_other_domain_instead_of_updating_it(self):
        self.window._show_manifestation({'kind':'weather','title':'CLIMA','temperature':19})
        self.window._show_manifestation({'kind':'status','title':'CONSULTANDO','items':[]})
        self.assertEqual(self.window._presentation['title'],'CONSULTANDO')
        self.assertEqual(self.window._center_split.width(),self.window._scene_stage.width())

    def test_narrated_scene_waits_for_speech_and_pause_does_not_expire(self):
        self.window._show_manifestation({'kind':'tasks','title':'TAREFAS','count':1,'narrationDriven':True,'items':[{'title':'Teste'}]})
        self.assertFalse(self.window._settle_timer.isActive())
        self.window._apply_state('SPEAKING');self.window._advance_presentation(.1)
        self.window._cancel_presentation();self.window._apply_state('LISTENING')
        self.assertFalse(self.window._settle_timer.isActive())
        self.window._apply_state('SPEAKING')
        self.assertTrue(self.window._presentation_clock.cancelled is False)
        self.assertFalse(self.window._presentation.get('narration_active'))

    def test_partial_data_does_not_crash_or_claim_zero_tasks(self):
        self.window._show_manifestation({'kind':'weather','temperature':None,'items':None,'forecast':[None,{'date':None}]})
        self.assertNotIn('None',self.window._content_display.toPlainText())
        self.window._show_manifestation({'kind':'tasks','items':[None,{'title':'Registro real'}]})
        self.assertIn('Registro real',self.window._content_display.toPlainText())

    def test_stale_and_untagged_speech_focus_are_ignored(self):
        self.window._show_manifestation({'kind':'gmail','title':'MENSAGENS','items':[{'title':'Um'},{'title':'Dois'}]})
        self.window._spatial_navigation(QUrl('file:///test#speech-focus-1-1'))
        self.assertEqual(self.window._presentation['focus'],0)
        identifier=self.window._presentation['model']['presentationId']
        self.window._spatial_navigation(QUrl('file:///test#speech-focus-1-2-'+str(identifier)))
        self.assertEqual(self.window._presentation['focus'],1)
        self.assertIsInstance(identifier,str)

    def test_return_uses_new_identity_and_preserves_focus(self):
        self.window._show_manifestation({'kind':'gmail','title':'MENSAGENS','items':[{'title':'Um'},{'title':'Dois'}]})
        self.command('focus','2');old=self.window._presentation['model']['presentationId']
        self.window._show_manifestation({'kind':'weather','title':'CLIMA','temperature':19})
        self.assertTrue(self.command('return')['ok'])
        self.assertNotEqual(old,self.window._presentation['model']['presentationId'])
        self.assertEqual(self.window._presentation['focus'],1)

    def test_completed_scene_does_not_receive_unrelated_speech(self):
        view=Mock(failed=False,_loaded=True)
        self.window._content_spatial=view
        self.window._show_manifestation({'kind':'gmail','title':'MENSAGENS','narrationDriven':True,'items':[{'title':'Um'},{'title':'Dois'}]})
        self.window._apply_state('SPEAKING');self.window._advance_presentation(.1);self.window._apply_state('LISTENING')
        view.page().runJavaScript.reset_mock()
        self.window._narrate_presentation('A segunda tarefa foi concluída.')
        self.window._apply_state('SPEAKING');self.window._advance_presentation(.1)
        self.assertFalse(any('advancePresentation' in call.args[0] for call in view.page().runJavaScript.call_args_list))
        self.window._content_spatial=None

    def test_late_news_completion_is_stamped_even_without_core(self):
        self.window._show_manifestation({'kind':'news','title':'NOTÍCIAS','narrationDriven':True,'items':[{'title':'Teste'}]})
        self.window._apply_state('SPEAKING');self.window._advance_presentation(.1);self.window._apply_state('LISTENING')
        self.assertEqual(self.window._presentation['model'].get('newsPhase'),'settled')

    def test_pin_top_corner_is_really_top_and_panels_do_not_cover_pins(self):
        self.window._show_manifestation({'kind':'weather','title':'CLIMA','temperature':19})
        self.command('pin')
        self.command('move_pin','weather','upper_right')
        self.window._layout_scene(False)
        pin=self.window._pin_previews['weather']['widget'].geometry()
        self.assertLess(pin.y(),100)
        self.window._show_manifestation({'kind':'tasks','title':'TAREFAS','count':1,'items':[{'title':'Teste'}]})
        self.window._layout_scene(False)
        self.assertFalse(pin.intersects(self.window._content_panel.geometry()))

    def test_anonymous_status_end_cannot_close_another_job(self):
        self.window._show_manifestation({'kind':'status','title':'VERIFICANDO','items':[]})
        self.window._show_manifestation({'kind':'status-end'})
        self.assertIsNotNone(self.window._presentation)
        self.window._show_manifestation({'kind':'status','id':'job','title':'VERIFICANDO','items':[]})
        self.window._show_manifestation({'kind':'status-end','id':'job'})
        self.assertIsNone(self.window._presentation)

    def test_new_scene_cannot_finish_without_its_audio(self):
        self.window._apply_state('SPEAKING')
        self.window._show_manifestation({'kind':'news','narrationDriven':True,'items':[{'title':'Nova resposta'}]})
        self.window._apply_state('LISTENING')
        self.assertFalse(self.window._presentation.get('completed',False))
        self.assertNotEqual(self.window._presentation['model'].get('newsPhase'),'front')

    def test_delayed_renderer_queues_cues_and_cancellation_discards_them(self):
        view=Mock(failed=False,_loaded=False)
        self.window._content_spatial=view
        self.window._show_manifestation({'kind':'gmail','narrationDriven':True,'items':[{'title':'Teste'}]})
        self.window._narrate_presentation({'text':'Primeira mensagem.', 'at':0,'duration':.1})
        self.window._advance_presentation(.2)
        self.assertTrue(self.window._presentation['pending_beats'])
        self.window._cancel_presentation()
        self.assertEqual(self.window._presentation['pending_beats'],[])
        self.window._resume_presentation()
        self.assertTrue(self.window._presentation['narration_active'])
        self.window._content_spatial=None

    def test_incomplete_pin_is_readable_and_terminal_avoids_top_pin(self):
        self.window._show_manifestation({'kind':'weather','title':'CLIMA','temperature':None,'condition':None})
        self.command('pin');self.command('move_pin','weather','upper_left')
        self.assertNotIn('None',self.window._pin_previews['weather']['label'].text())
        self.window._content_panel.hide();self.window._open_terminal();self.window._layout_scene(False)
        self.assertFalse(self.window._terminal.geometry().intersects(self.window._pin_previews['weather']['widget'].geometry()))

    def test_four_pins_and_each_domain_fit_the_stage(self):
        models=[{'kind':'weather','title':'CLIMA','temperature':19},
                {'kind':'calendar','title':'AGENDA','items':[{'title':'Compromisso de teste'}]},
                {'kind':'tasks','title':'TAREFAS','count':1,'items':[{'title':'Tarefa de teste'}]},
                {'kind':'system','title':'SISTEMA','cpu_percent':32,'ram_percent':50}]
        for model in models:
            self.window._show_manifestation(model);self.command('pin')
        for width,height in ((820,580),(1366,768)):
            self.window.resize(width,height);self.app.processEvents()
            for kind in ('weather','tasks','calendar','gmail','whatsapp','news','status'):
                self.window._show_manifestation({'kind':kind,'title':'VALIDACAO','items':[{'title':'Registro de teste'}]})
                self.window._layout_scene(False)
                bounds=self.window._scene_stage.rect();panel=self.window._content_panel.geometry()
                self.assertTrue(bounds.contains(panel),(width,height,kind,panel,bounds))
                for item in self.window._pin_previews.values():
                    pin=item['widget'].geometry()
                    self.assertTrue(bounds.contains(pin))
                    self.assertFalse(pin.intersects(panel),(width,height,kind,pin,panel))

    def test_late_renderer_recovers_audio_even_without_transcript_and_keeps_pause(self):
        view=Mock(failed=False,_loaded=False)
        self.window._content_spatial=view
        self.window._show_manifestation({'kind':'tasks','narrationDriven':True,'items':[{'title':'Teste'}]})
        self.window._advance_presentation(.2)
        view._loaded=True;view.page().runJavaScript.reset_mock()
        self.window._presentation_loaded(True)
        self.assertTrue(any('advancePresentation' in call.args[0] for call in view.page().runJavaScript.call_args_list))
        self.window._cancel_presentation();view.page().runJavaScript.reset_mock()
        self.window._presentation_loaded(True)
        self.assertTrue(any('cancelPresentation' in call.args[0] for call in view.page().runJavaScript.call_args_list))
        self.window._content_spatial=None
