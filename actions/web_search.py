#web_search.py
import json
import sys
import threading
import time
import re
import queue
from concurrent.futures import wait, FIRST_COMPLETED
from core.bounded_work import BoundedWork

_SEARCH_WORK=BoundedWork()
from pathlib import Path

# ── Gemini grounding quota circuit breaker ────────────────────────────────────
# The google_search grounding tool has its own small quota, separate from plain
# generation.  Once it is spent every call returns 429 — so retrying it at the
# top of every search only adds a dead round-trip before the DDG fallback runs.
# After a quota error, skip Gemini entirely for a cooldown period.
_QUOTA_COOLDOWN_SEC  = 900          # 15 minutes
_quota_blocked_until = 0.0
_quota_lock          = threading.Lock()


def _gemini_available() -> bool:
    with _quota_lock:
        return time.monotonic() >= _quota_blocked_until


def _note_gemini_error(exc: Exception) -> None:
    """Trip the breaker when the error is a quota / rate-limit rejection."""
    global _quota_blocked_until
    msg = str(exc)
    if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
        with _quota_lock:
            already = time.monotonic() < _quota_blocked_until
            _quota_blocked_until = time.monotonic() + _QUOTA_COOLDOWN_SEC
        if not already:
            print(
                "[WebSearch] Gemini grounding quota exhausted — skipping it for "
                f"{_QUOTA_COOLDOWN_SEC // 60} min and serving results from DDG."
            )


class _QuotaCooldown(RuntimeError):
    """Raised instead of calling Gemini while the quota breaker is open."""


def _log_gemini_failure(context: str, exc: Exception) -> None:
    """Log a Gemini failure — silently when it is just the expected cooldown."""
    if isinstance(exc, _QuotaCooldown):
        return          # announced once when the breaker tripped; not a warning
    print(f"[WebSearch] \u26a0\ufe0f {context} failed ({exc}) — using DDG instead")


def _run_bounded(fn, timeout: float, label: str = "task"):
    """Return by the deadline; occupied workers continue counting against the cap."""
    future=None
    try:
        future=_SEARCH_WORK.submit(fn)
        return future.result(timeout=timeout)
    except (TimeoutError,queue.Full):
        if future:future.cancel()
        return None
    except Exception as error:
        _log_gemini_failure(label,error)
        return None


def _parallel_bounded(callbacks,timeout,workers=3):
    values=[None]*len(callbacks);jobs={};deadline=time.monotonic()+timeout
    next_index=0
    while (jobs or next_index<len(callbacks)) and time.monotonic()<deadline:
        while next_index<len(callbacks) and len(jobs)<max(1,workers):
            try:future=_SEARCH_WORK.submit(callbacks[next_index])
            except queue.Full:break
            jobs[future]=next_index;next_index+=1
        if not jobs:break
        done,_=wait(jobs,timeout=max(0,deadline-time.monotonic()),return_when=FIRST_COMPLETED)
        if not done:break
        for future in done:
            index=jobs.pop(future)
            try:values[index]=future.result()
            except Exception:pass
    for future in jobs:future.cancel()
    return values


def _localized(records):
    from core.search_locale import localize_records
    return _run_bounded(lambda:localize_records(records),6,'Traducao PT-BR') or []


def _localized_answer(text):
    if not text:return None
    from core.search_locale import portuguese
    if portuguese(text):return text
    records=_localized([{'title':'Resposta da pesquisa','snippet':text}])
    return records[0].get('snippet') if records else None

def _get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


BASE_DIR        = _get_base_dir()
from memory.config_manager import CONFIG_FILE as API_CONFIG_PATH


def _get_api_key() -> str:
    with open(API_CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)["gemini_api_key"]


def _gemini_search(query: str) -> str:
    if not _gemini_available():
        raise _QuotaCooldown("Gemini grounding is in quota cooldown")

    from core import gemini

    # Grounded search reads a live page, so it gets a longer deadline than the
    # default — but it still HAS one, and it still walks the fallback ladder.
    try:
        response = gemini.call(query, tier=gemini.SEARCH,
                               config={"tools": [{"google_search": {}}]},
                               timeout_ms=30_000)
        if response is None:
            raise RuntimeError("every Gemini model on the ladder failed")
    except Exception as e:
        _note_gemini_error(e)
        raise

    text = ""
    for part in response.candidates[0].content.parts:
        if hasattr(part, "text") and part.text:
            text += part.text

    text = text.strip()
    if not text:
        raise ValueError("Gemini returned an empty response.")
    return text


def _get_ddgs():
    """
    Returns the DDGS class.  The package was renamed duckduckgo-search -> ddgs;
    the legacy package's endpoints are now rejected by DuckDuckGo (news() gets a
    403 Ratelimit, text() silently returns zero results), so warn loudly if we
    end up on it instead of failing in silence.
    """
    try:
        from ddgs import DDGS
        return DDGS
    except ImportError:
        from duckduckgo_search import DDGS
        print(
            "[WebSearch] ⚠️ Using the deprecated 'duckduckgo-search' package — "
            "DuckDuckGo blocks its endpoints, so every search will come back "
            "empty.  Fix with:  pip install -U ddgs"
        )
        return DDGS


def _ddg_search(query: str, max_results: int = 6) -> list[dict]:
    DDGS = _get_ddgs()
    results = []
    try:
        with DDGS() as ddgs:
            for r in ddgs.text(query+' em português', region="br-pt", max_results=max_results):
                results.append({
                    "title":   r.get("title",  ""),
                    "snippet": r.get("body",   ""),
                    "url":     r.get("href",   ""),
                })
    except Exception as e:
        print(f"[WebSearch] ⚠️ DDG text() failed: {e}")
    return results


def _ddg_news(query: str, max_results: int = 8) -> list[dict]:
    """DDG news search — returns actual articles, not website homepages."""
    DDGS = _get_ddgs()
    results = []
    try:
        with DDGS() as ddgs:
            for r in ddgs.news(query+' em português', region="br-pt", max_results=max_results):
                results.append({
                    "title":   r.get("title",  ""),
                    "snippet": r.get("body",   ""),
                    "url":     r.get("url",    ""),
                    "source":  r.get("source", ""),
                    "image_url": r.get("image", ""),
                })
    except Exception as e:
        print(f"[WebSearch] ⚠️ DDG news() failed ({e}) — falling back to text search")
    # Also covers the legacy-package case, where news() returns an empty list
    # instead of raising.
    if not results:
        results = _ddg_search(query, max_results=max_results)
    return results


def fetch_news_package(query=""):
    from core.profile import read_profile
    from core.news_media import thumbnail, article_thumbnail
    preferences=read_profile()
    query=query or preferences["news_interests"] or "notícias Brasil mundo hoje"
    topics=[topic.strip() for topic in query.split(',') if topic.strip()][:3]
    def find_records():
        if len(topics)<=1:
            return _run_bounded(lambda:_ddg_news(query,preferences['news_count']),9,'Noticias') or []
        batches=[value or [] for value in _parallel_bounded([
            lambda topic=topic:_ddg_news(topic,preferences['news_count']) for topic in topics],8)]
        records=[];seen=set()
        for rank in range(preferences['news_count']):
            for batch in batches:
                if rank<len(batch):
                    record=batch[rank];identity=record.get('url') or record['title']
                    if identity not in seen:records.append(record);seen.add(identity)
        return records
    records=find_records()
    records=records[:preferences["news_count"]]
    records=_localized(records)
    items=[{"title":r["title"],"detail":r.get("snippet",""),"source":r.get("source",""),"url":r.get("url","")} for r in records]
    if items:
        def image_for(record):
            direct=thumbnail(record.get('image_url','')) if record.get('image_url') else ''
            return direct or article_thumbnail(record.get('url',''))
        images=_parallel_bounded([lambda record=record:image_for(record) for record in records],5)
        for index,image in enumerate(images):items[index]['image']=image or ''
        illustrated=sorted(zip(records,items),key=lambda pair:not bool(pair[1].get('image')))
        records=[record for record,item in illustrated];items=[item for record,item in illustrated]
        text=_format_news(query,records)
    else:
        text='Não consegui obter notícias em português nesta consulta. Tente novamente mais tarde.'
    return {"text":text,"model":{"kind":"news","title":"NOTÍCIAS","items":items,"text":text if not items else "","source":"Fontes consultadas · pt-BR","narrationDriven":True,
        'refresh':{'provider':'news','parameters':{'query':query}}}}


def _format_ddg(query: str, results: list[dict]) -> str:
    if not results:
        return f"Nenhum resultado para: {query}"

    lines = [f"Resultados da busca: {query}\n"]
    for i, r in enumerate(results, 1):
        if r.get("title"):   lines.append(f"{i}. {r['title']}")
        if r.get("snippet"): lines.append(f"   {r['snippet']}")
        if r.get("url"):     lines.append(f"   Fonte: {r['url']}")
        lines.append("")
    return "\n".join(lines).strip()


def _format_news(query: str, results: list[dict]) -> str:
    if not results:
        return f"Nenhuma notícia encontrada para: {query}"

    lines = [f"Últimas notícias: {query}\n"]
    for i, r in enumerate(results, 1):
        title = r.get("title", "")
        if not title:
            continue
        src = f"  [{r['source']}]" if r.get("source") else ""
        lines.append(f"{i}. {title}{src}")
        if r.get("snippet"):
            lines.append(f"   {r['snippet'][:140]}")
        if r.get("url"):
            lines.append(f"   {r['url']}")
        lines.append("")
    return "\n".join(lines).strip()


# ── Briefing helper ────────────────────────────────────────────────────────────

def _gemini_headlines(n: int = 5) -> tuple[list[str], str]:
    """
    Fetches current headlines via Gemini grounded search.
    Optimised for speed: minimal prompt + strict token cap.
    Returns (headline_list, raw_text_for_display).
    """
    import re
    from core import gemini

    response = gemini.call(
        f"Noticias atuais do Brasil e do mundo: {n} manchetes em portugues brasileiro. Lista numerada, apenas titulos.",
        tier=gemini.SEARCH,
        config={"tools": [{"google_search": {}}]},
        timeout_ms=30_000,
    )
    if response is None:
        return [], ""

    raw = ""
    for part in response.candidates[0].content.parts:
        if hasattr(part, "text") and part.text:
            raw += part.text

    headlines = []
    for line in raw.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        # Only accept lines that begin with a number — skips preamble/closing sentences
        if not re.match(r'^[\d]+[.\)\-]', line):
            continue
        clean = re.sub(r'^[\d]+[.\)\-]\s*', '', line)
        clean = re.sub(r'^\*+\s*',          '', clean).strip()
        if clean and len(clean) > 10:
            headlines.append(clean)

    return headlines[:n], raw.strip()


# ── Modes ──────────────────────────────────────────────────────────────────────

def _search(query: str) -> str:
    """Default search — Gemini grounded, DDG fallback."""
    try:
        answer=_run_bounded(lambda:_gemini_search(query+'\nResponda em português do Brasil. Priorize o contexto brasileiro, exceto se outro país ou idioma foi solicitado.'),12,'Busca principal')
        if not answer:raise TimeoutError('Busca principal excedeu o prazo')
        localized=_localized_answer(answer)
        if not localized:raise ValueError('Nao consegui traduzir os resultados')
        return localized
    except Exception as e:
        _log_gemini_failure("Gemini search", e)
        results = _localized(_run_bounded(lambda:_ddg_search(query),6,'Busca alternativa') or [])
        return _format_ddg(query, results)


def _news(query: str) -> str:
    """
    DDG first, Gemini as backup.

    The old version raced both backends in parallel and kept the first answer.
    That burned one google_search grounding call on *every* news request —
    including the startup briefing — even when DDG had already won the race.
    Grounding has a small quota, so it ran dry after a handful of launches and
    then 429'd for everything else (research/compare), which are the modes that
    actually need a synthesised answer.

    DDG news returns in well under a second and gives raw headlines, which is
    exactly what the briefing wants, so it goes first and Gemini is only touched
    when DDG comes back empty.
    """
    gemini_query = f"Notícias atuais sobre: {query}. Responda em português do Brasil." if query else "Principais notícias do mundo hoje em português do Brasil."
    ddg_query = query if query else "notícias do mundo hoje"

    def _ddg_attempt() -> str:
        results=_localized(_ddg_news(ddg_query,max_results=8))
        return _format_news(ddg_query,results) if results else ''

    text = _run_bounded(_ddg_attempt, timeout=5.0, label="DDG news")
    if text:
        return text

    text = _run_bounded(
        lambda: _gemini_search(gemini_query), timeout=6.0, label="Gemini news"
    )
    if text and len(text) > 60:
        return _localized_answer(text) or 'Não consegui apresentar as notícias em português agora.'

    return f"Nenhuma notícia encontrada para: {query}"


def _research(query: str) -> str:
    """
    Deep dive — asks Gemini for a comprehensive answer with context.
    Falls back to a wider DDG fetch.
    """
    research_query = (
        f"Pesquise em detalhes: {query}. Responda em português brasileiro. "
        "Inclua contexto, fatos, fontes e limites. Priorize o Brasil, sem alterar um país explicitamente solicitado."
    )
    try:
        answer=_run_bounded(lambda:_gemini_search(research_query),12,'Pesquisa detalhada')
        if not answer:raise TimeoutError('Pesquisa excedeu o prazo')
        localized=_localized_answer(answer)
        if not localized:raise ValueError('Nao consegui traduzir a pesquisa')
        return localized
    except Exception as e:
        _log_gemini_failure("Gemini research", e)
        results = _localized(_run_bounded(lambda:_ddg_search(query,max_results=10),6,'Pesquisa alternativa') or [])
        return _format_ddg(query, results)


def _price(query: str) -> str:
    """Product price lookup — searches for current market prices."""
    price_query = f"Preço atual de {query}. Responda em português brasileiro. Use mercado brasileiro e reais por padrão, preservando país ou moeda explicitamente solicitados. Cite as fontes."
    try:
        answer=_run_bounded(lambda:_gemini_search(price_query),12,'Consulta de precos')
        if not answer:raise TimeoutError('Consulta de precos excedeu o prazo')
        localized=_localized_answer(answer)
        if not localized:raise ValueError('Nao consegui traduzir os precos')
        return localized
    except Exception as e:
        _log_gemini_failure("Gemini price", e)
        results = _localized(_run_bounded(lambda:_ddg_search(f'{query} preço comprar',max_results=6),6,'Precos alternativos') or [])
        return _format_ddg(query, results)


def _compare(items: list[str], aspect: str) -> str:
    query = (
        f"Compare {', '.join(items)} quanto a {aspect}. Responda em português brasileiro. "
        "Priorize o Brasil sem alterar país explicitamente solicitado. Cite fatos e fontes verificadas."
    )
    try:
        answer=_run_bounded(lambda:_gemini_search(query),12,'Comparacao')
        if not answer:raise TimeoutError('Comparacao excedeu o prazo')
        localized=_localized_answer(answer)
        if not localized:raise ValueError('Nao consegui traduzir a comparacao')
        return localized
    except Exception as e:
        _log_gemini_failure("Gemini compare", e)

    all_results: dict[str, list] = {}
    selected=items[:5]
    batches=_parallel_bounded([lambda item=item:_ddg_search(f'{item} {aspect}',max_results=3) for item in selected],6)
    records=[{**record,'comparison_item':item} for item,batch in zip(selected,batches) for record in (batch or [])[:3]]
    for item in selected:all_results[item]=[]
    for record in _localized(records):all_results[record['comparison_item']].append(record)

    if not any(all_results.values()):return 'Nenhum resultado confirmado para esta comparação.'
    label={'price':'PREÇOS','specs':'ESPECIFICAÇÕES','reviews':'AVALIAÇÕES','features':'RECURSOS','general':'GERAL'}.get(aspect,aspect.upper())
    lines = [f"Comparação · {label}", "─" * 40]
    for item in items[:5]:
        lines.append(f"\n▸ {item}")
        for r in all_results.get(item, [])[:2]:
            if r.get("snippet"):
                lines.append(f"  • {r['snippet']}")
            if r.get("url"):
                lines.append(f"    {r['url']}")
    return "\n".join(lines)


# ── Public entry point ─────────────────────────────────────────────────────────

def _web_search(
    parameters:     dict,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    params = parameters if isinstance(parameters,dict) else {}
    query  = str(params.get('query') or '').strip()[:1000]
    mode   = str(params.get('mode') or 'search').lower().strip()
    raw_items=params.get('items',[])
    items=[item.strip()[:250] for item in raw_items if isinstance(item,str) and item.strip()][:5] if isinstance(raw_items,list) else []
    aspect = str(params.get('aspect') or 'general').strip()[:250] or 'general'

    if mode == "news":
        if not query or query.lower() in ("notícias", "noticias", "notícias recentes", "noticias recentes"):
            query=""
        package=fetch_news_package(query)
        if player and package['model'].get('items'):
            player.show_manifestation(package["model"])
        return package["text"]
    if not query and not items:
        return 'Informe o que deseja pesquisar.'

    if items and mode not in ("compare",):
        mode = "compare"

    if player:
        player.write_log(f"[Search:{mode}] {query or ', '.join(items)}")

    print(f"[WebSearch] 🔍 mode={mode!r}  query={query!r}")

    try:
        if mode == "compare" and items:
            return _compare(items, aspect)
        if mode == "news":
            return _news(query)
        if mode == "research":
            return _research(query)
        if mode == "price":
            return _price(query)
        return _search(query)

    except Exception as e:
        print(f"[WebSearch] ❌ All backends failed: {e}")
        return f"Falha na pesquisa: {e}"


def web_search(parameters,response=None,player=None,session_memory=None):
    params=dict(parameters) if isinstance(parameters,dict) else {}
    mode=str(params.get('mode','search')).lower().strip()
    query=str(params.get('query',''))
    if mode=='search' and re.search(r'\b(noticias|notícias|news|manchetes)\b',query,re.I):
        mode='news'
    params['mode']=mode
    result=_web_search(params,response,player,session_memory)
    if player and mode!='news' and result and not result.startswith(('No results','Search failed','Please provide','Nenhum resultado','Falha na pesquisa','Informe o que','Não consegui')):
        labels={'search':'BUSCA','research':'PESQUISA','price':'PREÇOS','compare':'COMPARAÇÃO'}
        title=labels.get(mode,'RESULTADOS')
        player.show_manifestation({'kind':'search' if mode=='search' else 'data','title':title,'text':result,
                                  'refresh':{'provider':'search','parameters':params}})
    return result


# ── Tool declaration (auto-discovered by core/action_loader.py) ──────────────
TOOL = {
    "name": "web_search",
    "description": "Searches the web. Use for ANY question about current facts, events, prices, or topics — always prefer this over guessing. Modes: 'search' (default), 'news' (latest headlines on a topic), 'research' (deep comprehensive answer), 'price' (product cost lookup), 'compare' (side-by-side comparison of items).",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "query": {
                "type": "STRING",
                "description": "Search query or topic"
            },
            "mode": {
                "type": "STRING",
                "description": "search | news | research | price | compare"
            },
            "items": {
                "type": "ARRAY",
                "items": {
                    "type": "STRING"
                },
                "description": "Items to compare (compare mode)"
            },
            "aspect": {
                "type": "STRING",
                "description": "Comparison aspect: price | specs | reviews | features"
            }
        },
        "required": [
            "query"
        ]
    },
    "handler": web_search,
}
