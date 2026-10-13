#web_search.py
import json
import sys
import threading
import time
import re
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
    """Run fn() in a daemon thread; return its result, or None if it overruns."""
    box = [None]

    def _run():
        try:
            box[0] = fn()
        except Exception as e:
            _log_gemini_failure(label, e)

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    t.join(timeout)
    if t.is_alive():
        print(f"[WebSearch] {label} exceeded {timeout:.0f}s — moving on")
    return box[0]

def _get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


BASE_DIR        = _get_base_dir()
API_CONFIG_PATH = BASE_DIR / "config" / "api_keys.json"


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
            for r in ddgs.text(query, region="br-pt", max_results=max_results):
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
            for r in ddgs.news(query, region="br-pt", max_results=max_results):
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
    from concurrent.futures import ThreadPoolExecutor
    preferences=read_profile()
    query=query or preferences["news_interests"] or "notícias Brasil mundo hoje"
    topics=[topic.strip() for topic in query.split(',') if topic.strip()][:3]
    def find_records():
        if len(topics)<=1:
            return _ddg_news(query,preferences['news_count'])
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures=[pool.submit(_ddg_news,topic,preferences['news_count']) for topic in topics]
            batches=[]
            for future in futures:
                try:batches.append(future.result(timeout=6))
                except Exception:batches.append([])
        records=[];seen=set()
        for rank in range(preferences['news_count']):
            for batch in batches:
                if rank<len(batch):
                    record=batch[rank];identity=record.get('url') or record['title']
                    if identity not in seen:records.append(record);seen.add(identity)
        return records
    records=_run_bounded(find_records,timeout=9,label="Notícias com imagens") or []
    records=records[:preferences["news_count"]]
    items=[{"title":r["title"],"detail":r.get("snippet",""),"source":r.get("source",""),"url":r.get("url","")} for r in records]
    if items:
        def image_for(record):
            direct=thumbnail(record.get('image_url','')) if record.get('image_url') else ''
            return direct or article_thumbnail(record.get('url',''))
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures={pool.submit(image_for,r):i for i,r in enumerate(records)}
            for future,index in futures.items():
                try:
                    items[index]["image"]=future.result(timeout=5)
                except Exception:
                    items[index]["image"]=""
        illustrated=sorted(zip(records,items),key=lambda pair:not bool(pair[1].get('image')))
        records=[record for record,item in illustrated];items=[item for record,item in illustrated]
        text=_format_news(query,records)
    else:
        text=_news(query)
    return {"text":text,"model":{"kind":"news","title":"NOTÍCIAS","items":items,"text":text if not items else "","source":"Fontes consultadas","narrationDriven":True}}


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
        f"Current world news: {n} headlines. Numbered list, titles only.",
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
        return _gemini_search(query)
    except Exception as e:
        _log_gemini_failure("Gemini search", e)
        results = _ddg_search(query)
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
        return _format_news(ddg_query, _ddg_news(ddg_query, max_results=8))

    text = _run_bounded(_ddg_attempt, timeout=5.0, label="DDG news")
    if text and len(text) > 60 and not text.startswith("No news found"):
        return text

    text = _run_bounded(
        lambda: _gemini_search(gemini_query), timeout=6.0, label="Gemini news"
    )
    if text and len(text) > 60:
        return text

    return f"Nenhuma notícia encontrada para: {query}"


def _research(query: str) -> str:
    """
    Deep dive — asks Gemini for a comprehensive answer with context.
    Falls back to a wider DDG fetch.
    """
    research_query = (
        f"Comprehensive, detailed explanation of: {query}. "
        "Include background context, key facts, current state, and important nuances."
    )
    try:
        return _gemini_search(research_query)
    except Exception as e:
        _log_gemini_failure("Gemini research", e)
        results = _ddg_search(query, max_results=10)
        return _format_ddg(query, results)


def _price(query: str) -> str:
    """Product price lookup — searches for current market prices."""
    price_query = f"current price of {query} — how much does it cost today"
    try:
        return _gemini_search(price_query)
    except Exception as e:
        _log_gemini_failure("Gemini price", e)
        results = _ddg_search(f"{query} price buy", max_results=6)
        return _format_ddg(query, results)


def _compare(items: list[str], aspect: str) -> str:
    query = (
        f"Compare {', '.join(items)} in terms of {aspect}. "
        "Give specific facts and data."
    )
    try:
        return _gemini_search(query)
    except Exception as e:
        _log_gemini_failure("Gemini compare", e)

    all_results: dict[str, list] = {}
    for item in items:
        try:
            all_results[item] = _ddg_search(f"{item} {aspect}", max_results=3)
        except Exception:
            all_results[item] = []

    lines = [f"Comparison — {aspect.upper()}", "─" * 40]
    for item in items:
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
    params = parameters or {}
    query  = params.get("query", "").strip()
    mode   = params.get("mode",  "search").lower().strip()
    items  = params.get("items", [])
    aspect = params.get("aspect", "general").strip() or "general"

    if mode == "news":
        if not query or query.lower() in ("notícias", "noticias", "notícias recentes", "noticias recentes"):
            query=""
        package=fetch_news_package(query)
        if player:
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
    params=dict(parameters or {})
    mode=str(params.get('mode','search')).lower().strip()
    query=str(params.get('query',''))
    if mode=='search' and re.search(r'\b(noticias|notícias|news|manchetes)\b',query,re.I):
        mode='news'
    params['mode']=mode
    result=_web_search(params,response,player,session_memory)
    if player and mode!='news' and result and not result.startswith(('No results','Search failed','Please provide')):
        labels={'search':'BUSCA','research':'PESQUISA','price':'PREÇOS','compare':'COMPARAÇÃO'}
        title=labels.get(mode,'RESULTADOS')
        player.show_manifestation({'kind':'search' if mode=='search' else 'data','title':title,'text':result})
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
