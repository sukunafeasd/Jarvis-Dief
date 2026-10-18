"""Persistent local-day delivery state, separate from credentials/preferences."""
import json
from datetime import date, datetime
from pathlib import Path
from core.local_data import migrate,atomic_write,LOCK

STATE_FILE = migrate(Path(__file__).resolve().parents[1] / 'memory/daily_briefing.json','daily_briefing.json')


def delivered_today():
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8")).get("date") == date.today().isoformat()
    except (OSError, ValueError, AttributeError):
        return False


def mark_delivered(unavailable=None, summary=True, delivery_day=None):
    """Record the data's local date (ISO string or date), defaulting to today."""
    day = date.today() if delivery_day is None else date.fromisoformat(str(delivery_day))
    with LOCK:
        data = _state()
        data.update(date=day.isoformat(), updated_at=datetime.now().isoformat())
        data.update(pending_sources=list(unavailable or []),complete=not bool(unavailable),
                    delivery_kind='summary' if summary else 'context')
        atomic_write(STATE_FILE,json.dumps(data).encode('utf-8'))


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
    return False


def automatic_attempted_today():
    state=_state()
    if state.get('automatic_attempt_date')!=date.today().isoformat():return False
    if delivered_today():return True
    try:
        age=(datetime.now()-datetime.fromisoformat(state['automatic_attempt_at'])).total_seconds()
        return age<300
    except (KeyError,ValueError,TypeError):return False


def automatic_suppressed_today():
    return _state().get('automatic_suppressed_date')==date.today().isoformat()


def suppress_automatic_today():
    with LOCK:
        data=_state();data['automatic_suppressed_date']=date.today().isoformat()
        atomic_write(STATE_FILE,json.dumps(data).encode('utf-8'))


def contacted_today():
    return _state().get('contact_date')==date.today().isoformat()


def record_contact(automatic=False):
    with LOCK:
        data = _state(); data['last_contact'] = datetime.now().isoformat()
        data['contact_date']=date.today().isoformat()
        if automatic:
            data['automatic_attempt_date']=date.today().isoformat()
            data['automatic_attempt_at']=datetime.now().isoformat()
        atomic_write(STATE_FILE,json.dumps(data).encode('utf-8'))
