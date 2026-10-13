import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch
import test_scene
import test_fui_screens
import test_refresh_visual
from core import daily_briefing
from core.briefing_presentation import explicit_refresh


class RefreshPolicyAudit(unittest.TestCase):
    def test_explicit_refresh_bypasses_daily_cooldown(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(daily_briefing,'STATE_FILE',Path(folder)/'daily.json'):
            now=datetime.now()
            daily_briefing.STATE_FILE.write_text(json.dumps({'date':now.date().isoformat(),'updated_at':now.isoformat()}))
            for text in ('me atualiza','Jarvis, se atualiza do dia','atualize meu dia','resumo do dia'):
                self.assertTrue(explicit_refresh(text),text)
                self.assertTrue(daily_briefing.refresh_due(text,now),text)
            self.assertFalse(explicit_refresh('atualize o Windows'))


class RefreshBackendAudit(unittest.IsolatedAsyncioTestCase):
    async def test_early_contact_does_not_cancel_first_opening_refresh(self):
        from main import JarvisLive
        assistant=JarvisLive.__new__(JarvisLive)
        assistant.session=Mock();assistant._manual_rest=False
        assistant._application_context=Mock(user_text='Abre o aplicativo')
        assistant._queue_daily_briefing=Mock(return_value=True)
        with patch('main.asyncio.sleep',new=AsyncMock()):
            await assistant._opening_greeting()
        assistant._queue_daily_briefing.assert_called_once_with(startup=True,wait_for_turn=True)

    async def test_manual_request_works_when_automatic_summary_is_disabled(self):
        from main import JarvisLive
        assistant=JarvisLive.__new__(JarvisLive)
        assistant._application_context=Mock(user_text='me atualiza');assistant._manual_rest=False
        assistant._daily_briefing_task=None;assistant._daily_briefing_after_contact=AsyncMock();assistant.ui=Mock()
        with patch('main.get_brief_enabled',return_value=False),patch.object(daily_briefing,'record_contact'),patch.object(daily_briefing,'delivered_today',return_value=True),patch.object(daily_briefing,'refresh_due',return_value=True):
            self.assertTrue(assistant._queue_daily_briefing(wait_for_turn=False))
            await assistant._daily_briefing_task

    async def test_startup_does_not_require_user_greeting(self):
        from main import JarvisLive
        assistant=JarvisLive.__new__(JarvisLive)
        assistant._application_context=Mock(user_text='');assistant._manual_rest=False
        assistant._daily_briefing_task=None;assistant._daily_briefing_after_contact=AsyncMock();assistant.ui=Mock()
        with patch('main.get_brief_enabled',return_value=True),patch.object(daily_briefing,'record_contact'),patch.object(daily_briefing,'delivered_today',return_value=False):
            self.assertTrue(assistant._queue_daily_briefing(startup=True,wait_for_turn=False))
            await assistant._daily_briefing_task
            assistant._daily_briefing_after_contact.assert_awaited_once_with(False)

    async def test_no_audio_never_marks_summary_delivered(self):
        from main import JarvisLive
        assistant=JarvisLive.__new__(JarvisLive)
        assistant.session=Mock();assistant._manual_rest=False;assistant._awake=True
        assistant._is_speaking=False;assistant.audio_in_queue=asyncio.Queue()
        assistant._tail_active=Mock(return_value=False);assistant._turn_done_event=asyncio.Event();assistant.ui=Mock()
        async def complete(**kwargs):assistant._turn_done_event.set()
        assistant.session.send_client_content=AsyncMock(side_effect=complete)
        with patch('core.session_refresh.collect_updates',new=AsyncMock(return_value={'data':{'tasks':{'count':2}},'unavailable':[]})),patch.object(daily_briefing,'mark_delivered') as delivered:
            with self.assertRaises(RuntimeError):await assistant._send_startup_briefing()
            delivered.assert_not_called()
            self.assertTrue(assistant.ui.show_manifestation.call_args.args[0]['retain'])
            self.assertFalse(assistant._refresh_in_progress)


class RefreshPanelAudit(unittest.TestCase):
    setUpClass=classmethod(test_scene.SceneTests.setUpClass.__func__)
    setUp=test_fui_screens.AllSettingsPagesTests.setUp
    tearDown=test_fui_screens.AllSettingsPagesTests.tearDown

    def begin(self):
        self.window._show_manifestation({'kind':'status','id':'transaction-1','refreshTransaction':True,'items':[],'total':3,'completed':0})

    def test_unrelated_data_cannot_remove_refresh(self):
        self.begin()
        self.window._show_manifestation({'kind':'weather','temperature':19})
        self.assertEqual(self.window._presentation['model']['id'],'transaction-1')
        self.assertTrue(self.window._content_panel.isVisible())

    def test_owned_chapter_can_follow_collection(self):
        self.begin()
        self.window._show_manifestation({'kind':'tasks','refreshOwner':'transaction-1','count':2})
        self.assertEqual(self.window._presentation['model']['kind'],'tasks')
        self.window._show_manifestation({'kind':'status-end','id':'transaction-1'})
        self.assertIsNone(self.window._refresh_lock)

    def test_old_end_cannot_close_or_expire_new_refresh(self):
        self.begin()
        self.window._show_manifestation({'kind':'status-end','id':'old-transaction','retain':True})
        self.assertEqual(self.window._refresh_lock,'transaction-1')
        self.assertFalse(self.window._settle_timer.isActive())


class RefreshVisualAudit(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=test_refresh_visual.RefreshVisualTests.asyncSetUp
    asyncTearDown=test_refresh_visual.RefreshVisualTests.asyncTearDown

    async def test_refresh_bar_reports_real_completion(self):
        await self.page.set_viewport_size({'width':540,'height':420})
        await self.page.goto(self.url+'/presentation.html')
        await self.page.wait_for_function('typeof window.updateCore === "function"')
        model={'kind':'status','refreshTransaction':True,'id':'audit-refresh','title':'ATUALIZANDO','completed':1,'total':3,
               'items':[{'title':'Noticias','status':'ok','detail':'Consultado'},{'title':'Agenda','status':'working','detail':'Consultando'},{'title':'Clima','status':'working','detail':'Consultando'}]}
        await self.page.evaluate('m=>window.updateCore(m)',model)
        self.assertEqual(await self.page.locator('[role=progressbar]').get_attribute('aria-valuenow'),'33')
        self.assertIn('Agenda',await self.page.locator('#summary').inner_text())
        await self.page.wait_for_timeout(3500)
        self.assertEqual(await self.page.locator('[role=progressbar]').get_attribute('aria-valuenow'),'33')
        model['completed']=3
        for item in model['items']:item.update(status='ok',detail='Consultado')
        await self.page.evaluate('m=>window.updateCore(m)',model)
        self.assertEqual(await self.page.locator('[role=progressbar]').get_attribute('aria-valuenow'),'100')
        await self.page.wait_for_timeout(250)
        self.assertIn('data:image',await self.page.evaluate('getComputedStyle(document.body).backgroundImage'))
        await self.page.screenshot(path=str(test_refresh_visual.BASE/'validation/daily-refresh-card.png'))
        self.assertEqual(self.errors,[])


class SoundAudit(unittest.TestCase):
    def test_original_cues_are_bounded_pcm(self):
        from core.ui_sounds import cue_pcm,TONES
        for name in TONES:
            data=cue_pcm(name)
            self.assertGreater(len(data),100)
            self.assertLessEqual(len(data),22050*12 if name=='ambient' else 22050)
            self.assertEqual(len(data)%2,0)

    def test_effects_are_ducked_and_rate_limited(self):
        from core.ui_sounds import SoundDirector
        director=SoundDirector(None);director.enabled=True
        effect=Mock();effect.isPlaying.return_value=False
        director.effects={'click':effect}
        director.voice(True)
        self.assertTrue(director.play('click'))
        effect.setVolume.assert_called_with(.055)
        self.assertFalse(director.play('click'))
