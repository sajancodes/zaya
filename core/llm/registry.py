"""Provider configuration and registry management."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


def _text(value: Any, default: str) -> str:
    """Return a non-empty string setting, or the default.

    Owner-edited config files can hold null or a number where a string
    belongs; passing those straight through produced a ProviderConfig with
    base_url=123, which blew up later in .rstrip("/").
    """
    if isinstance(value, str) and value.strip():
        return value.strip()
    return default


def _default_config_path() -> Path:
    """Absolute path to the app's own api_keys.json."""
    try:
        from core.runtime_paths import get_config_dir
        cfg = get_config_dir() / "api_keys.json"
        if cfg.is_file():
            return cfg
    except Exception:
        pass
    project_root = Path(__file__).resolve().parent.parent.parent
    return project_root / "config" / "api_keys.json"


from core.providers.catalog import PROVIDER_SPECS, provider_spec

DEFAULT_BASE_URLS = {key: spec.base_url for key, spec in PROVIDER_SPECS.items()}
DEFAULT_MODELS = {key: spec.model for key, spec in PROVIDER_SPECS.items()}


@dataclass
class ProviderConfig:
    name: str
    provider_type: str = ""  # gemini, openai, openrouter, groq, deepseek, ollama, compatible
    base_url: str = ""
    api_keys: List[str] = field(default_factory=list)
    model: str = ""
    timeout_sec: float = 30.0
    headers: Dict[str, str] = field(default_factory=dict)
    priority: int = 100
    task_affinity: List[str] = field(default_factory=list)  # e.g. ["fast", "vision", "reasoning", "code"]
    active_key_index: int = 0
    label: str = ""
    local: bool = False
    requires_key: bool = True
    capabilities: Dict[str, Any] = field(default_factory=dict)
    max_tools: int = 16
    max_tool_schema_chars: int = 18000
    settings_fields: List[Dict[str, Any]] = field(default_factory=list)

    def __post_init__(self):
        if not self.provider_type:
            self.provider_type = self.name.lower()
        spec = provider_spec(self.name) or provider_spec(self.provider_type)
        if spec is not None:
            if not self.base_url:
                self.base_url = spec.base_url
            if not self.model:
                self.model = spec.model
            if not self.label:
                self.label = spec.label
            self.local = bool(self.local or spec.local)
            self.requires_key = bool(self.requires_key and spec.requires_key)
            if not self.task_affinity:
                self.task_affinity = list(spec.task_affinity)
            if self.max_tools == 16:
                self.max_tools = spec.max_tools
            if self.max_tool_schema_chars == 18000:
                self.max_tool_schema_chars = spec.max_tool_schema_chars
            if not self.capabilities:
                self.capabilities = {
                    "tools": spec.supports_tools,
                    "vision": spec.supports_vision,
                    "streaming": spec.supports_streaming,
                    "local": spec.local,
                }
            if not self.settings_fields:
                self.settings_fields = spec.settings
        if not self.base_url:
            self.base_url = DEFAULT_BASE_URLS.get(self.provider_type, "")
        if not self.model:
            self.model = DEFAULT_MODELS.get(self.provider_type, "")
        if not self.label:
            self.label = self.name

    @property
    def configured(self) -> bool:
        if self.local and not self.requires_key:
            return bool(self.base_url or self.provider_type == "ollama")
        return bool(self.api_key) and bool(self.base_url)

    @property
    def api_key(self) -> str:
        if not self.api_keys:
            return ""
        return self.api_keys[self.active_key_index % len(self.api_keys)]

    def rotate_key(self) -> str:
        if len(self.api_keys) > 1:
            self.active_key_index = (self.active_key_index + 1) % len(self.api_keys)
        return self.api_key


class ProviderRegistry:
    """Stores and discovers configured LLM providers."""

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = Path(config_path) if config_path else _default_config_path()
        self.providers: Dict[str, ProviderConfig] = {}
        self.primary_provider: str = "gemini"
        self.fallback_chain: List[str] = []
        self.allow_cloud_fallback: bool = True

    def register(self, config: ProviderConfig) -> None:
        self.providers[config.name] = config

    def get(self, name: str) -> Optional[ProviderConfig]:
        return self.providers.get(name)

    def load_from_config(self) -> None:
        """Reads config/api_keys.json and environment variables to populate registry."""
        data: Dict[str, Any] = {}
        if self.config_path.exists():
            try:
                loaded = json.loads(self.config_path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    data = loaded
            except Exception:
                data = {}

        # Every field below is optional in the owner's config file, and a
        # hand-edited file can hold null or the wrong type. Reading them
        # blind ("data.get(k, default).strip()") raised AttributeError on a
        # null value and TypeError when a list field held a string.
        primary = data.get("llm_provider")
        self.primary_provider = (
            str(primary).strip().lower()
            if isinstance(primary, str) and primary.strip()
            else "gemini"
        )

        raw_fallbacks = data.get("fallback_providers")
        if isinstance(raw_fallbacks, str):
            raw_fallbacks = re.split(r"[,\s]+", raw_fallbacks)
        elif not isinstance(raw_fallbacks, (list, tuple)):
            raw_fallbacks = [key for key in PROVIDER_SPECS if key != "custom"]
        self.fallback_chain = [
            str(p).strip().lower() for p in raw_fallbacks if str(p).strip()
        ]

        from core.security.key_vault import decrypt_secret
        enc_map = data.get("encrypted_keys", {}) if isinstance(data.get("encrypted_keys"), dict) else {}
        engine_mode = str(data.get("engine_mode") or "gemini_live").strip().lower()
        raw_cloud = data.get("allow_cloud_fallback")
        self.allow_cloud_fallback = (
            bool(raw_cloud) if isinstance(raw_cloud, bool)
            else engine_mode not in {"local", "local_pipeline", "offline"}
        )

        def _key_values(provider: str) -> list[str]:
            raw = (enc_map.get(provider) if isinstance(enc_map, dict) else None)
            if raw in (None, ""):
                raw = (data.get(f"{provider}_api_keys")
                       or data.get(f"{provider}_api_key")
                       or data.get(f"{provider}_key")
                       or os.environ.get((provider_spec(provider).env_key if provider_spec(provider) else ""), ""))
            if isinstance(raw, (list, tuple)):
                values = [str(item).strip() for item in raw if str(item).strip()]
            elif isinstance(raw, str) and raw.strip():
                values = [item.strip() for item in re.split(r"[\n,]+", raw) if item.strip()]
            else:
                values = []
            values = [decrypt_secret(item).strip() for item in values if item.strip()]
            if provider == "gemini" and not values:
                legacy = data.get("api_key") or os.environ.get("GEMINI_API_KEY", "")
                if isinstance(legacy, str) and legacy.strip():
                    values = [decrypt_secret(legacy.strip())]
            return values

        for key, spec in PROVIDER_SPECS.items():
            if key == "custom":
                continue
            keys = _key_values(key)
            base = _text(data.get(f"{key}_base_url"), spec.base_url)
            model = _text(data.get(f"{key}_model"), spec.model)
            if key == "gemini":
                model = _text(data.get("gemini_model") or data.get("model_name"), spec.model)
            headers = {"HTTP-Referer": "https://github.com/sajancodes/zaya", "X-Title": "Zaya"} if key == "openrouter" else {}
            self.register(ProviderConfig(
                name=key,
                provider_type=spec.provider_type,
                base_url=base,
                api_keys=keys,
                model=model,
                priority=spec.priority,
                task_affinity=list(spec.task_affinity),
                headers=headers,
                local=spec.local,
                requires_key=spec.requires_key,
                max_tools=spec.max_tools,
                max_tool_schema_chars=spec.max_tool_schema_chars,
            ))

        custom_base = _text(data.get("custom_base_url"), "")
        custom_keys = _key_values("custom")
        if custom_base:
            self.register(ProviderConfig(
                name="custom",
                provider_type="compatible",
                base_url=custom_base,
                api_keys=custom_keys,
                model=_text(data.get("custom_model"), "local-model"),
                priority=90,
                task_affinity=["general"],
                local=bool(data.get("custom_local", False)),
                requires_key=False,
                max_tools=12,
                max_tool_schema_chars=12000,
            ))

        if not self.fallback_chain:
            self.fallback_chain = [key for key in PROVIDER_SPECS if key != "custom"]
