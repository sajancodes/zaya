"""Explicit capability declarations shared by Zaya's conversation engines."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


TOOL_FORMATS = {"gemini", "openai"}


@dataclass(frozen=True)
class EngineCapabilities:
    name: str
    tools: bool = True
    vision: bool = False
    audio_input: bool = True
    audio_output: bool = True
    native_audio: bool = False
    barge_in: bool = True
    reasoning: bool = True
    local: bool = False
    streaming: bool = True
    tool_format: str = "openai"
    context_limit: int = 0
    max_tools: int = 16
    max_tool_schema_chars: int = 18000
    supports_images: bool = False
    supports_phone_audio: bool = False
    extra: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.tool_format not in TOOL_FORMATS:
            raise ValueError(f"Unknown tool format: {self.tool_format}")
        if self.max_tools < 0 or self.max_tool_schema_chars < 0:
            raise ValueError("Tool budgets cannot be negative")

    def supports(self, capability: str) -> bool:
        return bool(getattr(self, capability, False))

    def for_provider(self, *, max_tools: int | None = None,
                     max_tool_schema_chars: int | None = None) -> "EngineCapabilities":
        values = asdict(self)
        values.pop("extra", None)
        if max_tools is not None:
            values["max_tools"] = max(1, int(max_tools))
        if max_tool_schema_chars is not None:
            values["max_tool_schema_chars"] = max(256, int(max_tool_schema_chars))
        values["extra"] = dict(self.extra)
        return EngineCapabilities(**values)


GEMINI_LIVE_CAPABILITIES = EngineCapabilities(
    name="gemini_live",
    tools=True,
    vision=True,
    audio_input=True,
    audio_output=True,
    native_audio=True,
    barge_in=True,
    reasoning=True,
    local=False,
    streaming=True,
    tool_format="gemini",
    context_limit=1_000_000,
    max_tools=64,
    max_tool_schema_chars=64000,
    supports_images=True,
    supports_phone_audio=True,
)


def local_pipeline_capabilities(provider=None) -> EngineCapabilities:
    config = provider
    local = bool(getattr(config, "local", True))
    vision = bool(getattr(config, "capabilities", {}).get("vision", False))
    max_tools = int(getattr(config, "max_tools", 10) or 10)
    max_chars = int(getattr(config, "max_tool_schema_chars", 9000) or 9000)
    return EngineCapabilities(
        name="local_pipeline",
        tools=bool(getattr(config, "capabilities", {}).get("tools", True)),
        # The modular pipeline currently carries text and microphone audio.
        # A provider's own vision flag is not a claim that Zaya forwards image
        # parts through this path, so the engine declaration stays honest.
        vision=False,
        audio_input=True,
        audio_output=True,
        native_audio=False,
        barge_in=True,
        reasoning=True,
        local=local,
        streaming=bool(getattr(config, "capabilities", {}).get("streaming", True)),
        tool_format="openai",
        context_limit=int(getattr(config, "context_limit", 32768) or 32768),
        max_tools=max_tools,
        max_tool_schema_chars=max_chars,
        supports_images=False,
        supports_phone_audio=True,
        extra={"provider_vision": vision},
    )
