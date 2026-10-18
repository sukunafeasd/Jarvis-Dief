import json
import sys
from pathlib import Path

def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

BASE_DIR    = get_base_dir()
from core.local_data import ROOT as DATA_ROOT,migrate
CONFIG_FILE = DATA_ROOT/'api_keys.json'
DEFAULT_CONFIG_FILE=CONFIG_FILE
CONFIG_DIR = CONFIG_FILE.parent

def prepare_storage():
    if CONFIG_FILE==DEFAULT_CONFIG_FILE:migrate(BASE_DIR/'config/api_keys.json','api_keys.json')


def ensure_config_dir() -> None:
    prepare_storage()
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)

def config_exists() -> bool:
    prepare_storage()
    return CONFIG_FILE.exists()

def _reject_json_constant(value):
    raise ValueError('Configuracao invalida; arquivo existente preservado.')


def mutate_config(mutation, *, path=None) -> None:
    """Serialize a strict read-modify-write; failed mutations preserve the file."""
    from core.local_data import LOCK, atomic_write
    with LOCK:
        target = Path(path) if path is not None else CONFIG_FILE
        if target == CONFIG_FILE:
            prepare_storage()
        try:
            data = json.loads(target.read_text(encoding='utf-8'), parse_constant=_reject_json_constant)
        except FileNotFoundError:
            data = {}
        if not isinstance(data, dict):
            raise ValueError('Configuracao invalida; arquivo existente preservado.')
        mutation(data)
        raw = json.dumps(data, indent=4, ensure_ascii=False, allow_nan=False).encode('utf-8')
        atomic_write(target, raw)


def save_api_keys(gemini_api_key: str, *, path=None) -> None:
    mutate_config(lambda data: data.update(gemini_api_key=gemini_api_key.strip()), path=path)

def load_api_keys() -> dict:
    prepare_storage()
    if not CONFIG_FILE.exists():
        return {}
    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception as e:
        print(f"❌ Failed to load api_keys.json: {e}")
        return {}

def get_gemini_key() -> str | None:
    return load_api_keys().get("gemini_api_key")

def is_configured() -> bool:
    key = get_gemini_key()
    return bool(key and len(key) > 15)


def get_assistant_name() -> str:
    """Return the configured assistant name, or 'JARVIS' if not set."""
    return load_api_keys().get("assistant_name", "DIEF JARVIS") or "DIEF JARVIS"


def get_user_name() -> str:
    """Return the configured user name for addressing."""
    return load_api_keys().get("user_name", "")


def save_assistant_config(assistant_name: str, user_name: str) -> None:
    """Persist assistant name and user name to config."""
    _patch_config(assistant_name=assistant_name.strip() or 'DIEF JARVIS', user_name=user_name.strip())


# ── Assistant voice ──────────────────────────────────────────────────────────
# Gemini Live prebuilt voices. Names are proper nouns — identical in every
# language, so this list is safe to show verbatim in any locale.
AVAILABLE_VOICES = ["Charon", "Puck", "Kore", "Fenrir", "Aoede"]
DEFAULT_VOICE    = "Charon"


def get_voice() -> str:
    """Return the configured Live voice, falling back to the default if unset
    or if the stored value is not a voice we recognise."""
    v = load_api_keys().get("voice_name", DEFAULT_VOICE) or DEFAULT_VOICE
    return v if v in AVAILABLE_VOICES else DEFAULT_VOICE


def save_voice(voice_name: str) -> None:
    """Persist the chosen Live voice. Unknown names collapse to the default so a
    bad value can never reach the API and break the session."""
    v = (voice_name or "").strip()
    _patch_config(voice_name=v if v in AVAILABLE_VOICES else DEFAULT_VOICE)


def get_wake_word_enabled() -> bool:
    """Legacy preference no longer gates conversation."""
    return False


def save_wake_word_enabled(enabled: bool) -> None:
    _save_flag('wake_word_enabled', bool(enabled))


def get_push_to_talk_enabled() -> bool:
    """Legacy preference no longer requires a held key."""
    return False


def save_push_to_talk_enabled(enabled: bool) -> None:
    _save_flag("push_to_talk_enabled", enabled)


HUD_STYLES = ("face", "core")


def get_hud_style() -> str:
    """Which centrepiece the HUD draws: the animated head, or the reactor core.

    Taste, not capability — both render in the same software painter and cost
    about the same. Defaults to the head because that is what MARK LIV shipped
    with; anyone who preferred the older look can switch back in ⚙ and the
    choice survives a restart.
    """
    v = str(load_api_keys().get("hud_style", "face")).strip().lower()
    return v if v in HUD_STYLES else "face"


def save_hud_style(style: str) -> None:
    s = str(style or "").strip().lower()
    _save_flag("hud_style", s if s in HUD_STYLES else "face")


# ── Live-session tuning ──────────────────────────────────────────────────────
# Everything here is optional and has a working default, so an untouched
# config behaves exactly like a configured one. Each value is also a way out:
# if a future model dislikes one of these, set it back and nothing else changes.

def get_thinking_enabled() -> bool:
    """Whether the Live model may spend tokens thinking before it answers.

    Off by default. A voice assistant is judged on how fast it starts talking,
    and the reasoning that actually needs deliberation in this app is delegated
    to the planning tools, which run on a separate non-Live model.
    """
    return bool(load_api_keys().get("thinking_enabled", False))


def save_thinking_enabled(enabled: bool) -> None:
    _save_flag("thinking_enabled", enabled)


def get_turn_tuning() -> dict:
    """How eagerly the server decides you have stopped speaking.

    OFF by default, and that default was earned. Cutting turns shorter looks
    like a free speed win and is not: proactive audio has to judge whether an
    utterance was even addressed to the assistant, and a turn clipped early
    gives it less to judge, so it stays quiet — and the reply to your first
    sentence only arrives once your second one has given it enough context.
    That reads as the assistant being a turn behind, which is far worse than
    the fraction of a second the tuning saves.

    Turn it on with "turn_tuning": {"enabled": true} if your own microphone and
    speaking pace suit it. `silence_ms` is the one that is felt: the pause the
    server sits through before accepting your turn is over.
    """
    cfg = load_api_keys().get("turn_tuning")
    cfg = cfg if isinstance(cfg, dict) else {}

    def _int(key, default, lo, hi):
        try:
            return max(lo, min(hi, int(cfg.get(key, default))))
        except (TypeError, ValueError):
            return default

    return {
        "enabled":    bool(cfg.get("enabled", False)),
        "silence_ms": _int("silence_ms", 550, 200, 3000),
        "prefix_ms":  _int("prefix_ms", 150, 0, 1000),
        # "high" = quicker to decide speech has ended.
        "end_sensitivity":   str(cfg.get("end_sensitivity", "high")).lower(),
        "start_sensitivity": str(cfg.get("start_sensitivity", "default")).lower(),
    }


def save_turn_tuning(values: dict) -> None:
    def update(data):
        cur = data.get('turn_tuning', {})
        if not isinstance(cur, dict):
            raise ValueError('Configuracao de turnos invalida; arquivo existente preservado.')
        data['turn_tuning'] = {**cur, **(values or {})}
    mutate_config(update)


def get_proactive_audio_enabled() -> bool:
    """Whether the model gets to decide an utterance was not aimed at it and
    stay quiet.

    Off by default: server-side selective silence can ignore direct calls and
    make a normal conversation appear a turn behind. Explicit opt-in remains
    available; local echo/VAD guards still protect the microphone path.
    """
    return bool(load_api_keys().get("proactive_audio", False))


def save_proactive_audio_enabled(enabled: bool) -> None:
    _save_flag("proactive_audio", enabled)


MEDIA_RESOLUTIONS = ("default", "low", "medium", "high")


def get_media_resolution() -> str:
    """How finely the model tokenises the screenshots and camera frames it is
    sent. 'medium' keeps on-screen text readable at a fraction of the tokens a
    full-resolution frame costs; 'low' is cheaper still but starts losing small
    text, which is most of what screen captures are for."""
    v = str(load_api_keys().get("media_resolution", "medium")).strip().lower()
    return v if v in MEDIA_RESOLUTIONS else "medium"


def save_media_resolution(value: str) -> None:
    v = str(value or "").strip().lower()
    _save_flag("media_resolution", v if v in MEDIA_RESOLUTIONS else "medium")


def _save_flag(key: str, value) -> None:
    """Read-modify-write one key without disturbing the rest of the config."""
    _patch_config(**{key: value})


def get_brief_enabled() -> bool:
    return load_api_keys().get("morning_brief_enabled", True)


def save_brief_enabled(enabled: bool) -> None:
    _save_flag('morning_brief_enabled', enabled)


# ── Audio devices ────────────────────────────────────────────────────────────
# Stored as device NAMES, not sounddevice indices. Indices shift every time a
# USB device is plugged in or removed, so a saved index silently starts pointing
# at a different microphone. The empty string means "system default", which is
# both the factory setting and what an unresolvable saved device falls back to —
# so unplugging a headset degrades to the built-in speakers instead of crashing.

def _patch_config(**fields) -> None:
    """Atomically merge one or more top-level preferences."""
    mutate_config(lambda data: data.update(fields))


def get_input_device() -> str:
    """Microphone device name, or '' for the system default."""
    return (load_api_keys().get("input_device", "") or "").strip()


def save_input_device(name: str) -> None:
    _patch_config(input_device=(name or "").strip())


def get_output_device() -> str:
    """Speaker device name, or '' for the system default."""
    return (load_api_keys().get("output_device", "") or "").strip()


def save_output_device(name: str) -> None:
    _patch_config(output_device=(name or "").strip())


def get_plugin_enabled(plugin_name: str) -> bool:
    """Plugins are enabled by default the moment they're discovered (opt-out model)."""
    plugins = load_api_keys().get('plugins_enabled')
    plugins = plugins if isinstance(plugins, dict) else {}
    return bool(plugins.get(plugin_name, True))


# ── Per-plugin settings ("tokens" / connection details) ───────────────────────
# Generic store so a plugin can declare its own config fields (PLUGIN_SETTINGS)
# and the settings UI renders + persists them WITHOUT any core edit — keeping the
# drop-in model intact. Values live under plugin_config[<namespace>][<key>].
# A namespace defaults to the plugin name, but a suite of plugins (e.g. the
# several printer plugins) can share ONE namespace.
def get_plugin_config(namespace: str) -> dict:
    """All stored values for a namespace (empty dict if none set yet)."""
    cfg = load_api_keys().get("plugin_config")
    val = cfg.get(namespace) if isinstance(cfg, dict) else None
    return dict(val) if isinstance(val, dict) else {}


def get_plugin_setting(namespace: str, key: str, default=None):
    """A single value from a namespace, or `default` if unset."""
    return get_plugin_config(namespace).get(key, default)


def save_plugin_config(namespace: str, values: dict) -> None:
    """Merge `values` into a namespace's stored config (read-modify-write, like
    every other helper here). Only the provided keys are touched."""
    def update(data):
        pc=data.get('plugin_config',{})
        if not isinstance(pc,dict):raise ValueError('Configuracao de plugins invalida; arquivo existente preservado.')
        cur=pc.get(namespace,{})
        if not isinstance(cur,dict):raise ValueError('Configuracao do plugin invalida; arquivo existente preservado.')
        pc[namespace]={**cur,**values};data['plugin_config']=pc
    mutate_config(update)


def save_plugin_enabled(plugin_name: str, enabled: bool) -> None:
    def update(data):
        plugins_cfg=data.get('plugins_enabled',{})
        if not isinstance(plugins_cfg,dict):raise ValueError('Configuracao de plugins invalida; arquivo existente preservado.')
        plugins_cfg[plugin_name]=enabled
        data['plugins_enabled']=plugins_cfg
    mutate_config(update)
