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


DEFAULT_BASE_URLS = {
    "gemini": "https://generativelanguage.googleapis.com",
    "openai": "https://api.openai.com/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "groq": "https://api.groq.com/openai/v1",
    "deepseek": "https://api.deepseek.com/v1",
    "ollama": "http://localhost:11434",
}

DEFAULT_MODELS = {
    "gemini": "gemini-2.5-flash",
    "openai": "gpt-4o-mini",
    "openrouter": "google/gemini-2.5-flash",
    "groq": "llama-3.3-70b-versatile",
    "deepseek": "deepseek-chat",
    "ollama": "llama3.2",
}


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

    def __post_init__(self):
        if not self.provider_type:
            self.provider_type = self.name.lower()
        if not self.base_url:
            self.base_url = DEFAULT_BASE_URLS.get(self.provider_type, "")
        if not self.model:
            self.model = DEFAULT_MODELS.get(self.provider_type, "")

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
            raw_fallbacks = ["gemini", "openai", "openrouter", "groq", "deepseek", "ollama"]
        self.fallback_chain = [
            str(p).strip().lower() for p in raw_fallbacks if str(p).strip()
        ]

        from core.security.key_vault import decrypt_secret
        enc_map = data.get("encrypted_keys", {}) if isinstance(data.get("encrypted_keys"), dict) else {}

        # 1. Gemini
        gemini_keys = []
        raw_keys = enc_map.get("gemini") or data.get("gemini_api_keys") or data.get("gemini_api_key") or data.get("api_key") or os.environ.get("GEMINI_API_KEY", "")
        if isinstance(raw_keys, list):
            gemini_keys = [decrypt_secret(str(k)).strip() for k in raw_keys if str(k).strip()]
        elif isinstance(raw_keys, str) and raw_keys.strip():
            gemini_keys = [decrypt_secret(k).strip() for k in raw_keys.replace("\n", ",").split(",") if k.strip()]

        self.register(ProviderConfig(
            name="gemini",
            provider_type="gemini",
            base_url=_text(data.get("gemini_base_url"), DEFAULT_BASE_URLS["gemini"]),
            api_keys=gemini_keys,
            model=_text(data.get("gemini_model") or data.get("model_name"), DEFAULT_MODELS["gemini"]),
            priority=10,
            task_affinity=["vision", "fast", "multimodal"]
        ))

        # 2. OpenAI
        openai_key = enc_map.get("openai") or data.get("openai_api_key") or data.get("openai_key") or os.environ.get("OPENAI_API_KEY", "")
        openai_keys = [decrypt_secret(str(openai_key)).strip()] if isinstance(openai_key, str) and openai_key.strip() else []
        self.register(ProviderConfig(
            name="openai",
            provider_type="openai",
            base_url=_text(data.get("openai_base_url"), DEFAULT_BASE_URLS["openai"]),
            api_keys=openai_keys,
            model=_text(data.get("openai_model"), DEFAULT_MODELS["openai"]),
            priority=20,
            task_affinity=["reasoning", "general"]
        ))

        # 3. OpenRouter
        or_key = data.get("openrouter_api_key") or data.get("openrouter_key") or os.environ.get("OPENROUTER_API_KEY", "")
        or_keys = [or_key] if isinstance(or_key, str) and or_key.strip() else []
        self.register(ProviderConfig(
            name="openrouter",
            provider_type="openrouter",
            base_url=_text(data.get("openrouter_base_url"), DEFAULT_BASE_URLS["openrouter"]),
            api_keys=or_keys,
            model=_text(data.get("openrouter_model"), DEFAULT_MODELS["openrouter"]),
            priority=30,
            headers={"HTTP-Referer": "https://github.com/sajancodes/zaya", "X-Title": "Zaya"},
            task_affinity=["general"]
        ))

        # 4. Groq
        groq_key = data.get("groq_api_key") or os.environ.get("GROQ_API_KEY", "")
        groq_keys = [groq_key] if isinstance(groq_key, str) and groq_key.strip() else []
        self.register(ProviderConfig(
            name="groq",
            provider_type="groq",
            base_url=_text(data.get("groq_base_url"), DEFAULT_BASE_URLS["groq"]),
            api_keys=groq_keys,
            model=_text(data.get("groq_model"), DEFAULT_MODELS["groq"]),
            priority=40,
            task_affinity=["fast"]
        ))

        # 5. DeepSeek
        deepseek_key = data.get("deepseek_api_key") or os.environ.get("DEEPSEEK_API_KEY", "")
        deepseek_keys = [deepseek_key] if isinstance(deepseek_key, str) and deepseek_key.strip() else []
        self.register(ProviderConfig(
            name="deepseek",
            provider_type="deepseek",
            base_url=_text(data.get("deepseek_base_url"), DEFAULT_BASE_URLS["deepseek"]),
            api_keys=deepseek_keys,
            model=_text(data.get("deepseek_model"), DEFAULT_MODELS["deepseek"]),
            priority=50,
            task_affinity=["code", "reasoning"]
        ))

        # 6. Ollama
        self.register(ProviderConfig(
            name="ollama",
            provider_type="ollama",
            base_url=data.get("ollama_base_url") or DEFAULT_BASE_URLS["ollama"],
            model=data.get("ollama_model") or DEFAULT_MODELS["ollama"],
            priority=60,
            task_affinity=["offline", "local"]
        ))
