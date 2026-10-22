"""Declarative provider catalog.

Adding a compatible endpoint is one entry here. The registry, router, settings
surface and capability checks all read the same declaration, so no provider is
special-cased in the conversation loop.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ProviderSpec:
    key: str
    label: str
    provider_type: str
    base_url: str
    model: str
    local: bool = False
    requires_key: bool = True
    env_key: str = ""
    priority: int = 100
    task_affinity: tuple[str, ...] = ("general",)
    max_tools: int = 16
    max_tool_schema_chars: int = 18000
    supports_streaming: bool = True
    supports_tools: bool = True
    supports_vision: bool = False
    settings_fields: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    help: str = ""

    @property
    def settings(self) -> list[dict[str, Any]]:
        common = [
            {"key": "api_key", "label": "API key", "type": "password",
             "required": self.requires_key, "secret": True},
            {"key": "base_url", "label": "Endpoint", "type": "url",
             "required": not bool(self.base_url), "default": self.base_url},
            {"key": "model", "label": "Model", "type": "text",
             "required": True, "default": self.model},
        ]
        if self.local:
            common[0] = {**common[0], "required": False, "help": "Leave empty for a local server."}
        return [*common, *self.settings_fields]


def _fields(*items: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    return tuple(items)


PROVIDER_SPECS: dict[str, ProviderSpec] = {
    "gemini": ProviderSpec(
        "gemini", "Google Gemini", "gemini",
        "https://generativelanguage.googleapis.com", "gemini-2.5-flash",
        env_key="GEMINI_API_KEY", priority=10,
        task_affinity=("vision", "fast", "multimodal"), max_tools=64,
        max_tool_schema_chars=64000, supports_vision=True,
        help="Gemini's native API; also used by Zaya's preferred live engine.",
    ),
    "openai": ProviderSpec(
        "openai", "OpenAI", "openai", "https://api.openai.com/v1", "gpt-4o-mini",
        env_key="OPENAI_API_KEY", priority=20, task_affinity=("reasoning", "general"),
        max_tools=32, max_tool_schema_chars=32000, supports_vision=True,
    ),
    "openrouter": ProviderSpec(
        "openrouter", "OpenRouter", "openrouter", "https://openrouter.ai/api/v1",
        "google/gemini-2.5-flash", env_key="OPENROUTER_API_KEY", priority=30,
        max_tools=24, max_tool_schema_chars=24000, supports_vision=True,
    ),
    "groq": ProviderSpec(
        "groq", "Groq", "groq", "https://api.groq.com/openai/v1",
        "llama-3.3-70b-versatile", env_key="GROQ_API_KEY", priority=40,
        task_affinity=("fast",), max_tools=16, max_tool_schema_chars=16000,
    ),
    "deepseek": ProviderSpec(
        "deepseek", "DeepSeek", "deepseek", "https://api.deepseek.com/v1",
        "deepseek-chat", env_key="DEEPSEEK_API_KEY", priority=50,
        task_affinity=("code", "reasoning"), max_tools=16, max_tool_schema_chars=16000,
    ),
    "mistral": ProviderSpec(
        "mistral", "Mistral", "mistral", "https://api.mistral.ai/v1",
        "mistral-small-latest", env_key="MISTRAL_API_KEY", priority=55,
        max_tools=16, max_tool_schema_chars=16000,
    ),
    "xai": ProviderSpec(
        "xai", "xAI", "xai", "https://api.x.ai/v1", "grok-3-mini",
        env_key="XAI_API_KEY", priority=56, max_tools=16, max_tool_schema_chars=16000,
    ),
    "together": ProviderSpec(
        "together", "Together", "together", "https://api.together.xyz/v1",
        "meta-llama/Llama-3.3-70B-Instruct-Turbo", env_key="TOGETHER_API_KEY",
        priority=57, max_tools=16, max_tool_schema_chars=16000,
    ),
    "cerebras": ProviderSpec(
        "cerebras", "Cerebras", "cerebras", "https://api.cerebras.ai/v1",
        "llama-3.3-70b", env_key="CEREBRAS_API_KEY", priority=58,
        task_affinity=("fast",), max_tools=12, max_tool_schema_chars=12000,
    ),
    "ollama": ProviderSpec(
        "ollama", "Ollama", "ollama", "http://localhost:11434", "llama3.2",
        local=True, requires_key=False, priority=60,
        task_affinity=("offline", "local"), max_tools=10, max_tool_schema_chars=9000,
        help="Runs on this machine and needs no network.",
    ),
    "lmstudio": ProviderSpec(
        "lmstudio", "LM Studio", "lmstudio", "http://localhost:1234/v1", "local-model",
        local=True, requires_key=False, priority=61,
        task_affinity=("offline", "local"), max_tools=10, max_tool_schema_chars=9000,
    ),
    "llamacpp": ProviderSpec(
        "llamacpp", "llama.cpp server", "llamacpp", "http://localhost:8080/v1", "local-model",
        local=True, requires_key=False, priority=62,
        task_affinity=("offline", "local"), max_tools=10, max_tool_schema_chars=9000,
    ),
    "vllm": ProviderSpec(
        "vllm", "vLLM", "vllm", "http://localhost:8000/v1", "local-model",
        local=True, requires_key=False, priority=63,
        task_affinity=("offline", "local"), max_tools=10, max_tool_schema_chars=9000,
    ),
    "custom": ProviderSpec(
        "custom", "Custom OpenAI-compatible", "compatible", "", "local-model",
        local=False, requires_key=False, priority=90,
        max_tools=12, max_tool_schema_chars=12000,
        help="Any endpoint that implements /v1/chat/completions.",
    ),
}


def provider_spec(name: str) -> ProviderSpec | None:
    return PROVIDER_SPECS.get(str(name or "").strip().lower())


def provider_specs(*, local: bool | None = None) -> list[ProviderSpec]:
    values = list(PROVIDER_SPECS.values())
    if local is not None:
        values = [item for item in values if item.local is local]
    return sorted(values, key=lambda item: (item.local, item.priority, item.key))
