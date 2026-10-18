import ast
import copy
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from core.briefing_presentation import chapters
import test_refresh_visual


class LivePresentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Exercise the actual method without starting the assistant or account services.
        source=Path(__file__).resolve().parents[1]/'ui.py'
        tree=ast.parse(source.read_text(encoding='utf-8'))
        window=next(node for node in tree.body if isinstance(node,ast.ClassDef) and node.name=='MainWindow')
        method=next(node for node in window.body if isinstance(node,ast.FunctionDef) and node.name=='_show_manifestation')
        namespace={'json':__import__('json'),'uuid':__import__('uuid')}
        exec(compile(ast.Module(body=[method],type_ignores=[]),str(source),'exec'),namespace)
        cls.show=staticmethod(namespace['_show_manifestation'])

    def window(self):
        return SimpleNamespace(_refresh_lock=None,_presentation=None,_pending_image_pin=False,
            _cancel_neural_memory=Mock(),
            _terminal=Mock(),_execution=Mock(),_environment=SimpleNamespace(operation='idle'),
            hud=Mock(),_ui_sounds=Mock(),_pin_previews={'tasks':{'data':{'kind':'tasks','refresh':{'provider':'organizer','parameters':{'domain':'tasks','action':'list'}}}}},_update_pin=Mock(),
            _resting=False,_presentation_clock=Mock(),_show_content=Mock(),_render_presentation=Mock(),
            _presentation_history=[])

    def test_live_model_is_full_size_without_changing_pin_payload_or_input(self):
        window=self.window()
        data={'kind':'tasks','title':'TAREFAS','compact':True,'framed':True,
              'items':[{'id':1,'title':'Teste'}],'count':1,'custom':'preserved',
              'refresh':{'provider':'organizer','parameters':{'domain':'tasks','action':'list'}}}
        original=copy.deepcopy(data)
        self.show(window,data)
        live=window._show_content.call_args.args[2]
        self.assertFalse(live['compact']);self.assertFalse(live['framed'])
        self.assertEqual(live['custom'],'preserved')
        pin=window._update_pin.call_args.args[1]
        self.assertTrue(pin['compact']);self.assertTrue(pin['framed'])
        self.assertEqual(data,original)

    def test_same_status_transaction_retains_presentation_clock_and_identity(self):
        window=self.window()
        window._daily_refresh_view=Mock()
        window._pinned=False
        self.show(window,{'kind':'status','id':'refresh','refreshTransaction':True,
                          'compact':True,'framed':True,'completed':2,'total':3})
        window._presentation_clock.replace_scene.assert_not_called()
        window._render_presentation.assert_not_called()
        window._daily_refresh_view.update_model.assert_called_once()

    def test_resting_history_and_all_briefing_chapters_are_full_size(self):
        window=self.window();window._resting=True
        self.show(window,{'kind':'weather','compact':True,'framed':True,'city':'Teste'})
        live=window._presentation_history[0]['model']
        self.assertFalse(live['compact']);self.assertFalse(live['framed'])
        package={'data':{kind:{'compact':True,'framed':True,'items':[{'title':'Teste'}]}
                         for kind in ('weather','calendar','tasks','gmail')}}
        package['data']['news']={'model':{'kind':'news','compact':True,'framed':True,
                                         'items':[{'title':'Primeira'},{'title':'Segunda'}]}}
        original=copy.deepcopy(package)
        sequence=chapters(package)
        self.assertEqual(len(sequence),6)
        for chapter in sequence:
            self.assertFalse(chapter['model']['compact']);self.assertFalse(chapter['model']['framed'])
            self.assertTrue(chapter['model']['narrationDriven'])
        self.assertEqual(package,original)


class RefreshDOMTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=test_refresh_visual.RefreshVisualTests.asyncSetUp
    asyncTearDown=test_refresh_visual.RefreshVisualTests.asyncTearDown

    async def test_same_transaction_updates_progress_without_replacing_nodes_or_animation(self):
        await self.page.goto(self.url+'/presentation.html')
        await self.page.wait_for_function('typeof window.updateCore === "function"')
        model={'kind':'status','id':'refresh','presentationId':'scene','refreshTransaction':True,
               'title':'ATUALIZANDO','total':2,'completed':0,'narrationDriven':False,
               'items':[{'id':'news','title':'Notícias','detail':'Consulta','status':'working'},
                        {'id':'tasks','title':'Tarefas','detail':'Aguardando','status':'working'}]}
        await self.page.evaluate('value=>window.updateCore(value)',model)
        await self.page.evaluate('''() => {
            window.keptSummary=document.querySelector('#summary h1');
            window.keptProgress=document.querySelector('.refresh-progress');
            window.keptRow=document.querySelector('.check-row');
            window.keptSurface=document.querySelector('main').animate([{opacity:.9},{opacity:1}],{duration:100000});
            window.keptAnimation=keptRow.animate([{opacity:.5},{opacity:1}],{duration:100000});
            window.beforeStatus=window.presentationStatus();
            window.surfaceStarts=0;
            const main=document.querySelector('main'),animate=main.animate.bind(main);
            main.animate=(...args)=>{window.surfaceStarts++;return animate(...args);};
        }''')
        model['completed']=1;model['count']=2
        model['items'][0].update(status='ok',detail='Concluída <script>')
        model['items'].append({'id':'extra','title':'Extra','detail':'Pendente','status':'working'})
        await self.page.evaluate('value=>window.updateCore(value)',model)
        result=await self.page.evaluate('''() => ({
            summary:keptSummary===document.querySelector('#summary h1'),
            progress:keptProgress===document.querySelector('.refresh-progress'),
            row:keptRow===document.querySelector('.check-row'),
            animation:keptAnimation.playState,
            surface:keptSurface.playState,
            starts:surfaceStarts,
            status:JSON.stringify(beforeStatus)===JSON.stringify(window.presentationStatus())
        })''')
        self.assertTrue(result['summary']);self.assertTrue(result['progress']);self.assertTrue(result['row'])
        self.assertEqual(result['animation'],'running');self.assertNotEqual(result['surface'],'idle')
        self.assertEqual(result['starts'],0);self.assertTrue(result['status'])
        self.assertEqual(await self.page.locator('.refresh-progress').get_attribute('aria-valuenow'),'50')
        self.assertEqual(await self.page.locator('.check-row').count(),3)
        self.assertEqual(await self.page.locator('.check-row p').first.inner_text(),'Concluída <script>')
        self.assertEqual(await self.page.locator('#details script').count(),0)
        model['items']=model['items'][1:]
        model['completed']=2
        await self.page.evaluate('value=>window.updateCore(value)',model)
        self.assertEqual(await self.page.locator('.check-row').count(),2)
        self.assertEqual(await self.page.locator('.refresh-progress').get_attribute('aria-valuenow'),'100')
        self.assertEqual(await self.page.evaluate('surfaceStarts'),0)
        model['id']='next';model['presentationId']='next-scene'
        await self.page.evaluate('value=>window.updateCore(value)',model)
        self.assertEqual(await self.page.evaluate('surfaceStarts'),1)
        self.assertFalse(await self.page.evaluate('keptRow.isConnected'))
        await self.page.evaluate("window.dismissPresentation()")
        await self.page.evaluate('value=>window.updateCore(value)',model)
        self.assertEqual(await self.page.locator('body').get_attribute('data-dismissing'),'false')
        self.assertGreater(await self.page.evaluate('surfaceStarts'),1)
        from io import BytesIO
        from PIL import Image, ImageStat
        for width,height in ((1200,900),(360,640)):
            await self.page.set_viewport_size({'width':width,'height':height})
            image=Image.open(BytesIO(await self.page.screenshot())).convert('RGB')
            self.assertGreater(max(ImageStat.Stat(image).stddev),5)
            bounds=await self.page.locator('.refresh-progress').bounding_box()
            self.assertGreater(bounds['width'],0)
            self.assertGreaterEqual(bounds['x'],0)
            self.assertLessEqual(bounds['x']+bounds['width'],width+1)
        self.assertEqual(self.errors,[])

    async def test_compact_framed_pin_rendering_is_preserved(self):
        await self.page.goto(self.url+'/presentation.html')
        await self.page.wait_for_function('typeof window.updateCore === "function"')
        await self.page.evaluate("window.updateCore({kind:'tasks',compact:true,framed:true,motion:'reduced',items:[{title:'Pin preservado'}]})")
        self.assertEqual(await self.page.locator('body').get_attribute('data-compact'),'true')
        self.assertEqual(await self.page.locator('body').get_attribute('data-framed'),'true')
        self.assertEqual(await self.page.locator('.record').count(),1)
        self.assertEqual(self.errors,[])


if __name__=='__main__':unittest.main()
