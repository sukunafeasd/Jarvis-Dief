"""A user-linked isolated browser session; all sends verify chat and DOM result."""
import asyncio
import re
import threading
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

PROFILE = Path(__file__).resolve().parents[1] / "config/whatsapp_web"

SEARCH_NAME = re.compile(r"pesquis|buscar|busca|procur|search", re.IGNORECASE)


def contact_key(value):
    return ' '.join(''.join(char for char in unicodedata.normalize('NFKD', value.casefold())
                           if not unicodedata.combining(char)).split())


def message_key(value):
    return unicodedata.normalize('NFC', value).replace('\r\n','\n').replace('\xa0',' ').translate(
        dict.fromkeys(map(ord,'\u200b\u200e\u200f'))).strip()


TEXT_VALUE = r"""el=>{
    if(el.tagName==='INPUT'||el.tagName==='TEXTAREA')return el.value;
    function children(node){
        let result='';
        for(const child of node.childNodes){
            if(['DIV','P'].includes(child.tagName)&&result&&!result.endsWith('\n'))result+='\n';
            result+=text(child);
        }
        return result;
    }
    function text(node){
        if(node.nodeType===Node.TEXT_NODE)return node.nodeValue;
        if(node.nodeType!==Node.ELEMENT_NODE)return '';
        if(node.tagName==='BR')return '\n';
        if(node.tagName==='IMG')return node.getAttribute('alt')||'';
        const value=children(node);
        return ['DIV','P'].includes(node.tagName)?value+'\n':value;
    }
    return children(el);
}"""


def bounded_limit(value, default=10):
    try:
        return max(1, min(30, int(value)))
    except (ValueError, TypeError, OverflowError):
        return default


async def chat_list(page):
    pane = page.locator('#pane-side').filter(visible=True)
    if await pane.count() == 1:
        return pane
    candidates = page.locator('#side [role="grid"]').or_(
        page.get_by_role('grid', name=re.compile(r'conversas|chats', re.I))
    ).filter(visible=True)
    return candidates if await candidates.count() == 1 else None


async def _chat_rows(pane):
    rows = pane.locator('[role="listitem"], [role="row"]').filter(visible=True)
    if not await rows.count():
        rows = pane.locator('[data-testid="cell-frame-container"]').filter(visible=True)
    return rows


async def unread_on_page(page, limit=10):
    """Read sidebar previews without opening chats or marking messages read."""
    limit = bounded_limit(limit)
    pane = await chat_list(page)
    if pane is None:
        return {'ok': False, 'error': 'Lista de conversas ausente ou ambígua. Não concluí que não há mensagens.'}
    search, error = await find_chat_search(page)
    if search is None:
        return {'ok': False, 'error': error, 'note': 'Não consultei uma lista que poderia estar filtrada.'}
    original = await search.evaluate('el => el.isContentEditable ? el.innerText : el.value')
    original_scroll = await pane.evaluate('el=>el.scrollTop')
    found, scanned, reached_end = {}, set(), False
    try:
        if original.strip():
            await search.fill('')
            await asyncio.sleep(.35)
        await pane.evaluate('el=>el.scrollTop=0')
        for _ in range(12):
            rows = await _chat_rows(pane)
            if not await rows.count():
                text = (await pane.inner_text()).strip()
                empty = bool(re.search(r'nenhuma conversa|nenhum resultado|no chats|no results', text, re.I))
                if not empty:
                    return {'ok': False, 'error': 'O formato da lista não foi reconhecido. Não afirmei que sua caixa está vazia.'}
                reached_end = True
                break
            snapshots = await rows.evaluate_all(r"""rows=>rows.map(row=>{
                const titles=[...row.querySelectorAll('span[title]')].map(el=>el.getAttribute('title')).filter(Boolean);
                const name=titles[0]||'';
                const badge=[...row.querySelectorAll('[aria-label], [data-icon]')].find(el=>
                    /unread[-_]?count/i.test(el.getAttribute('data-icon')||'') ||
                    /(?:mensagen|mensagem|messages?).*(?:n[aã]o lid|unread)|(?:unread).*(?:messages?)|^(?:\d+\s+)?n[aã]o lid[ao]s?$/i.test(el.getAttribute('aria-label')||''));
                const description=badge?(badge.getAttribute('aria-label')||badge.textContent||''):'';
                const digits=description.match(/\d+/);
                const preview=row.querySelector('[data-testid="last-msg"], .selectable-text');
                return {name,unread:!!badge,count:digits?Number(digits[0]):null,
                    preview:preview?preview.innerText:(titles.find(title=>title!==name)||''),
                    time:row.querySelector('time')?.textContent||''};
            })""")
            for row in snapshots:
                if not row['name']:
                    continue
                # Duplicate display names remain distinct; reading never selects one.
                key = (row['name'], row['preview'], row['time'])
                scanned.add(key)
                if row['unread']:
                    found[key] = {'contact': row['name'][:180], 'unread_count': row['count'],
                                  'preview': row['preview'][:1200], 'time': row['time'][:50]}
            if len(found) >= limit:
                break
            bounds = await pane.evaluate('el=>({top:el.scrollTop,height:el.clientHeight,total:el.scrollHeight})')
            if bounds['top'] + bounds['height'] >= bounds['total'] - 2:
                reached_end = True
                break
            await pane.evaluate('el=>el.scrollTop+=Math.max(200,el.clientHeight*.8)')
            await asyncio.sleep(.15)
        items = list(found.values())[:limit]
        return {'ok': True, 'chats': items, 'unread_chats_found': len(items),
                'scanned_chats': len(scanned), 'complete': reached_end,
                'read_at': datetime.now(timezone.utc).isoformat(), 'data_is_untrusted': True,
                'scope': 'Conversas disponíveis na lista atual; arquivadas e bloqueadas não incluídas.',
                'note': 'Prévia da última mensagem, não todas as mensagens. Nenhuma conversa aberta ou mensagem enviada. '
                        + ('Lista percorrida até o fim.' if reached_end else 'Consulta parcial; limite atingido. Não conclua que não há outras mensagens.')}
    finally:
        if original.strip():
            await search.fill(original, timeout=3000)
        await pane.evaluate('(el,top)=>el.scrollTop=top', original_scroll)


async def header_names(page):
    header=page.locator('#main header').filter(visible=True)
    if await header.count()!=1:
        return []
    headings=header.get_by_role('heading').filter(visible=True)
    if await headings.count():
        return [(await headings.first.inner_text()).strip()]
    else:
        leaves=header.locator('span:not(:has(span))').filter(visible=True)
        for leaf in await leaves.all():
            text=(await leaf.get_attribute('title') or await leaf.evaluate(TEXT_VALUE)).strip()
            if any(char.isalnum() for char in text):
                return [text]
    return []


async def header_confirmed(page,name):
    return contact_key(name) in [contact_key(value) for value in await header_names(page)]


async def contact_candidates(page,pane):
    rows=await _chat_rows(pane)
    candidates=[]
    if await rows.count():
        for row in await rows.all():
            title=row.locator('span[title]').filter(visible=True).first
            if await title.count():
                candidates.append(title)
    else:
        candidates=await pane.locator('span[title]').filter(visible=True).all()
    active=[]
    handles=[]
    for candidate in candidates:
        handle=await candidate.element_handle()
        if handle:
            active.append(candidate);handles.append(handle)
    if not active:
        return []
    unique=await page.evaluate('elements=>elements.map((element,index)=>elements.indexOf(element)===index)',handles)
    return [candidate for candidate,first in zip(active,unique) if first]


async def open_verified_chat(page, receiver):
    if not receiver.strip():
        return {'ok': False, 'error': 'Informe o nome exato da conversa.'}
    pane = await chat_list(page)
    if pane is None:
        return {'ok': False, 'error': 'WhatsApp Web não conectado. Vincule pelo QR nas Conexões.'}
    search, error = await find_chat_search(page)
    if search is None:
        return {'ok': False, 'error': error}
    await search.fill(receiver, timeout=5000)
    value = await search.evaluate('el => el.isContentEditable ? el.innerText : el.value')
    if value.strip() != receiver.strip():
        return {'ok': False, 'error': 'A busca não confirmou o nome solicitado.'}
    for _ in range(40):
        contacts=await contact_candidates(page,pane)
        exact = [item for item in contacts if contact_key(await item.get_attribute('title')) == contact_key(receiver)]
        if exact:
            break
        await asyncio.sleep(.2)
    if len(exact) != 1:
        return {'ok': False, 'stage':'contact_results','error': 'Contato não encontrado ou nome duplicado. Não abri uma conversa ao acaso.',
                'candidates':[await item.get_attribute('title') for item in contacts[:10]]}
    actual = await exact[0].get_attribute('title')
    previous_header = await header_names(page)
    previous_ids = await page.locator('#main [data-id]').evaluate_all("els=>els.map(el=>el.getAttribute('data-id'))")
    await exact[0].click()
    for _ in range(40):
        if await header_confirmed(page,actual):
            break
        await asyncio.sleep(.2)
    else:
        return {'ok': False,'stage':'chat_header', 'error': 'O cabeçalho não confirmou o contato. Não li nem enviei mensagens.'}
    return {'ok': True, 'recipient': actual, 'conversation_changed': actual not in previous_header, 'previous_ids': previous_ids}


async def read_chat_on_page(page, receiver, limit=10):
    verified = await open_verified_chat(page, receiver)
    if not verified['ok']:
        return verified
    # Wait for the selected conversation, not the previous chat's recycled rows.
    if verified['conversation_changed'] and verified['previous_ids']:
        try:
            await page.wait_for_function("previous=>[...document.querySelectorAll('#main [data-id]')].some(el=>!previous.includes(el.getAttribute('data-id')))",arg=verified['previous_ids'],timeout=5000)
        except Exception:
            return {'ok': False, 'error': 'O contato mudou, mas não confirmei o carregamento das mensagens dessa conversa. Não li as mensagens antigas.'}
    messages = page.locator('#main [data-id]').filter(visible=True)
    try:
        await messages.first.wait_for(state='visible', timeout=4000)
    except Exception:
        return {'ok': False, 'error': 'Conversa confirmada, mas as mensagens ainda não foram identificadas. Não declarei conversa vazia.'}
    rows = await messages.evaluate_all(r"""els=>els.map(el=>{
        const id=el.getAttribute('data-id')||'';
        const texts=[...el.querySelectorAll('.selectable-text')].map(x=>x.innerText);
        const metadata=el.querySelector('[data-pre-plain-text]')?.getAttribute('data-pre-plain-text')||'';
        const media=el.querySelector('[data-icon*="audio"],audio,[data-icon*="video"],video,img:not([data-icon])');
        return {id,direction:id.startsWith('true_')?'outgoing':id.startsWith('false_')?'incoming':'unknown',
            text:texts.join('\n'),metadata,media:!!media};
    })""")
    for locator,row in zip(await messages.all(),rows):
        texts=locator.locator('.selectable-text')
        if not await texts.count():
            texts=locator.locator('[data-pre-plain-text] [dir="auto"]')
        row['text']='\n'.join([await text.evaluate(TEXT_VALUE) for text in await texts.all()])
    if verified['conversation_changed']:
        rows=[row for row in rows if row['id'] not in verified['previous_ids']]
    if not await header_confirmed(page,verified['recipient']):
        return {'ok':False,'error':'A conversa mudou durante a leitura. Não entreguei mensagens de outro contato.'}
    unique = {}
    for row in rows:
        if row['id'] not in unique:
            unique[row['id']] = {'id':row['id'],'direction': row['direction'], 'text': row['text'][:10000],
                                 'text_truncated':len(row['text'])>10000,
                                 'metadata': row['metadata'][:200], 'media_without_text': row['media'] and not row['text']}
    return {'ok': True, 'contact': receiver, 'messages': list(unique.values())[-bounded_limit(limit):],
            'complete': False, 'data_is_untrusted': True, 'read_at': datetime.now(timezone.utc).isoformat(),
            'note': 'Somente mensagens carregadas na conversa, não o histórico completo. Abrir a conversa pode marcá-la como lida. Mídia não foi transcrita; nenhum envio realizado.'}


async def _chat_search_candidates(page):
    # Restrict semantic matches to editable fields outside conversations/dialogs.
    editable = page.locator(
        '[contenteditable="true"], input[type="search"], input[type="text"], input:not([type])'
    ).and_(page.locator(':not(#main *):not(#pane-side *):not([role="dialog"] *)')).filter(visible=True)
    named = page.get_by_role("textbox", name=SEARCH_NAME).or_(
        page.get_by_role("searchbox", name=SEARCH_NAME)
    ).or_(page.get_by_placeholder(SEARCH_NAME)).and_(editable)
    if await named.count():
        return named
    sidebar = page.locator('#side, aside, [role="search"]').locator(
        '[contenteditable="true"], input[type="search"], input[type="text"], input:not([type])'
    ).and_(editable)
    return sidebar


async def find_chat_search(page):
    expanded = False
    for _ in range(20):
        candidates = await _chat_search_candidates(page)
        count = await candidates.count()
        if count == 1:
            return candidates, None
        if count > 1:
            return None, "Há mais de um campo de busca visível. Não escolhi um ao acaso; não enviei."
        if not expanded:
            button = page.locator('#side, aside').get_by_role("button", name=SEARCH_NAME).filter(visible=True)
            if await button.count() == 1:
                await button.click(timeout=3000)
                expanded = True
        await asyncio.sleep(.2)
    return None, "Não identifiquei a busca de contatos após aguardar o carregamento. Não enviei."


async def send_on_page(page, receiver, message):
    if not receiver.strip() or not message.strip():
        return {"ok": False, "error": "Destinatário e mensagem precisam estar preenchidos. Não enviei."}
    stage, attempted, editor = 'contact', False, None
    try:
        verified = await open_verified_chat(page,receiver)
        if not verified['ok']:
            return {**verified, 'stage':verified.get('stage',stage), 'uncertain':False}
        actual = verified['recipient']
        stage='chat_ready'
        if verified['conversation_changed'] and verified['previous_ids']:
            await page.wait_for_function("previous=>![...document.querySelectorAll('#main [data-id]')].some(el=>previous.includes(el.getAttribute('data-id')))",arg=verified['previous_ids'],timeout=5000)
        stage = 'composer'
        await page.locator('#main footer').wait_for(state='visible',timeout=8000)
        candidates=page.locator('#main footer [contenteditable="true"]:not([contenteditable="true"] [contenteditable="true"]), #main footer textarea').filter(visible=True)
        for _ in range(15):
            count=await candidates.count()
            if count:
                break
            await asyncio.sleep(.2)
        if count != 1:
            return {'ok':False,'stage':stage,'uncertain':False,'error':'Campo de mensagem ausente ou ambíguo. Não enviei.'}
        editor=candidates
        if message_key(await editor.evaluate(TEXT_VALUE)):
            return {"ok": False,'stage':stage,'uncertain':False, "error": "Há um rascunho na conversa. Preservei seu texto e não enviei."}
        before = set(await page.locator('#main [data-id^="true_"]').evaluate_all("els=>els.map(el=>el.getAttribute('data-id'))"))
        stage = 'message_verification'
        await editor.fill(message)
        if message_key(await editor.evaluate(TEXT_VALUE)) != message_key(message):
            return {'ok':False,'stage':stage,'uncertain':False,'error':'O editor não confirmou o texto solicitado. Não pressionei enviar; confira o rascunho.'}
        # Header is checked again immediately before the irreversible send.
        if not await header_confirmed(page,actual):
            return {"ok": False,'stage':'recipient_verification','uncertain':False, "error": "Conversa mudou antes do envio. Não pressionei enviar."}
        footer=page.locator('#main footer')
        send_button=footer.get_by_role('button',name=re.compile(r'^(enviar(?: mensagem)?|send(?: message)?)$',re.I)).or_(
            footer.locator('button, [role="button"]').filter(has=page.locator('[data-icon="send"], [data-icon="wds-ic-send-filled"]'))
        ).filter(visible=True)
        for _ in range(5):
            buttons=await send_button.count()
            if buttons:
                break
            await asyncio.sleep(.1)
        if buttons>1:
            return {'ok':False,'stage':'send_control','uncertain':False,'error':'Mais de um botão Enviar identificado. Mantive o texto como rascunho; não enviei.'}
        stage = 'dispatch'
        attempted = True
        if buttons==1:
            await send_button.click(timeout=4000)
        else:
            await editor.press('Enter',timeout=4000)
        stage = 'confirmation'
        for _ in range(24):
            if not await header_confirmed(page,actual):
                return {'ok':False,'stage':stage,'uncertain':True,'error':'A conversa mudou depois do acionamento. Confira o envio antes de tentar novamente.'}
            for item in await page.locator('#main [data-id^="true_"]').all():
                if await item.get_attribute("data-id") not in before:
                    text = [await element.evaluate(TEXT_VALUE) for element in await item.locator('.selectable-text').all()]
                    if message_key('\n'.join(text)) == message_key(message):
                        return {"ok": True, 'stage':'confirmed', "recipient": actual,
                                "status": "Mensagem confirmada na conversa. Entrega/leitura não confirmadas."}
            await asyncio.sleep(.25)
        return {"ok": False,'stage':stage, "uncertain": True,
                "error": "Envio acionado, mas não confirmei a mensagem na conversa. Confira antes de repetir."}
    except Exception as error:
        return {"ok": False,'stage':stage,'uncertain':attempted, "error": f"Falha na etapa {stage} ({type(error).__name__}). " +
                ('O envio pode ter sido acionado. Confira a conversa antes de repetir.' if attempted else 'Não pressionei enviar.')}


class WhatsAppWeb:
    def __init__(self):
        self.loop = None
        self.context = None
        self.page = None
        self.pw = None
        self.background = None
        self.ready = threading.Event()
        self.start_lock = threading.Lock()

    def _worker(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.lock = asyncio.Lock()
        self.ready.set()
        self.loop.run_forever()

    def _context_closed(self, context):
        if self.context is context:
            self.context = None
            self.page = None
            self.background = None

    async def _ensure_session(self, background):
        usable = self.page is not None and not self.page.is_closed()
        linked_visible = (self.context is not None and usable and background and
                          self.background is False and await self._connected())
        if self.context is not None and (not usable or (not background and self.background) or linked_visible):
            old_context = self.context
            await old_context.close()
            self._context_closed(old_context)
        if self.context is None:
            from playwright.async_api import async_playwright
            if self.pw is None:
                self.pw = await async_playwright().start()
            options = {"headless": background, "locale": "pt-BR",
                       "viewport": {"width": 1280, "height": 900}}
            edge = Path("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe")
            if edge.exists():
                options["executable_path"] = str(edge)
            context = await self.pw.chromium.launch_persistent_context(str(PROFILE), **options)
            self.context = context
            self.background = background
            context.on("close", lambda *_: self._context_closed(context))
            self.page = context.pages[0] if context.pages else await context.new_page()
            await self.page.goto("https://web.whatsapp.com", wait_until="domcontentloaded", timeout=30000)
            return True
        return False

    async def _connected(self, wait=False):
        if wait:
            for _ in range(60):
                if await chat_list(self.page) is not None:
                    return True
                await asyncio.sleep(.5)
            return False
        return await chat_list(self.page) is not None

    async def _execute(self, action, receiver, message, limit=10):
        async with self.lock:
            if action == "connect":
                await self._ensure_session(background=False)
                await self.page.bring_to_front()
                return {"ok": True, "status": "WhatsApp Web aberto. No iPhone: WhatsApp > Configurações > Aparelhos conectados > Conectar aparelho. Após carregar suas conversas, pode fechar esta janela; a sessão salva será reutilizada em segundo plano."}
            if action not in {"status", "send", "unread", "read_chat"}:
                return {"ok": False, "error": "Ação inválida."}
            if self.context is None and not PROFILE.exists():
                return {"ok": action == "status", "connected": False, "needs_link": True,
                        "error": "Conecte o WhatsApp Web pelo QR nas Conexões primeiro."}
            # Closing the linking window is not logout. Reload the same persistent
            # profile headlessly, and wait for WhatsApp to restore its account.
            opened = await self._ensure_session(background=True)
            connected = await self._connected(wait=True)
            if not connected:
                return {"ok": action == "status", "connected": False, "needs_link": True,
                        "error": "Não confirmei as conversas carregadas. Confira a internet; se persistir, use Conectar WhatsApp Web para verificar o QR ou a autorização."}
            if action == "status":
                return {"ok": True, "connected": True, "background": bool(self.background),
                        "status": "WhatsApp Web conectado" + (" em segundo plano." if self.background else ". Pode fechar a janela de conexão.")}
            if action == "send":
                return await send_on_page(self.page, receiver, message)
            if action == 'unread':
                return {**await unread_on_page(self.page,limit), 'background': bool(self.background)}
            if action == 'read_chat':
                return {**await read_chat_on_page(self.page,receiver,limit), 'background': bool(self.background)}
            return {"ok": False, "error": "Ação inválida."}

    def call(self, action, receiver="", message="", limit=10):
        with self.start_lock:
            if self.loop is None:
                if action != "connect" and not PROFILE.exists():
                    return {"ok": action == "status", "connected": False,
                            "error": "WhatsApp Web ainda não conectado nas Conexões."}
                threading.Thread(target=self._worker, daemon=True, name="WhatsAppWeb").start()
                if not self.ready.wait(5):
                    return {'ok': False, 'error': 'O serviço do WhatsApp não iniciou a tempo. Tente novamente.'}
        future = asyncio.run_coroutine_threadsafe(self._execute(action, receiver, message, limit), self.loop)
        try:
            return future.result(timeout=75)
        except Exception as error:
            future.cancel()
            return {"ok": False, "stage": "transport", "uncertain": action == "send",
                    "error": f"Operação não confirmada ({type(error).__name__}). Nenhuma repetição automática realizada."}


transport = WhatsAppWeb()
