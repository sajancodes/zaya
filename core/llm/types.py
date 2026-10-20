"""Type definitions and exception hierarchy for Zaya LLM Router."""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Union


# --- Exception Hierarchy ---

class LLMError(Exception):
    """Base exception for all LLM router errors."""
    def __init__(self, message: str, provider: str = "", model: str = "", raw_error: Optional[Any] = None):
        super().__init__(message)
        self.message = message
        self.provider = provider
        self.model = model
        self.raw_error = raw_error

    def __str__(self) -> str:
        ctx = []
        if self.provider:
            ctx.append(f"provider={self.provider}")
        if self.model:
            ctx.append(f"model={self.model}")
        prefix = f"[{', '.join(ctx)}] " if ctx else ""
        return f"{prefix}{self.message}"


class RecoverableError(LLMError):
    """Errors that indicate a temporary or failover-eligible condition."""
    pass


class RateLimitError(RecoverableError):
    """429 Too Many Requests or RESOURCE_EXHAUSTED."""
    def __init__(self, message: str, retry_after: float = 60.0, **kwargs):
        super().__init__(message, **kwargs)
        self.retry_after = retry_after


class ProviderUnavailableError(RecoverableError):
    """5xx Server Error, connection refused, or unreachable host."""
    pass


class TimeoutError(RecoverableError):
    """Request timed out."""
    pass


class QuotaExhaustedError(RecoverableError):
    """Account out of credits or daily quota exceeded."""
    pass


class AuthenticationError(RecoverableError):
    """401/403 or invalid API key (eligible for key rotation or next provider)."""
    pass


class ModelNotFoundError(RecoverableError):
    """Specified model name does not exist on this provider."""
    pass


class InvalidRequestError(LLMError):
    """400 Bad Request, malformed JSON, or schema error (NOT recoverable via fallback)."""
    pass


class SchemaError(InvalidRequestError):
    """Tool schema or payload generation failed validation."""
    pass


# --- Data Models ---

@dataclass
class ImagePart:
    """Represents an image for multimodal input."""
    data: bytes
    mime_type: str = "image/png"

    @classmethod
    def from_base64(cls, b64_str: str, mime_type: str = "image/png") -> ImagePart:
        if "," in b64_str:
            b64_str = b64_str.split(",", 1)[1]
        return cls(data=base64.b64decode(b64_str), mime_type=mime_type)

    def to_base64(self) -> str:
        return base64.b64encode(self.data).decode("utf-8")

    def to_data_uri(self) -> str:
        return f"data:{self.mime_type};base64,{self.to_base64()}"


@dataclass
class ToolCall:
    """Represents a model tool/function call."""
    name: str
    arguments: Dict[str, Any]
    id: str = ""


@dataclass
class ToolDefinition:
    """Represents a tool schema callable by the model."""
    name: str
    description: str
    parameters: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LLMMessage:
    """Unified message structure."""
    role: str  # "system", "user", "assistant", "tool"
    content: Union[str, List[Union[str, ImagePart]]]
    name: Optional[str] = None
    tool_call_id: Optional[str] = None
    tool_calls: Optional[List[ToolCall]] = None

    @classmethod
    def user(cls, text: str, image: Optional[ImagePart] = None) -> LLMMessage:
        if image is not None:
            return cls(role="user", content=[text, image])
        return cls(role="user", content=text)

    @classmethod
    def system(cls, text: str) -> LLMMessage:
        return cls(role="system", content=text)

    @classmethod
    def assistant(cls, text: str, tool_calls: Optional[List[ToolCall]] = None) -> LLMMessage:
        return cls(role="assistant", content=text, tool_calls=tool_calls)

    @classmethod
    def tool_result(cls, tool_call_id: str, content: str, name: Optional[str] = None) -> LLMMessage:
        return cls(role="tool", content=content, tool_call_id=tool_call_id, name=name)


@dataclass
class LLMResponse:
    """Unified response structure."""
    content: str
    tool_calls: List[ToolCall] = field(default_factory=list)
    provider: str = ""
    model: str = ""
    finish_reason: str = "stop"
    usage: Dict[str, int] = field(default_factory=dict)
    raw: Any = None
    latency_ms: float = 0.0


@dataclass
class StreamChunk:
    """Incremental chunk for streaming responses."""
    delta_text: str = ""
    tool_calls: List[ToolCall] = field(default_factory=list)
    finish_reason: Optional[str] = None
