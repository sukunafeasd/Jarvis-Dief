import unittest
from PyQt6.QtTest import QTest
from PyQt6.QtCore import QUrl
import test_scene
import test_fui_screens
import test_refresh_visual
from core.presentation_clock import PresentationClock


class ThirdInterfaceAudit(unittest.TestCase):
    setUpClass=classmethod(test_scene.SceneTests.setUpClass.__func__)
    setUp=test_fui_screens.AllSettingsPagesTests.setUp
    tearDown=test_fui_screens.AllSettingsPagesTests.tearDown
    command=test_scene.SceneTests.command

    def test_reopen_during_exit_cancels_old_dismissal(self):
        self.window._show_manifestation({'kind':'weather','title':'CLIMA','temperature':19})
        self.command('settle');self.command('open','weather')
        QTest.qWait(340)
        self.assertIsNotNone(self.window._presentation)
        self.assertTrue(self.window._content_panel.isVisible())

    def test_resume_closed_presentation_shows_it_again(self):
        self.window._show_manifestation({'kind':'news','title':'NOTICIAS','narrationDriven':True,'items':[{'title':'Teste'}]})
        self.command('close','presentation')
        self.assertFalse(self.window._content_panel.isVisible())
        self.assertTrue(self.command('resume')['ok'])
        self.assertTrue(self.window._content_panel.isVisible())

    def test_resume_cannot_report_success_while_resting(self):
        self.window._show_manifestation({'kind':'tasks','title':'TAREFAS','items':[{'title':'Teste'}]})
        self.command('rest','on')
        self.assertFalse(self.command('resume')['ok'])

    def test_open_history_preserves_selected_item(self):
        self.window._show_manifestation({'kind':'gmail','title':'GMAIL','items':[{'title':'Um'},{'title':'Dois'}]})
        self.command('focus','2')
        self.window._show_manifestation({'kind':'weather','title':'CLIMA','temperature':19})
        self.assertTrue(self.command('open','gmail')['ok'])
        self.assertEqual(self.window._presentation['focus'],1)

    def test_bad_transcript_packet_cannot_crash_qt_callback(self):
        self.window._show_manifestation({'kind':'tasks','title':'TAREFAS','narrationDriven':True,'items':[]})
        self.window._narrate_presentation({'duration':1})
        self.window._narrate_presentation(None)
        self.assertFalse(self.window._presentation_clock.pending)

    def test_interrupt_during_exit_preserves_context(self):
        self.window._show_manifestation({'kind':'weather','title':'CLIMA','temperature':19})
        self.command('settle');self.window._cancel_presentation()
        QTest.qWait(340)
        self.assertIsNotNone(self.window._presentation)
        self.assertTrue(self.window._presentation['paused'])

    def test_delayed_focus_callback_cannot_change_paused_scene(self):
        self.window._show_manifestation({'kind':'gmail','title':'GMAIL','items':[{'title':'Um'},{'title':'Dois'}]})
        identifier=self.window._presentation['model']['presentationId']
        self.window._cancel_presentation()
        self.window._spatial_navigation(QUrl('file:///test#speech-focus-1-1-'+identifier))
        self.assertEqual(self.window._presentation['focus'],0)


class ThirdClockAudit(unittest.TestCase):
    def test_resume_of_active_clock_preserves_provider_timestamps(self):
        clock=PresentationClock();clock.advance(.4);clock.resume()
        self.assertEqual(clock.elapsed,.4)

    def test_invalid_text_and_timing_cannot_poison_scheduler(self):
        clock=PresentationClock()
        clock.enqueue(None)
        clock.enqueue('Texto real',at='invalido',duration=float('nan'))
        self.assertEqual(clock.advance(.1)['cues'],['Texto real'])

    def test_invalid_pcm_does_not_mark_audio_active(self):
        clock=PresentationClock()
        for value in (None,float('nan'),float('inf'),-1,True,0):
            clock.advance(value)
        self.assertEqual(clock.elapsed,0)
        self.assertFalse(clock.active)


class ThirdVisualAudit(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=test_refresh_visual.RefreshVisualTests.asyncSetUp
    asyncTearDown=test_refresh_visual.RefreshVisualTests.asyncTearDown

    async def test_resume_origin_does_not_double_count_other_reply_audio(self):
        await self.page.goto(self.url+'/presentation.html')
        await self.page.wait_for_function('typeof window.updateCore === "function"')
        await self.page.evaluate('window.updateCore({kind:"gmail",presentationId:"resume-test",narrationDriven:true,items:[{title:"Teste"}]});window.advancePresentation({elapsed:3,cues:[]});window.cancelPresentation()')
        paused=await self.page.evaluate('window.presentationStatus().audioElapsed')
        await self.page.evaluate('window.resumePresentation(2);window.advancePresentation({elapsed:2.2,cues:[]})')
        resumed=await self.page.evaluate('window.presentationStatus().audioElapsed')
        self.assertAlmostEqual(resumed,paused+.2,places=2)
        self.assertEqual(self.errors,[])
