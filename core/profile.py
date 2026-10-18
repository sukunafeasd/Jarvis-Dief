"""Public preferences shared by UI and tools; never returns credentials."""
import json
from pathlib import Path

from memory.config_manager import CONFIG_FILE as CONFIG

def read_profile():
    try:
        config = json.loads(CONFIG.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        config = {}
    def bounded(key, default, minimum, maximum):
        try:
            return max(minimum, min(maximum, int(config.get(key, default))))
        except (TypeError, ValueError):
            return default
    return {"user_name": str(config.get("user_name", ""))[:100],
            "city": str(config.get("city", ""))[:120],
            "news_interests": str(config.get("news_interests", ""))[:1000],
            "news_count": bounded("news_count",5,1,10),
            "presentation_hold": bounded("presentation_hold",15,0,120)}
