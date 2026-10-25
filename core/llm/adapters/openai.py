"""OpenAI, OpenRouter, Groq, DeepSeek, and Compatible adapters."""

from __future__ import annotations

from typing import Dict
from core.llm.adapters.openai_base import OpenAIBaseAdapter


class OpenAIAdapter(OpenAIBaseAdapter):
    def supports_multimodal(self) -> bool:
        return True


class OpenRouterAdapter(OpenAIBaseAdapter):
    def get_headers(self) -> Dict[str, str]:
        headers = super().get_headers()
        headers.setdefault("HTTP-Referer", "https://github.com/sajancodes/zaya")
        headers.setdefault("X-Title", "Zaya")
        return headers

    def supports_multimodal(self) -> bool:
        return True


class GroqAdapter(OpenAIBaseAdapter):
    pass


class DeepSeekAdapter(OpenAIBaseAdapter):
    pass


class CompatibleEndpointAdapter(OpenAIBaseAdapter):
    pass
