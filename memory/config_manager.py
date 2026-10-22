import json
import sys
import os
import tempfile
import threading
from pathlib import Path

def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

def _resolve_config_dir() -> Path:
    try:
        from core.runtime_paths import get_config_dir
        return get_config_dir()
    except Exception:
        return get_base_dir() / "config"

BASE_DIR    = get_base_dir()
CONFIG_DIR  = _resolve_config_dir()
CONFIG_FILE = CONFIG_DIR / "api_keys.json"

_CONFIG_LOCK = threading.RLock()


def _read_config(path=None) -> dict:
    target = Path(path or CONFIG_FILE)
    if not target.is_file() and target != BASE_DIR / "config" / "api_keys.json":
        fallback = BASE_DIR / "config" / "api_keys.json"
        if fallback.is_file():
            target = fallback
    try:
        raw = target.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("Configuration must be a JSON object.")
    return data


def _update_config(update, *, path=None) -> None:
    """Serialize the entire read/update/write and replace only complete JSON.

    Refuse to overwrite unreadable settings: recovering a damaged file must not
    silently discard credentials or unrelated owner settings.
    """
    with _CONFIG_LOCK:
        target = Path(path or CONFIG_FILE)
        target.parent.mkdir(parents=True, exist_ok=True)
        data = _read_config(target)
        update(data)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8",
                    dir=target.parent, prefix=".zaya-config-", suffix=".tmp", delete=False) as stream:
                temporary = Path(stream.name)
                json.dump(data, stream, indent=4)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, target)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)


def ensure_config_dir() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

def config_exists() -> bool:
    return CONFIG_FILE.exists() or (BASE_DIR / "config" / "api_keys.json").exists()

def save_api_keys(gemini_api_key: str) -> None:
    from core.gemini_keys import parse_keys
    from core.security.key_vault import encrypt_secret
    keys = parse_keys(gemini_api_key)
    if not keys:
        raise ValueError('Enter at least one Gemini API key.')
    enc_keys = [encrypt_secret(k) for k in keys]
    _patch_config(gemini_api_key=enc_keys[0], gemini_api_keys=enc_keys)

def load_api_keys() -> dict:
    with _CONFIG_LOCK:
        try:
            data = _read_config()
            try:
                from core.security.key_vault import decrypt_secret
                for k in ('gemini_api_key', 'openai_api_key'):
                    if k in data and isinstance(data[k], str) and data[k]:
                        data[k] = decrypt_secret(data[k])
                if 'gemini_api_keys' in data and isinstance(data['gemini_api_keys'], list):
                    data['gemini_api_keys'] = [decrypt_secret(str(x)) for x in data['gemini_api_keys']]
                enc_keys = data.get("encrypted_keys")
                if isinstance(enc_keys, dict):
                    for prov, enc_val in enc_keys.items():
                        if isinstance(enc_val, str) and enc_val:
                            dec = decrypt_secret(enc_val)
                            data[f"{prov}_api_key"] = dec
                            if prov == "custom":
                                data["custom_api_key"] = dec
            except Exception:
                pass
            return data
        except (OSError, ValueError) as error:
            print(f"Failed to load api_keys.json ({type(error).__name__}).")
            return {}

def get_gemini_key() -> str | None:
    from core.gemini_keys import parse_keys
    config = load_api_keys()
    keys = parse_keys(config.get('gemini_api_keys')) or parse_keys(config.get('gemini_api_key'))
    return keys[0] if keys else None

def is_configured() -> bool:
    key = get_gemini_key()
    return bool(key and len(key) > 15)


def get_assistant_name() -> str:
    """Return the configured assistant name, or 'JARVIS' if not set."""
    return "Zaya"


def get_user_name() -> str:
    """Return the configured user name for addressing."""
    return load_api_keys().get("user_name", "")


def save_assistant_config(assistant_name: str, user_name: str) -> None:
    """Persist assistant name and user name to config."""
    _patch_config(assistant_name="Zaya", user_name=user_name.strip())


# ── Assistant voice ──────────────────────────────────────────────────────────
# Gemini Live prebuilt voices. Names are proper nouns — identical in every
# language, so this list is safe to show verbatim in any locale.
AVAILABLE_VOICES = ["Nika", "Charon", "Puck", "Kore", "Fenrir", "Aoede"]
DEFAULT_VOICE    = "Nika"


def get_voice() -> str:
    """Return the configured Live voice, falling back to the default if unset
    or if the stored value is not a voice we recognise."""
    v = load_api_keys().get("voice_name", DEFAULT_VOICE) or DEFAULT_VOICE
    return v if v in AVAILABLE_VOICES else DEFAULT_VOICE


def save_voice(voice_name: str) -> None:
    """Persist the chosen Live voice. Unknown names collapse to the default so a
    bad value can never reach the API and break the session."""
    voice = (voice_name or "").strip()
    _patch_config(voice_name=voice if voice in AVAILABLE_VOICES else DEFAULT_VOICE)


def get_wake_word_enabled() -> bool:
    """Whether local wake-word gating is on (assistant sleeps until 'Hey Jarvis')."""
    return load_api_keys().get("wake_word_enabled", False)


def save_wake_word_enabled(enabled: bool) -> None:
    _patch_config(wake_word_enabled=bool(enabled))


def get_push_to_talk_enabled() -> bool:
    """Hold-a-key-to-speak. When on, the mic is closed unless the chord is held."""
    return load_api_keys().get("push_to_talk_enabled", False)


def save_push_to_talk_enabled(enabled: bool) -> None:
    _save_flag("push_to_talk_enabled", enabled)


def get_double_clap_enabled() -> bool:
    """Whether acoustic double-clap wake activation is on."""
    return load_api_keys().get("double_clap_enabled", False) is True


def save_double_clap_enabled(enabled: bool) -> None:
    """Persist the double-clap preference without touching any other setting."""
    _save_flag("double_clap_enabled", bool(enabled))


def get_auto_execute_enabled() -> bool:
    """Only a saved boolean opt-in enables automatic owner operations."""
    return load_api_keys().get('auto_execute_owner', False) is True


def save_auto_execute_enabled(enabled: bool) -> None:
    """Local settings control; never exposed as a model tool parameter."""
    from core.execution_policy import trust_context, TRUST_LOCAL_OWNER
    if trust_context.get() != TRUST_LOCAL_OWNER:
        raise PermissionError('Only the local owner can change command permissions.')
    if not isinstance(enabled, bool):
        raise ValueError('Automatic execution must be true or false.')
    _save_flag('auto_execute_owner', enabled)


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
        current = data.get("turn_tuning")
        current = dict(current) if isinstance(current, dict) else {}
        current.update(values or {})
        data["turn_tuning"] = current
    _update_config(update)


def get_proactive_audio_enabled() -> bool:
    """Whether the model gets to decide an utterance was not aimed at it and
    stay quiet.

    Opt-in: a direct voice assistant must respond to owner speech by default.
    Selective audio lets the model silently ignore a correctly received
    utterance, which can appear to the owner as a broken microphone.
    """
    return load_api_keys().get("proactive_audio", False) is True


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
    _patch_config(morning_brief_enabled=bool(enabled))


# ── Audio devices ────────────────────────────────────────────────────────────
# Stored as device NAMES, not sounddevice indices. Indices shift every time a
# USB device is plugged in or removed, so a saved index silently starts pointing
# at a different microphone. The empty string means "system default", which is
# both the factory setting and what an unresolvable saved device falls back to —
# so unplugging a headset degrades to the built-in speakers instead of crashing.

def _patch_config(**fields) -> None:
    """Read-modify-write one or more keys in api_keys.json.

    Every setter in this file open-coded this. Collapsing it here means a new
    setting is one line, and there is one place where a corrupt config file is
    handled instead of nine."""
    _update_config(lambda data: data.update(fields))


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
    return load_api_keys().get("plugins_enabled", {}).get(plugin_name, True)


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
        plugins = data.get("plugin_config")
        plugins = dict(plugins) if isinstance(plugins, dict) else {}
        current = plugins.get(namespace)
        current = dict(current) if isinstance(current, dict) else {}
        current.update(values)
        plugins[namespace] = current
        data["plugin_config"] = plugins
    _update_config(update)


def save_plugin_enabled(plugin_name: str, enabled: bool) -> None:
    def update(data):
        plugins = data.get("plugins_enabled")
        plugins = dict(plugins) if isinstance(plugins, dict) else {}
        plugins[plugin_name] = bool(enabled)
        data["plugins_enabled"] = plugins
    _update_config(update)
