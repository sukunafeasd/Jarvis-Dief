import json
import unittest
import test_refresh_visual
from core.presentation_clock import PresentationClock


class ClockAuditTests(unittest.TestCase):
    def test_already_due_pcm_cues_do_not_wait_for_another_batch(self):
        clock=PresentationClock()
        clock.enqueue('Primeira notícia.',at=0,duration=.1)
        clock.enqueue('Segunda notícia.',at=.1,duration=.1)
        self.assertEqual(len(clock.advance(.2)['cues']),2)

    def test_sixth_and_seventh_are_split(self):
        clock=PresentationClock()
        clock.enqueue('Sexta notícia: ciência. Sétima notícia: pesquisa.',at=0,duration=2)
        self.assertEqual(len(clock.pending),2)


class PresentationAuditTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=test_refresh_visual.RefreshVisualTests.asyncSetUp
    asyncTearDown=test_refresh_visual.RefreshVisualTests.asyncTearDown

    async def ready(self):
        await self.page.goto(self.url+'/presentation.html')
        await self.page.wait_for_function('typeof window.updateCore === "function"')

    async def test_image_cannot_appear_before_played_speech(self):
        await self.ready()
        image=json.loads((test_refresh_visual.BASE/'core/spatial/assets/moon-sss.json').read_text())['image']
        model={'kind':'news','title':'NOTÍCIAS','presentationId':'photo-gate','narrationDriven':True,'items':[{'title':'Imagem de validação','image':image}]}
        await self.page.evaluate('v=>window.updateCore(v)',model)
        await self.page.wait_for_timeout(800)
        self.assertEqual(await self.page.locator('.news-banner').evaluate('el=>getComputedStyle(el).opacity'),'0')
        await self.page.evaluate('window.advancePresentation({elapsed:1,cues:[],presentationId:"photo-gate"})')
        await self.page.wait_for_timeout(650)
        self.assertEqual(await self.page.locator('.news-banner').evaluate('el=>getComputedStyle(el).opacity'),'1')

    async def test_stale_cues_and_other_domain_ordinals_do_not_select_news(self):
        await self.ready()
        model={'kind':'news','presentationId':'current','narrationDriven':True,'items':[{'title':'Pesquisa lunar'},{'title':'Exploração orbital'}]}
        await self.page.evaluate('v=>window.updateCore(v)',model)
        await self.page.evaluate('window.advancePresentation({elapsed:1,cues:["Segunda notícia."],presentationId:"old"})')
        self.assertEqual(await self.page.locator('.selected').get_attribute('data-index'),'0')
        await self.page.evaluate('window.advancePresentation({elapsed:1,cues:["Segunda tarefa."],presentationId:"current"})')
        self.assertEqual(await self.page.locator('.selected').get_attribute('data-index'),'0')
        await self.page.evaluate('window.advancePresentation({elapsed:2,cues:["Segunda notícia."],presentationId:"current"})')
        self.assertEqual(await self.page.locator('.selected').get_attribute('data-index'),'1')
        self.assertTrue((await self.page.evaluate('location.hash')).endswith('-current'))

    async def test_long_list_selected_item_has_real_global_index(self):
        await self.ready()
        items=[{'id':str(i),'title':f'Mensagem {i+1}','detail':'Conteúdo de teste'} for i in range(35)]
        await self.page.evaluate('v=>window.updateCore(v)',{'kind':'gmail','presentationId':'long-list','focus':24,'items':items,'narrationDriven':False})
        self.assertEqual(await self.page.locator('.selected').get_attribute('data-index'),'24')
        self.assertEqual(await self.page.locator('.selected h2').get_attribute('aria-label'),'Mensagem 25')
        await self.page.evaluate('window.updateCore({kind:"gmail",presentationId:"long-list",focus:0,narrationDriven:true,items:Array.from({length:35},(_,i)=>({title:"Mensagem "+(i+1)}))})')
        await self.page.evaluate('window.narratePresentation("Mensagem 25 tem documentos")')
        # Explicit selection remains supported for every item, not just the first twenty.
        await self.page.evaluate('window.updateCore({...{kind:"gmail",presentationId:"long-list"},focus:34,items:Array.from({length:35},(_,i)=>({title:"Mensagem "+(i+1)}))})')
        self.assertEqual(await self.page.locator('.selected').get_attribute('data-index'),'34')

    async def test_live_metrics_do_not_blank_existing_text(self):
        await self.ready()
        model={'kind':'system','presentationId':'telemetry','narrationDriven':True,'cpu_percent':10,'ram_percent':40}
        await self.page.evaluate('v=>window.updateCore(v)',model)
        await self.page.evaluate('window.advancePresentation({elapsed:5,cues:[]})')
        await self.page.wait_for_timeout(100)
        before=await self.page.locator('#summary h1').inner_text()
        self.assertTrue(before)
        await self.page.evaluate('v=>window.updateCore(v)',{**model,'cpu_percent':72})
        self.assertEqual(await self.page.locator('#summary h1').inner_text(),before)
        self.assertEqual(await self.page.locator('.metric strong').first.inner_text(),'72%')

    async def test_partial_data_and_failed_source_are_readable(self):
        await self.ready()
        await self.page.evaluate('window.updateCore({kind:"weather",items:null,forecast:[null,{date:null,max:18}]})')
        await self.page.evaluate('window.updateCore({kind:"tasks",items:[null,{title:"Registro real"}]})')
        self.assertEqual(await self.page.locator('.fact').get_attribute('aria-label'),'--')
        await self.page.evaluate('window.updateCore({kind:"status",items:[{title:"Gmail",status:"error",detail:"Fonte indisponível"}]})')
        self.assertEqual(await self.page.locator('.check-row').get_attribute('data-state'),'error')
        self.assertEqual(self.errors,[])

    async def test_interruption_resume_and_completion_keep_correct_article(self):
        await self.ready()
        await self.page.evaluate("document.documentElement.style.background=\"#03070a url('./assets/deep-space.png') center/cover\"")
        output=test_refresh_visual.BASE/'validation/interface-audit'
        output.mkdir(parents=True,exist_ok=True)
        image=json.loads((test_refresh_visual.BASE/'core/spatial/assets/moon-sss.json').read_text())['image']
        model={'kind':'news','title':'NOTICIAS DE TESTE','presentationId':'conversation',
               'narrationDriven':True,'items':[{'title':'Pesquisa lunar','image':image}, {'title':'Exploracao espacial','image':image}]}
        await self.page.evaluate('v=>window.updateCore(v)',model)
        await self.page.evaluate('window.advancePresentation({elapsed:2,cues:["Primeira noticia."],presentationId:"conversation"})')
        await self.page.wait_for_timeout(650)
        await self.page.screenshot(path=str(output/'news-speaking.png'))
        await self.page.evaluate('window.cancelPresentation();window.advancePresentation({elapsed:5,cues:["Segunda noticia."],presentationId:"conversation"})')
        self.assertEqual(await self.page.locator('.selected').get_attribute('data-index'),'0')
        await self.page.screenshot(path=str(output/'news-paused.png'))
        await self.page.evaluate('window.resumePresentation();window.advancePresentation({elapsed:2,cues:["Segunda noticia."],presentationId:"conversation"})')
        self.assertEqual(await self.page.locator('.selected').get_attribute('data-index'),'1')
        await self.page.evaluate('window.finishPresentation();window.advancePresentation({elapsed:10,cues:["Primeira noticia."],presentationId:"conversation"})')
        self.assertEqual(await self.page.locator('.selected').get_attribute('data-index'),'1')
        await self.page.wait_for_timeout(2200)
        await self.page.screenshot(path=str(output/'news-finished.png'))
        self.assertEqual(self.errors,[])
