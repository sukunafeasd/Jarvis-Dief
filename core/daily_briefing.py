"""Persistent local-day delivery state, separate from credentials/preferences."""
import json
import re
from datetime import date, datetime
from pathlib import Path

STATE_FILE = Path(__file__).resolve().parents[1] / "memory/daily_briefing.json"


def delivered_today():
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8")).get("date") == date.today().isoformat()
    except (OSError, ValueError, AttributeError):
        return False


def mark_delivered():
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary = STATE_FILE.with_suffix(".tmp")
    data = _state()
    data.update(date=date.today().isoformat(), updated_at=datetime.now().isoformat())
    temporary.write_text(json.dumps(data), encoding="utf-8")
    temporary.replace(STATE_FILE)


def _state():
    try:
        value = json.loads(STATE_FILE.read_text(encoding='utf-8'))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def refresh_due(text='', now=None):
    from core.briefing_presentation import explicit_refresh
    if explicit_refresh(text):return True
    now = now or datetime.now()
    state = _state()
    if state.get('date') != now.date().isoformat():
        return True
    try:
        updated = datetime.fromisoformat(state.get('updated_at', ''))
    except (ValueError,TypeError):
        return True
    if (now-updated).total_seconds() < 900:
        return False
    greeting = bool(re.search(r'\b(bom dia|boa tarde|boa noite|me atualiza|atualize meu dia)\b', text, re.I))
    try:
        absent = (now-datetime.fromisoformat(state.get('last_contact', state['updated_at']))).total_seconds() >= 14400
    except (ValueError,TypeError):
        absent = False
    return greeting or absent


def record_contact():
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    data = _state(); data['last_contact'] = datetime.now().isoformat()
    temporary = STATE_FILE.with_suffix('.tmp')
    temporary.write_text(json.dumps(data), encoding='utf-8'); temporary.replace(STATE_FILE)
