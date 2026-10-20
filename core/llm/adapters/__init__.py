"""Adapter exports."""

from core.llm.adapters.base import BaseAdapter
from core.llm.adapters.openai_base import OpenAIBaseAdapter
from core.llm.adapters.openai import (
    OpenAIAdapter,
    OpenRouterAdapter,
    GroqAdapter,
    DeepSeekAdapter,
    CompatibleEndpointAdapter,
)
from core.llm.adapters.gemini import GeminiAdapter
from core.llm.adapters.ollama import OllamaAdapter

ADAPTER_MAP = {
    "gemini": GeminiAdapter,
    "openai": OpenAIAdapter,
    "openrouter": OpenRouterAdapter,
    "groq": GroqAdapter,
    "deepseek": DeepSeekAdapter,
    "ollama": OllamaAdapter,
    "compatible": CompatibleEndpointAdapter,
}

__all__ = [
    "BaseAdapter",
    "OpenAIBaseAdapter",
    "OpenAIAdapter",
    "OpenRouterAdapter",
    "GroqAdapter",
    "DeepSeekAdapter",
    "CompatibleEndpointAdapter",
    "GeminiAdapter",
    "OllamaAdapter",
    "ADAPTER_MAP",
]
