import base64
import json
import unittest
from unittest.mock import Mock, patch
from core.gmail_message import message_view
from core import gmail_connection as gmail
from core import windows_accessibility as desktop
import test_connections


def part(mime,text):
    return {'mimeType':mime,'body':{'data':base64.urlsafe_b64encode(text.encode()).decode().rstrip('=')}}


class GmailContentTests(unittest.TestCase):
    def test_plain_body_preferred_over_html_and_attachments_not_downloaded(self):
        service=Mock()
        message={'id':'abc','payload':{'mimeType':'multipart/mixed','parts':[
            {'mimeType':'multipart/alternative','parts':[part('text/plain','Mensagem completa'),part('text/html','<p>Duplicada</p>')]},
            {'mimeType':'application/pdf','filename':'arquivo.pdf','body':{'attachmentId':'private','size':20}}]}}
        view=message_view(message,service)
        self.assertEqual(view['body'],'Mensagem completa')
        self.assertEqual(view['attachments'][0]['filename'],'arquivo.pdf')
        service.users.assert_not_called()

    def test_html_excludes_script_style_and_remote_images(self):
        result=message_view({'id':'abc','payload':part('text/html','<style>invisível</style><script>não executar()</script><p>Olá &amp; obrigado</p><img src="https://example.org/tracker"><p>Texto final</p>')})
        self.assertIn('Olá & obrigado',result['body'])
        self.assertNotIn('executar',result['body'])
        self.assertNotIn('tracker',result['body'])
        self.assertNotIn('invisível',result['body'])

    def test_body_limit_is_explicit(self):
        result=message_view({'id':'abc','payload':part('text/plain','x'*1400)},max_chars=1000)
        self.assertEqual(len(result['body']),1000)
        self.assertTrue(result['body_truncated'])

    def test_read_uses_full_message_and_rejects_wrong_id(self):
        with patch.object(gmail,'_service') as service:
            request=service.return_value.users.return_value.messages.return_value.get
            request.return_value.execute.return_value={'id':'abc','threadId':'thread1','payload':part('text/plain','Corpo real de teste')}
            result=gmail.read_message('abc')
            self.assertEqual(result['message']['body'],'Corpo real de teste')
            request.assert_called_with(userId='me',id='abc',format='full')
            request.return_value.execute.return_value['id']='other'
            self.assertFalse(gmail.read_message('abc')['ok'])

    def test_plugin_presents_body_and_preserves_readonly_scopes(self):
        from plugins.gmail_control import run
        player=Mock()
        with patch.object(gmail,'read_message',return_value={'ok':True,'message':{'id':'abc','subject':'Assunto','from':'Remetente','body':'Conteúdo completo'}}):
            result=json.loads(run({'action':'read','message_id':'abc'},player=player))
        self.assertTrue(result['ok'])
        self.assertIn('Conteúdo completo',player.show_manifestation.call_args.args[0]['items'][0]['detail'])
        self.assertEqual(gmail.SCOPES,['https://www.googleapis.com/auth/gmail.readonly'])


class ObservedControlTests(unittest.TestCase):
    def setUp(self):
        self.control=Mock()
        self.control.element_info.name='Pesquisar'
        self.control.element_info.automation_id='search'
        self.control.element_info.control_type='Edit'
        self.control.element_info.runtime_id=[7,11]
        self.control.element_info.element.CurrentIsPassword=False
        self.control.is_visible.return_value=True
        self.control.is_enabled.return_value=True
        self.control.has_keyboard_focus.return_value=True
        self.window=Mock();self.window.handle=123
        self.window.process_id.return_value=17
        self.window.is_visible.return_value=True
        self.window.descendants.return_value=[self.control]
        self.stub=patch.object(desktop,'desktop')
        self.root=self.stub.start().return_value.__enter__.return_value
        self.root.window.return_value.wrapper_object.return_value=self.window
        self.addCleanup(self.stub.stop)

    def token(self):
        return desktop.operate({'action':'inspect','handle':123})['controls'][0]['control_id']

    def test_runtime_id_targets_unnamed_controls_and_rejects_stale_tree(self):
        self.control.element_info.name=''
        self.control.element_info.automation_id=''
        token=self.token()
        self.control.iface_value.CurrentValue='Texto'
        result=desktop.operate({'action':'fill','handle':123,'control_id':token,'text':'Texto'})
        self.assertTrue(result['ok'])
        self.control.element_info.runtime_id=[7,12]
        self.assertFalse(desktop.operate({'action':'fill','handle':123,'control_id':token,'text':'Outro'})['ok'])
        self.control.iface_value.SetValue.assert_called_once_with('Texto')

    def test_token_cannot_cross_window_or_process(self):
        token=self.token()
        self.window.process_id.return_value=18
        self.assertFalse(desktop.operate({'action':'fill','handle':123,'control_id':token,'text':'Texto'})['ok'])
        self.control.iface_value.SetValue.assert_not_called()

    def test_keyboard_mode_is_opt_in_and_escapes_shortcuts(self):
        token=self.token()
        self.assertFalse(desktop.operate({'action':'fill','handle':123,'control_id':token,'input_mode':'keyboard','text':'A+B{C}'})['ok'])
        self.control.window_text.return_value='A+B{C}'
        with patch.object(desktop,'focus_verified'):
            result=desktop.operate({'action':'fill','handle':123,'control_id':token,'input_mode':'keyboard','allow_visible':True,'text':'A+B{C}'})
        self.assertTrue(result['ok'])
        self.assertEqual(self.control.type_keys.call_args.args[0],'A{+}B{{}C{}}')
        self.control.iface_value.SetValue.assert_not_called()

    def test_uncertain_invocation_never_repeats_with_click(self):
        self.control.element_info.control_type='Button'
        token=self.token()
        self.control.invoke.side_effect=RuntimeError('provider timeout')
        result=desktop.operate({'action':'invoke','handle':123,'control_id':token,'allow_visible':True})
        self.assertFalse(result['ok'])
        self.assertTrue(result['uncertain'])
        self.control.click_input.assert_not_called()


class WhatsAppModernDOMTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=test_connections.WhatsAppDOMTests.asyncSetUp
    asyncTearDown=test_connections.WhatsAppDOMTests.asyncTearDown

    async def test_contact_row_preview_with_same_name_is_not_a_duplicate_contact(self):
        await self.page.locator('#pane-side').evaluate("el=>{const name=el.firstElementChild;const row=document.createElement('div');row.setAttribute('role','row');row.appendChild(name);const preview=document.createElement('span');preview.title='Contato de teste';preview.textContent='Contato de teste';row.appendChild(preview);el.appendChild(row);}")
        self.assertTrue((await test_connections.send_on_page(self.page,'Contato de teste','Texto de teste'))['ok'])

    async def test_header_without_title_attribute_can_be_verified(self):
        await self.page.locator('#main header').evaluate("el=>el.innerHTML='<span dir=auto>--</span>'")
        await self.page.locator('#pane-side span').evaluate("el=>el.onclick=()=>document.querySelector('#main header span').textContent='Contato de teste'")
        self.assertTrue((await test_connections.send_on_page(self.page,'Contato de teste','Texto de teste'))['ok'])

    async def test_readonly_chat_without_composer_is_readable(self):
        from core.whatsapp_web import read_chat_on_page
        await self.page.locator('footer').evaluate('el=>el.remove()')
        await self.page.locator('#pane-side span').evaluate("el=>el.onclick=()=>{document.querySelector('#main header span').title='Contato de teste';const msg=document.createElement('div');msg.dataset.id='false_readonly';msg.innerHTML='<span class=selectable-text>Mensagem <img alt="+'"😊"'+"></span>';document.querySelector('#main').appendChild(msg);}")
        result=await read_chat_on_page(self.page,'Contato de teste')
        self.assertTrue(result['ok'])
        self.assertIn('😊',result['messages'][0]['text'])
