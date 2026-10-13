import json
import unittest
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
from core.whatsapp_web import unread_on_page, read_chat_on_page, bounded_limit, WhatsAppWeb

FIXTURE = '''<div id="side"><input type="search" aria-label="Pesquisar conversas"></div>
<div id="pane-side" style="height:300px;overflow:auto">
<div role="row"><span title="Ana" onclick="openChat('Ana')">Ana</span><span title="Oi, tudo bem?">Oi, tudo bem?</span><span aria-label="2 mensagens não lidas">2</span></div>
<div role="row"><span title="Grupo" onclick="openChat('Grupo')">Grupo</span><span class="selectable-text">Foto</span><span data-icon="unread-count">1</span></div>
<div role="row"><span title="Lida">Lida</span><span title="Bom dia">Bom dia</span></div>
</div><div id="main"><header><span title="Outro">Outro</span></header>
<div data-id="false_other_old"><span class="selectable-text">Não é de Ana</span></div>
<footer><div role="textbox" contenteditable="true">Meu rascunho</div></footer></div>
<script>window.clicks=0;function openChat(name){window.clicks++;
document.querySelector('#main header span').setAttribute('title',name);
setTimeout(()=>{document.querySelectorAll('#main [data-id]').forEach(el=>el.remove());
for(const [id,text] of [['false_ana_1','Olá!'],['true_ana_2','Tudo certo.'],['false_ana_3','Até amanhã.']]){
const el=document.createElement('div');el.setAttribute('data-id',id);
const span=document.createElement('span');span.className='selectable-text';span.textContent=text;el.append(span);document.querySelector('#main').append(el);}},100);}</script>'''


class WhatsAppReadingDOMTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        from playwright.async_api import async_playwright
        self.pw=await async_playwright().start()
        edge=Path('C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe')
        self.browser=await self.pw.chromium.launch(headless=True,**({'executable_path':str(edge)} if edge.exists() else {}))
        self.page=await self.browser.new_page()
        await self.page.set_content(FIXTURE)

    async def asyncTearDown(self):
        await self.browser.close();await self.pw.stop()

    async def test_unread_reads_real_badges_without_opening_or_sending(self):
        result=await unread_on_page(self.page)
        self.assertTrue(result['ok']);self.assertTrue(result['complete'])
        self.assertEqual([c['contact'] for c in result['chats']],['Ana','Grupo'])
        self.assertEqual([c['unread_count'] for c in result['chats']],[2,1])
        self.assertEqual(result['chats'][0]['preview'],'Oi, tudo bem?')
        self.assertEqual(await self.page.evaluate('window.clicks'),0)
        self.assertEqual(await self.page.locator('#main footer [contenteditable]').inner_text(),'Meu rascunho')

    async def test_unread_restores_existing_search_and_reports_partial_limit(self):
        await self.page.locator('#side input').fill('Filtro antigo')
        result=await unread_on_page(self.page,1)
        self.assertTrue(result['ok']);self.assertFalse(result['complete'])
        self.assertEqual(len(result['chats']),1)
        self.assertEqual(await self.page.locator('#side input').input_value(),'Filtro antigo')

    async def test_bad_layout_is_error_not_empty_inbox(self):
        await self.page.locator('#pane-side').evaluate('el=>el.innerHTML="Layout desconhecido"')
        result=await unread_on_page(self.page)
        self.assertFalse(result['ok']);self.assertNotIn('chats',result)

    async def test_read_waits_for_new_chat_and_preserves_draft(self):
        result=await read_chat_on_page(self.page,'Ana',2)
        self.assertTrue(result['ok']);self.assertFalse(result['complete'])
        self.assertEqual(result['contact'],'Ana')
        self.assertEqual([m['text'] for m in result['messages']],['Tudo certo.','Até amanhã.'])
        self.assertEqual([m['direction'] for m in result['messages']],['outgoing','incoming'])
        self.assertEqual(await self.page.locator('#main footer [contenteditable]').inner_text(),'Meu rascunho')

    async def test_duplicate_contact_never_opens_or_reads(self):
        await self.page.locator('#pane-side').evaluate('el=>el.append(el.firstElementChild.cloneNode(true))')
        result=await read_chat_on_page(self.page,'Ana')
        self.assertFalse(result['ok']);self.assertEqual(await self.page.evaluate('window.clicks'),0)

    async def test_english_unread_badge_and_no_numeric_count(self):
        await self.page.locator('[aria-label="2 mensagens não lidas"]').evaluate('el=>{el.setAttribute("aria-label","Unread messages");el.textContent="";}')
        result=await unread_on_page(self.page)
        self.assertTrue(result['ok']);self.assertIsNone(result['chats'][0]['unread_count'])

    async def test_hidden_list_is_not_connected(self):
        await self.page.locator('#pane-side').evaluate('el=>el.style.display="none"')
        session=WhatsAppWeb();session.page=self.page
        self.assertFalse(await session._connected())

    async def test_nested_semantic_grid_does_not_duplicate_chat_list(self):
        await self.page.locator('#pane-side').evaluate('el=>{const grid=document.createElement("div");grid.setAttribute("role","grid");grid.setAttribute("aria-label","Conversas");el.append(grid);}')
        result=await unread_on_page(self.page)
        self.assertTrue(result['ok']);self.assertEqual(result['unread_chats_found'],2)


class WhatsAppReadingPluginTests(unittest.TestCase):
    def test_new_messages_plugin_calls_unread_not_status_or_desktop(self):
        from plugins import whatsapp_web as plugin
        result={'ok':True,'chats':[{'contact':'Ana','preview':'Oi','unread_count':2}],'note':'Prévia real'}
        context=Mock();player=Mock()
        with patch.object(plugin.transport,'call',return_value=result) as call:
            self.assertTrue(json.loads(plugin.run({'action':'unread'},session_memory=context,player=player))['ok'])
            call.assert_called_once_with('unread',receiver='',limit=10)
            player.show_manifestation.assert_called_once();context.select.assert_called_once_with('WhatsApp Web')

    def test_read_requires_contact_and_rejects_send_in_read_plugin(self):
        from plugins import whatsapp_web as plugin
        with patch.object(plugin.transport,'call') as call:
            self.assertFalse(json.loads(plugin.run({'action':'read_chat'}))['ok'])
            self.assertFalse(json.loads(plugin.run({'action':'send'}))['ok'])
            call.assert_not_called()

    def test_limits_are_bounded(self):
        self.assertEqual(bounded_limit(9999),30)
        self.assertEqual(bounded_limit(-1),1)
        self.assertEqual(bounded_limit('bad'),10)
