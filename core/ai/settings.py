"""Owner-facing AI engine settings with backward-compatible defaults."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from core.providers.catalog import provider_spec, provider_specs

VALID_ENGINE_MODES = {"gemini_live", "local_pipeline"}
_ALIASES = {
    "gemini": "gemini_live",
    "live": "gemini_live",
    "native": "gemini_live",
    "local": "local_pipeline",
    "offline": "local_pipeline",
    "pipeline": "local_pipeline",
    "modular": "local_pipeline",
}


def _runtime_root() -> Path:
    try:
        from core.runtime_paths import get_runtime_dir
        return get_runtime_dir()
    except Exception:
        return Path(__file__).resolve().parent.parent.parent / "logs" / "runtime"


def engine_mode() -> str:
    from memory.config_manager import load_api_keys
    raw = str(load_api_keys().get("engine_mode") or "gemini_live").strip().lower()
    raw = _ALIASES.get(raw, raw)
    return raw if raw in VALID_ENGINE_MODES else "gemini_live"


def save_engine_mode(mode: str) -> str:
    from memory.config_manager import _patch_config
    value = _ALIASES.get(str(mode or "").strip().lower(), str(mode or "").strip().lower())
    if value not in VALID_ENGINE_MODES:
        raise ValueError(f"Unknown engine mode: {mode}")
    _patch_config(engine_mode=value)
    return value


@dataclass
class LocalPipelineSettings:
    provider: str = "ollama"
    model: str = ""
    base_url: str = ""
    api_key: str = ""
    stt_provider: str = "faster_whisper"
    stt_model: str = "small"
    stt_device: str = "auto"
    stt_compute_type: str = "int8"
    stt_language: str = ""
    tts_provider: str = "piper"
    tts_model: str = ""
    tts_voice_map: dict[str, str] = field(default_factory=dict)
    tts_fallback_voice: str = ""
    allow_cloud_fallback: bool = False
    max_history_messages: int = 12
    vad_silence_ms: int = 650
    vad_min_speech_ms: int = 300
    max_tools: int = 0
    max_tool_schema_chars: int = 0
    timings: bool = True


def _as_int(value: Any, default: int, low: int, high: int) -> int:
    try:
        return max(low, min(high, int(value)))
    except (TypeError, ValueError):
        return default


def local_pipeline_settings() -> LocalPipelineSettings:
    from memory.config_manager import load_api_keys
    from core.security.key_vault import load_provider_key, decrypt_secret
    data = load_api_keys()
    # local_llm_provider is the local-engine choice. Do not inherit the live
    # engine's llm_provider here: selecting the modular engine without a
    # provider must stay local, never silently become a cloud request.
    provider = str(data.get("local_llm_provider") or "ollama").strip().lower()
    if provider not in {spec.key for spec in provider_specs()}:
        provider = "ollama"
    spec = provider_spec(provider)
    voice_map = data.get("local_tts_voice_map")
    if not isinstance(voice_map, dict):
        voice_map = {}
    cleaned_map = {
        str(key).strip().lower(): str(value).strip()
        for key, value in voice_map.items()
        if str(key).strip() and str(value).strip()
    }

    # Load decrypted API key via key vault or legacy keys
    api_key = load_provider_key(provider)
    if not api_key:
        raw_key = str(data.get(f"{provider}_api_key") or data.get("local_llm_api_key") or "").strip()
        if raw_key:
            api_key = decrypt_secret(raw_key)

    return LocalPipelineSettings(
        provider=provider,
        model=str(data.get("local_llm_model") or (spec.model if spec else "")).strip(),
        base_url=str(data.get("local_llm_base_url") or (spec.base_url if spec else "")).strip(),
        api_key=api_key,
        stt_provider=str(data.get("local_stt_provider") or "faster_whisper").strip().lower(),
        stt_model=str(data.get("local_stt_model") or "small").strip(),
        stt_device=str(data.get("local_stt_device") or "auto").strip(),
        stt_compute_type=str(data.get("local_stt_compute") or "int8").strip(),
        stt_language=str(data.get("local_stt_language") or "").strip(),
        tts_provider=str(data.get("local_tts_provider") or "piper").strip().lower(),
        tts_model=str(data.get("local_tts_model") or "").strip(),
        tts_voice_map=cleaned_map,
        tts_fallback_voice=str(data.get("local_tts_fallback_voice") or "").strip(),
        allow_cloud_fallback=data.get("allow_cloud_fallback") is True,
        max_history_messages=_as_int(data.get("local_history_messages"), 12, 2, 40),
        vad_silence_ms=_as_int(data.get("local_vad_silence_ms"), 650, 250, 2000),
        vad_min_speech_ms=_as_int(data.get("local_vad_min_speech_ms"), 300, 100, 1500),
        max_tools=_as_int(data.get("local_max_tools"), 0, 0, 64),
        max_tool_schema_chars=_as_int(data.get("local_max_tool_schema_chars"), 0, 0, 64000),
        timings=data.get("local_timings", True) is not False,
    )


def save_local_pipeline_settings(values: dict[str, Any]) -> LocalPipelineSettings:
    """Persist only known keys; never rewrite unrelated owner settings or store secrets in plain text."""
    from memory.config_manager import _patch_config
    from core.security.key_vault import store_provider_key

    # Securely store API key via DPAPI key vault if passed
    raw_key = str(values.get("local_llm_api_key") or "").strip()
    provider = str(values.get("local_llm_provider") or "").strip().lower()
    if not provider:
        provider = local_pipeline_settings().provider
    if raw_key and provider:
        store_provider_key(provider, raw_key)

    allowed = {
        "local_llm_provider", "local_llm_model", "local_llm_base_url",
        "local_stt_provider", "local_stt_model", "local_stt_device", "local_stt_compute",
        "local_stt_language", "local_tts_provider", "local_tts_model", "local_tts_voice_map",
        "local_tts_fallback_voice", "allow_cloud_fallback", "local_history_messages",
        "local_vad_silence_ms", "local_vad_min_speech_ms", "local_max_tools",
        "local_max_tool_schema_chars", "local_timings",
    }
    update = {key: value for key, value in values.items() if key in allowed}
    if update:
        _patch_config(**update)
    return local_pipeline_settings()


def readiness_path() -> Path:
    return _runtime_root() / "local_engine_readiness.json"


def write_readiness(state: dict[str, Any]) -> Path:
    path = readiness_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass
    return path


def provider_settings_schema() -> list[dict[str, Any]]:
    """Declarative settings for the owner UI; no provider-specific page code."""
    sections = []
    for spec in provider_specs():
        sections.append({
            "id": spec.key,
            "label": spec.label,
            "local": spec.local,
            "help": spec.help,
            "fields": spec.settings,
        })
    return sections
