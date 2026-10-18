import hashlib
import unittest
from unittest.mock import Mock, patch
import test_refresh_visual


class CommunicationModels(unittest.TestCase):
    def test_gmail_list_creates_actual_header_presentation(self):
        from plugins.gmail_control import run
        player=Mock()
        with patch('plugins.gmail_control.gmail.list_messages',return_value={'ok':True,'messages':[{'id':'test','subject':'Assunto de teste','from':'Remetente de teste'}]}):
            run({'action':'list'},player=player)
        model=player.show_manifestation.call_args.args[0]
        self.assertEqual(model['kind'],'gmail')
        self.assertEqual(model['items'][0]['title'],'Assunto de teste')


class PresentationUpgradeTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=test_refresh_visual.RefreshVisualTests.asyncSetUp
    asyncTearDown=test_refresh_visual.RefreshVisualTests.asyncTearDown

    async def test_symbols_move_and_compact_previews_keep_data(self):
        await self.page.goto(self.url+'/presentation.html')
        await self.page.wait_for_function('typeof window.updateCore === "function"')
        models=[{'kind':'weather','title':'CLIMA','code':61,'temperature':19,'condition':'Chuva','city':'Porto Alegre'},
                {'kind':'gmail','title':'GMAIL','items':[{'title':'Assunto de teste','detail':'Remetente de teste'}]},
                {'kind':'whatsapp','title':'WHATSAPP','items':[{'title':'Conversa de teste','detail':'Prévia de teste'}]},
                {'kind':'tasks','title':'TAREFAS','count':3,'items':[{'title':'Tarefa de teste'}]},
                {'kind':'calendar','title':'AGENDA','items':[{'title':'Reunião de teste'}]},
                {'kind':'memory','title':'MEMÓRIA','items':[{'title':'Contexto de teste'}]},
                {'kind':'files','title':'ARQUIVOS','items':[{'title':'Arquivo de teste.pdf'}]},
                {'kind':'search','title':'BUSCA','items':[{'title':'Resultado de teste'}]},
                {'kind':'data','title':'DADOS','items':[{'title':'Registro de teste'}]},
                {'kind':'system','title':'SISTEMA','cpu_percent':40,'ram_percent':60}]
        for model in models:
            await self.page.set_viewport_size({'width':900,'height':600})
            await self.page.evaluate('value=>window.updateCore({...value,narrationDriven:false})',model)
            await self.page.evaluate("document.documentElement.style.background='#05090d'")
            await self.page.wait_for_timeout(2200)
            first=await self.page.locator('canvas').screenshot()
            await self.page.wait_for_timeout(450)
            second=await self.page.locator('canvas').screenshot()
            self.assertNotEqual(hashlib.sha256(first).digest(),hashlib.sha256(second).digest(),model['kind'])
            self.assertGreater(int(await self.page.locator('body').get_attribute('data-draw-calls')),0)
            self.assertLess(int(await self.page.locator('body').get_attribute('data-geometries')),65)
            self.assertTrue(await self.page.locator('body').get_attribute('data-animation-profile'))
            await self.page.screenshot(path=str(test_refresh_visual.BASE/f"validation/upgrade-{model['kind']}.png"))
            await self.page.set_viewport_size({'width':274,'height':125})
            await self.page.evaluate('value=>window.updateCore({...value,compact:true,narrationDriven:false})',model)
            await self.page.wait_for_timeout(1500)
            await self.page.screenshot(path=str(test_refresh_visual.BASE/f"validation/pin-{model['kind']}.png"))
            self.assertEqual(await self.page.locator('body').get_attribute('data-compact'),'true')
        self.assertEqual(self.errors,[])

    async def test_reduced_motion_is_still_readable_and_resources_stay_bounded(self):
        await self.page.goto(self.url+'/presentation.html')
        await self.page.wait_for_function('typeof window.updateCore === "function"')
        for i in range(12):
            kind='gmail' if i%2 else 'whatsapp'
            await self.page.evaluate('value=>window.updateCore(value)',{'kind':kind,'title':kind,'motion':'reduced','narrationDriven':False,'items':[{'title':'Texto acessível','detail':'Conteúdo preservado'}]})
            await self.page.wait_for_timeout(120)
        await self.page.wait_for_timeout(2000)
        first=await self.page.locator('canvas').screenshot()
        await self.page.wait_for_timeout(300)
        second=await self.page.locator('canvas').screenshot()
        self.assertEqual(hashlib.sha256(first).digest(),hashlib.sha256(second).digest())
        self.assertIn('Texto acessível',await self.page.locator('#details').inner_text())
        self.assertLess(int(await self.page.locator('body').get_attribute('data-geometries')),20)
        self.assertEqual(self.errors,[])

    async def test_spoken_subject_reveals_only_its_detail_and_end_preserves_rest(self):
        await self.page.goto(self.url+'/presentation.html')
        await self.page.wait_for_function('typeof window.updateCore === "function"')
        await self.page.evaluate("window.updateCore({kind:'gmail',title:'GMAIL',narrationDriven:true,items:[{title:'Reunião de revisão',detail:'Primeiro remetente'},{title:'Documento do projeto',detail:'Segundo remetente'}]})")
        await self.page.evaluate('window.advancePresentation({elapsed:4,cues:[]})')
        await self.page.wait_for_timeout(250)
        self.assertEqual(await self.page.locator('.record p').all_inner_texts(),['',''])
        await self.page.evaluate("window.advancePresentation({elapsed:5,cues:['Sobre o documento do projeto.']})")
        await self.page.evaluate('window.advancePresentation({elapsed:6,cues:[]})')
        await self.page.wait_for_timeout(100)
        self.assertEqual(await self.page.locator('.record p').nth(0).inner_text(),'')
        self.assertEqual(await self.page.locator('.record p').nth(1).inner_text(),'Segundo remetente')
        await self.page.evaluate('window.finishPresentation()')
        await self.page.wait_for_timeout(1400)
        self.assertEqual(await self.page.locator('.record p').nth(0).inner_text(),'')
        self.assertEqual(self.errors,[])

    async def test_news_does_not_jump_on_shared_word_or_future_transcript(self):
        await self.page.goto(self.url+'/presentation.html')
        await self.page.wait_for_function('typeof window.updateCore === "function"')
        await self.page.evaluate("window.updateCore({kind:'news',title:'NOTÍCIAS',narrationDriven:true,items:[{title:'Ciência brasileira descobre molécula'},{title:'Ciência brasileira lança satélite'}]})")
        await self.page.evaluate("window.advancePresentation({elapsed:.3,cues:['Primeira notícia e segunda notícia.']})")
        await self.page.evaluate("window.advancePresentation({elapsed:4,cues:['Ciência brasileira.']})")
        await self.page.evaluate("window.advancePresentation({elapsed:5,cues:['Isso aconteceu na segunda-feira.']})")
        self.assertEqual(await self.page.locator('.record.selected').get_attribute('aria-label'),'Selecionar Ciência brasileira descobre molécula')
        await self.page.evaluate("window.advancePresentation({elapsed:12,cues:['Segunda notícia: lança satélite.']})")
        self.assertIn('satélite',await self.page.locator('.record.selected').get_attribute('aria-label'))
        await self.page.evaluate('window.cancelPresentation()')
        await self.page.evaluate("window.advancePresentation({elapsed:15,cues:['Primeira notícia.']})")
        self.assertIn('satélite',await self.page.locator('.record.selected').get_attribute('aria-label'))
        self.assertEqual(self.errors,[])
