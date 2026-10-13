import unittest
import hashlib
from pathlib import Path
import test_refresh_visual


class FinishVisualTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=test_refresh_visual.RefreshVisualTests.asyncSetUp
    asyncTearDown=test_refresh_visual.RefreshVisualTests.asyncTearDown

    async def test_communication_framing_text_and_keyboard_focus(self):
        await self.page.goto(self.url+'/presentation.html')
        await self.page.wait_for_function('typeof window.updateCore === "function"')
        for kind in ('gmail','whatsapp'):
            for width,height in ((900,600),(390,650)):
                await self.page.set_viewport_size({'width':width,'height':height})
                await self.page.evaluate('value=>window.updateCore(value)',{
                    'kind':kind,'title':'DIEF JARVIS · '+kind.upper(),'motion':'reduced','narrationDriven':False,
                    'items':[{'title':'Uma conversa com um assunto suficientemente longo para conferir o enquadramento',
                              'detail':'Conteúdo de teste, sem informações pessoais, para conferir a leitura.'}]})
                await self.page.wait_for_timeout(1700)
                bounds=await self.page.locator('.record h2').bounding_box()
                self.assertLessEqual(bounds['x']+bounds['width'],width)
                self.assertGreaterEqual(bounds['x'],0)
                self.assertLess(int(await self.page.locator('body').get_attribute('data-geometries')),65)
                self.assertEqual(await self.page.locator('button,[role=button]').count(),0)
                self.assertEqual(await self.page.locator('.record').get_attribute('role'),'article')
                await self.page.screenshot(path=str(test_refresh_visual.BASE/f'validation/finish-{kind}-{width}.png'))
        self.assertEqual(self.errors,[])

    async def test_domain_motion_materials_and_reduced_motion(self):
        await self.page.goto(self.url+'/presentation.html')
        await self.page.wait_for_function('typeof window.updateCore === "function"')
        await self.page.evaluate("document.documentElement.style.background='#070b12'")
        models=[
            {'kind':'weather','code':95,'city':'Cidade de teste','temperature':19,'rain':80,'wind':12},
            {'kind':'gmail','items':[{'title':'Mensagem de teste','detail':'Sem dados pessoais'}]},
            {'kind':'whatsapp','items':[{'title':'Conversa de teste','detail':'Conteudo de teste'}]},
            {'kind':'tasks','count':3,'items':[{'title':'Tarefa '+str(i)} for i in range(3)]},
            {'kind':'calendar','items':[{'title':'Compromisso de teste'}]},
            {'kind':'memory','items':[{'title':'Contexto de teste'}]},
            {'kind':'files','items':[{'title':'Documento de teste'}]},
        ]
        from PIL import Image
        from io import BytesIO
        for model in models:
            await self.page.evaluate('value=>window.updateCore(value)',dict(model,motion='full'))
            await self.page.wait_for_timeout(2700)
            first=await self.page.locator('canvas').screenshot()
            await self.page.wait_for_timeout(500)
            second=await self.page.locator('canvas').screenshot()
            self.assertNotEqual(hashlib.sha256(first).digest(),hashlib.sha256(second).digest(),model['kind'])
            pixels=Image.open(BytesIO(second)).convert('RGBA')
            self.assertGreater(sum(pixel[3]>0 for pixel in pixels.getdata()),100,model['kind'])
            self.assertLess(int(await self.page.locator('body').get_attribute('data-draw-calls')),65)
            await self.page.screenshot(path=str(test_refresh_visual.BASE/f"validation/finish-motion-{model['kind']}.png"))
            await self.page.evaluate('value=>window.updateCore(value)',dict(model,motion='reduced'))
            await self.page.wait_for_timeout(200)
            still=await self.page.locator('canvas').screenshot()
            await self.page.wait_for_timeout(350)
            if model['kind']!='calendar':
                self.assertEqual(still,await self.page.locator('canvas').screenshot(),model['kind'])
        self.assertEqual(self.errors,[])
