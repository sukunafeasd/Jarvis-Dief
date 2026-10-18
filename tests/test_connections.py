import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from core import gmail_connection as gmail
from core.whatsapp_web import WhatsAppWeb, find_chat_search, send_on_page


class ConnectionTests(unittest.TestCase):
    def test_uncertain_send_reports_stage_and_never_retries(self):
        from actions.send_message import _send_whatsapp
        with patch('core.whatsapp_web.transport') as transport, patch('memory.config_manager.get_plugin_enabled',return_value=True):
            transport.call.return_value={'ok':False,'stage':'confirmation','uncertain':True,'error':'Confira a conversa.'}
            result=_send_whatsapp('Contato de teste','Texto de teste')
            self.assertIn('confirmação na conversa',result)
            self.assertIn('Não repita automaticamente',result)
            transport.call.assert_called_once_with('send','Contato de teste','Texto de teste')

    def test_whatsapp_never_falls_back_to_windows_search(self):
        from actions.send_message import _send_whatsapp
        with tempfile.TemporaryDirectory() as folder, patch("core.whatsapp_web.PROFILE", Path(folder)/"unlinked"), patch("core.whatsapp_web.transport", WhatsAppWeb()), patch("actions.send_message._desktop_send") as blind, patch("memory.config_manager.get_plugin_enabled",return_value=True):
            result=_send_whatsapp("Contato de teste","Mensagem de teste")
            self.assertIn("Não confirmei",result)
            blind.assert_not_called()

    def test_gmail_requires_authorization_and_monitor_is_not_claimed(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(gmail,"TOKEN",Path(folder)/"token.bin"),patch.object(gmail,"CREDENTIALS",Path(folder)/"credentials.json"),patch("memory.config_manager.get_plugin_setting",return_value=False):
            self.assertFalse(gmail.status()["connected"])
            self.assertFalse(gmail.set_monitor(True)["ok"])
            self.assertFalse(gmail.connect()[0])

    def test_gmail_import_is_desktop_oauth_and_uses_google_endpoints(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(gmail,"CREDENTIALS",Path(folder)/"credentials.json"):
            source=Path(folder)/"input.json"
            source.write_text(json.dumps({"installed":{"client_id":"test.apps.googleusercontent.com","client_secret":"dummy","auth_uri":"https://evil.example"}}))
            gmail.import_credentials(source)
            saved=json.loads(gmail.CREDENTIALS.read_text())
            self.assertEqual(saved["installed"]["auth_uri"],"https://accounts.google.com/o/oauth2/auth")
            source.write_text('{"web":{"client_id":"wrong"}}')
            with self.assertRaises(ValueError):gmail.import_credentials(source)

    def test_gmail_token_is_encrypted_for_windows_user(self):
        from google.oauth2.credentials import Credentials
        with tempfile.TemporaryDirectory() as folder,patch.object(gmail,"TOKEN",Path(folder)/"token.bin"):
            credential=Credentials(token="dummy-private-token",refresh_token="dummy-refresh",token_uri="https://oauth2.googleapis.com/token",client_id="test.apps.googleusercontent.com",client_secret="dummy",scopes=gmail.SCOPES)
            gmail._save(credential)
            self.assertNotIn(b"dummy-private-token",gmail.TOKEN.read_bytes())
            self.assertEqual(gmail._load().token,"dummy-private-token")

    def test_gmail_poll_baselines_and_only_announces_new_ids(self):
        with patch.object(gmail,"_monitoring",return_value=True),patch.object(gmail,"TOKEN") as token,patch.object(gmail,"_service") as service,patch.object(gmail,"_seen",None):
            token.exists.return_value=True
            request=service.return_value.users.return_value.messages.return_value.list.return_value
            request.execute.side_effect=[{"messages":[{"id":"old"}]},{"messages":[{"id":"old"},{"id":"new"}]},{"messages":[{"id":"old"},{"id":"new"}]}]
            self.assertEqual(gmail.poll(),0);self.assertEqual(gmail.poll(),1);self.assertEqual(gmail.poll(),0)

    def test_plugins_load_and_expose_actual_connections(self):
        from core.plugin_loader import discover_plugins
        base=Path(__file__).resolve().parents[1]
        registry=discover_plugins(base/"plugins",set(),logger=lambda _:None)
        self.assertEqual({p["name"] for p in registry.list_for_ui() if p["valid"]},
            {"desktop_accessibility","gmail_control","whatsapp_web","structured_browser","google_calendar",
             "google_drive","spotify_control","document_reader","personal_routines"}
              | {"local_resources","file_library","task_execution","office_resources","resource_backups",
                 "gmail_compose","home_automation","resource_diagnostics","desktop_resources","outlook_service",
                 "mcp_bridge","resource_monitor","resource_updates","calendar_planning","notion_service"}
              | {"playwright_mcp","windows_mcp","markitdown","planet_knowledge","qdrant_memory",
                 "github_mcp","context7","deep_research","local_transcription","fish_audio","skill_library"})

    def test_desktop_ambiguous_controls_never_invoke(self):
        from core.windows_accessibility import operate
        controls=[]
        for _ in range(2):
            item=Mock();item.element_info.name="Enviar";item.element_info.automation_id=""
            item.element_info.control_type="Button";item.element_info.element.CurrentIsPassword=False
            item.is_visible.return_value=True;item.is_enabled.return_value=True;controls.append(item)
        with patch("core.windows_accessibility.desktop") as desktop:
            window=desktop.return_value.__enter__.return_value.window.return_value.wrapper_object.return_value
            window.is_visible.return_value=True;window.descendants.return_value=controls
            result=operate({"action":"invoke","handle":123,"name":"Enviar","type":"Button"})
            self.assertFalse(result["ok"])
            for control in controls:control.invoke.assert_not_called()

    def test_password_controls_are_not_exposed(self):
        from core.windows_accessibility import visible_controls
        password=Mock();password.is_visible.return_value=True
        password.element_info.element.CurrentIsPassword=True
        window=Mock();window.descendants.return_value=[password]
        self.assertEqual(list(visible_controls(window)),[])

    def test_unmanaged_browser_tabs_do_not_open_another_session(self):
        from actions.browser_control import browser_control
        with patch("actions.browser_control._registry") as registry:
            registry.has.return_value=False
            result=browser_control({"action":"list_tabs"})
            self.assertIn("Nenhuma sessão",result)
            registry.get.assert_not_called()


FIXTURE = """<div id="side"><div role="textbox" contenteditable="true"></div></div>
<div id="pane-side"><span title="Contato de teste" onclick="document.querySelector('#main header span').setAttribute('title',window.wrong?'Outro contato':'Contato de teste')">Contato de teste</span></div>
<div id="main"><header><span title="--">Cabeçalho</span></header>
<footer><div contenteditable="true" role="textbox"></div></footer></div>
<script>document.querySelector('footer div').addEventListener('keydown',e=>{
 if(e.key==='Enter'){e.preventDefault();const row=document.createElement('div');row.dataset.id='true_test';
 const text=document.createElement('span');text.className='selectable-text';text.textContent=e.target.innerText;
 row.appendChild(text);document.querySelector('#main').appendChild(row);e.target.textContent='';}});</script>"""


class WhatsAppDOMTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        from playwright.async_api import async_playwright
        self.pw=await async_playwright().start()
        edge=Path("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe")
        self.browser=await self.pw.chromium.launch(headless=True,**({"executable_path":str(edge)} if edge.exists() else {}))
        self.context=await self.browser.new_context()
        self.page=await self.context.new_page()
        await self.page.set_content(FIXTURE)

    async def asyncTearDown(self):
        await self.browser.close();await self.pw.stop()

    async def test_send_confirms_new_outgoing_message_not_delivery(self):
        result=await send_on_page(self.page,"Contato de teste","Olá, teste com acentos!")
        self.assertTrue(result["ok"])
        self.assertIn("não confirmadas",result["status"])

    async def test_multiline_message_is_verified_without_losing_lines(self):
        result=await send_on_page(self.page,'Contato de teste','Primeira linha\nSegunda linha')
        self.assertTrue(result['ok'],result)

    async def test_search_contenteditable_without_textbox_role(self):
        await self.page.locator('#side [contenteditable]').evaluate("el=>el.removeAttribute('role')")
        result = await send_on_page(self.page, 'Contato de teste', 'Teste sem role')
        self.assertTrue(result['ok'])

    async def test_delayed_header_and_composer_without_role(self):
        await self.page.locator('#pane-side span').evaluate("el=>el.onclick=()=>setTimeout(()=>document.querySelector('#main header span').setAttribute('title','Contato de teste'),300)")
        await self.page.locator('footer div').evaluate("el=>el.removeAttribute('role')")
        self.assertTrue((await send_on_page(self.page, 'contato de teste', 'Texto correto'))['ok'])

    async def test_search_waits_for_contact_results(self):
        await self.page.locator('#pane-side').evaluate("el=>{el.style.minHeight='100px';const row=el.firstElementChild;row.remove();setTimeout(()=>el.appendChild(row),450)}")
        result=await send_on_page(self.page, 'Contato de teste', 'Resultado atrasado')
        self.assertTrue(result['ok'],result)

    async def test_send_button_works_when_enter_is_disabled(self):
        await self.page.locator('footer').evaluate("""el=>{
            el.innerHTML='<div contenteditable=true></div><button aria-label=Enviar>Enviar</button>';
            el.querySelector('button').onclick=()=>{
                const row=document.createElement('div');row.dataset.id='true_button';
                const text=document.createElement('span');text.className='selectable-text';
                text.textContent=el.querySelector('div').innerText;row.appendChild(text);
                document.querySelector('#main').appendChild(row);el.querySelector('div').textContent='';
            };
        }""")
        self.assertTrue((await send_on_page(self.page, 'Contato de teste', 'Botao confirmado'))['ok'])

    async def test_emoji_image_is_included_in_confirmation(self):
        await self.page.locator('footer').evaluate("""el=>{
            el.innerHTML='<div contenteditable=true></div><button aria-label=Enviar>Enviar</button>';
            el.querySelector('button').onclick=()=>{
                const row=document.createElement('div');row.dataset.id='true_emoji';
                row.innerHTML='<span class=selectable-text>Oi <img alt="😊"></span>';
                document.querySelector('#main').appendChild(row);el.querySelector('div').textContent='';
            };
        }""")
        self.assertTrue((await send_on_page(self.page, 'Contato de teste', 'Oi 😊'))['ok'])

    async def test_ambiguous_send_buttons_preserve_draft(self):
        await self.page.locator('footer').evaluate("el=>el.insertAdjacentHTML('beforeend','<button aria-label=Enviar>A</button><button aria-label=Enviar>B</button>')")
        result=await send_on_page(self.page, 'Contato de teste', 'Nao enviar')
        self.assertFalse(result['ok'])
        self.assertFalse(result['uncertain'])
        self.assertEqual(result['stage'],'send_control')
        self.assertEqual(await self.page.locator('footer div').inner_text(),'Nao enviar')
        self.assertEqual(await self.page.locator('#main [data-id]').count(),0)

    async def test_changed_editor_text_never_dispatches(self):
        await self.page.locator('footer div').evaluate("el=>el.addEventListener('input',()=>el.textContent='Texto alterado')")
        result=await send_on_page(self.page, 'Contato de teste', 'Texto solicitado')
        self.assertFalse(result['ok'])
        self.assertFalse(result['uncertain'])
        self.assertEqual(result['stage'],'message_verification')
        self.assertEqual(await self.page.locator('#main [data-id]').count(),0)

    async def test_chat_change_after_dispatch_is_uncertain_without_retry(self):
        await self.page.locator('footer').evaluate("""el=>{
            const button=document.createElement('button');button.setAttribute('aria-label','Enviar');
            button.onclick=()=>{window.attempts=(window.attempts||0)+1;document.querySelector('#main header span').setAttribute('title','Outro contato')};
            el.appendChild(button);
        }""")
        result=await send_on_page(self.page, 'Contato de teste', 'Teste incerto')
        self.assertFalse(result['ok'])
        self.assertTrue(result['uncertain'])
        self.assertEqual(await self.page.evaluate('window.attempts'),1)

    async def test_search_outside_old_sidebar_by_accessible_name(self):
        await self.page.locator('#side').evaluate("el=>el.id='new-sidebar'")
        await self.page.locator('#new-sidebar [contenteditable]').evaluate("el=>el.setAttribute('aria-label','Pesquisar ou começar uma nova conversa')")
        self.assertTrue((await send_on_page(self.page, 'Contato de teste', 'Busca acessivel'))['ok'])

    async def test_input_placeholder_search_is_supported(self):
        await self.page.locator('#side').evaluate("el=>{el.id='new-sidebar';el.innerHTML='<input type=search placeholder=Pesquisar>';}")
        self.assertTrue((await send_on_page(self.page, 'Contato de teste', 'Busca input'))['ok'])

    async def test_hidden_search_duplicate_does_not_block(self):
        await self.page.locator('#side').evaluate("el=>{const clone=el.firstElementChild.cloneNode(true);clone.style.display='none';el.appendChild(clone);}")
        self.assertTrue((await send_on_page(self.page, 'Contato de teste', 'Busca visivel'))['ok'])

    async def test_visible_search_duplicates_never_send(self):
        await self.page.locator('#side').evaluate("el=>el.appendChild(el.firstElementChild.cloneNode(true))")
        result = await send_on_page(self.page, 'Contato de teste', 'Nao enviar')
        self.assertFalse(result['ok'])
        self.assertIn('mais de um', result['error'])
        self.assertEqual(await self.page.locator('#main [data-id]').count(), 0)
        self.assertEqual(await self.page.locator('#side [contenteditable]').all_inner_texts(), ['', ''])

    async def test_conversation_search_is_not_contact_search(self):
        await self.page.locator('#main').evaluate("el=>{const input=document.createElement('input');input.type='search';input.setAttribute('aria-label','Pesquisar nesta conversa');el.appendChild(input);}")
        self.assertTrue((await send_on_page(self.page, 'Contato de teste', 'Busca de contatos'))['ok'])
        self.assertEqual(await self.page.locator('#main input').input_value(), '')

    async def test_search_button_expands_field(self):
        await self.page.locator('#side').evaluate("el=>{el.innerHTML='<button aria-label=Pesquisar>Busca</button>';el.firstElementChild.onclick=()=>{el.innerHTML='<input type=search aria-label=Pesquisar>';};}")
        self.assertTrue((await send_on_page(self.page, 'Contato de teste', 'Busca recolhida'))['ok'])

    async def test_search_waits_for_delayed_field(self):
        await self.page.locator('#side').evaluate("el=>{el.innerHTML='';setTimeout(()=>el.innerHTML='<input type=search aria-label=Pesquisar>',350);}")
        search, error = await find_chat_search(self.page)
        self.assertIsNone(error)
        self.assertEqual(await search.count(), 1)

    async def test_empty_recipient_never_sends(self):
        result = await send_on_page(self.page, '', 'Nao enviar')
        self.assertFalse(result['ok'])
        self.assertEqual(await self.page.locator('#main [data-id]').count(), 0)

    async def test_wrong_header_blocks_send(self):
        await self.page.evaluate("window.wrong=true")
        result=await send_on_page(self.page,"Contato de teste","Nunca enviar")
        self.assertFalse(result["ok"])
        self.assertEqual(await self.page.locator('[data-id^="true_"]').count(),0)

    async def test_duplicate_name_blocks_send(self):
        await self.page.evaluate("document.querySelector('#pane-side').appendChild(document.querySelector('#pane-side span').cloneNode(true))")
        result=await send_on_page(self.page,"Contato de teste","Nunca enviar")
        self.assertFalse(result["ok"])
        self.assertIn("duplicado",result["error"])

    async def test_existing_draft_is_preserved(self):
        await self.page.locator('footer div').fill("Meu rascunho")
        result=await send_on_page(self.page,"Contato de teste","Não substituir")
        self.assertFalse(result["ok"])
        self.assertEqual(await self.page.locator('footer div').inner_text(),"Meu rascunho")

    async def test_controlled_browser_tab_listing_and_selection(self):
        from actions.browser_control import _BrowserSession
        session=_BrowserSession.__new__(_BrowserSession)
        session._context=self.page.context;session._page=self.page
        second=await self.page.context.new_page()
        await second.set_content("<title>Segunda aba de teste</title>")
        result=json.loads(await session.list_tabs())
        self.assertEqual(len(result["tabs"]),2)
        await session.switch_tab(1)
        self.assertIs(session._page,second)
        self.assertIn("inexistente",await session.switch_tab(99))
