"""Last update failure, with no credentials, URLs or exception text."""
from datetime import datetime, timezone
from pathlib import Path
import urllib.error


def record_failure(root, stage, error, current=None, target=None):
    from core.distribution import atomic_json
    code=error.code if isinstance(error,urllib.error.HTTPError) else None
    category=('http' if code else 'timeout' if isinstance(error,TimeoutError)
              else 'network' if isinstance(error,urllib.error.URLError)
              else 'permission' if isinstance(error,PermissionError)
              else 'validation' if isinstance(error,ValueError) else 'unexpected')
    record={'time':datetime.now(timezone.utc).isoformat(), 'stage':stage,
            'category':category,'error_type':type(error).__name__,
            'http_status':code,'installed_version':current,'target_version':target}
    try:
        atomic_json(Path(root)/'logs'/'last-update-error.json',record)
    except OSError:
        pass
    return category
