"""Base adapter interface for LLM providers."""

from __future__ import annotations

import abc
import time
from typing import Any, Dict, Iterator, List, Optional

from core.llm.registry import ProviderConfig
from core.llm.types import (
    AuthenticationError,
    ImagePart,
    InvalidRequestError,
    LLMError,
    LLMMessage,
    LLMResponse,
    ProviderUnavailableError,
    RateLimitError,
    RecoverableError,
    StreamChunk,
    TimeoutError,
    ToolCall,
    ToolDefinition,
)


class BaseAdapter(abc.ABC):
    """Abstract base class for all LLM provider adapters."""

    def __init__(self, config: ProviderConfig):
        self.config = config

    @abc.abstractmethod
    def chat(
        self,
        messages: List[LLMMessage],
        tools: Optional[List[ToolDefinition]] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        timeout_sec: Optional[float] = None,
        **kwargs
    ) -> LLMResponse:
        """Executes a non-streaming chat completion request."""
        pass

    @abc.abstractmethod
    def stream_chat(
        self,
        messages: List[LLMMessage],
        tools: Optional[List[ToolDefinition]] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        timeout_sec: Optional[float] = None,
        **kwargs
    ) -> Iterator[StreamChunk]:
        """Executes a streaming chat completion request."""
        pass

    def supports_multimodal(self) -> bool:
        return False

    def supports_tools(self) -> bool:
        return True

    def classify_http_error(self, status_code: int, response_text: str, headers: Optional[Dict[str, str]] = None) -> LLMError:
        """Converts HTTP error into structured LLM exception."""
        headers = headers or {}
        low_text = response_text.lower()
        retry_after = 60.0
        if "retry-after" in headers:
            try:
                retry_after = float(headers["retry-after"])
            except (ValueError, TypeError):
                pass

        if status_code == 429 or "resource_exhausted" in low_text or "rate limit" in low_text:
            return RateLimitError(
                f"Rate limit exceeded (HTTP 429): {response_text[:300]}",
                retry_after=retry_after,
                provider=self.config.name,
                model=self.config.model,
            )
        elif status_code in (401, 403) or "unauthorized" in low_text or "permission_denied" in low_text:
            return AuthenticationError(
                f"Authentication error (HTTP {status_code}): {response_text[:300]}",
                provider=self.config.name,
                model=self.config.model,
            )
        elif status_code in (500, 502, 503, 504):
            return ProviderUnavailableError(
                f"Provider server error (HTTP {status_code}): {response_text[:300]}",
                provider=self.config.name,
                model=self.config.model,
            )
        elif status_code == 400:
            # 400 indicates client bug, invalid schema, or malformed payload
            return InvalidRequestError(
                f"Invalid request (HTTP 400): {response_text[:300]}",
                provider=self.config.name,
                model=self.config.model,
            )
        return LLMError(
            f"Provider error (HTTP {status_code}): {response_text[:300]}",
            provider=self.config.name,
            model=self.config.model,
        )
