"""Backward-compatibility wrapper preserving UniversalLLMRouter API over core.llm.
Created and developed by Sajan Rai for Zaya.
"""

from __future__ import annotations

import json
from typing import Any, Callable, Dict, List, Optional

from core.llm.adapters.openai_base import OpenAIBaseAdapter
from core.llm.registry import ProviderConfig as CoreProviderConfig
from core.llm.router import LLMRouter, get_default_router
from core.llm.types import (
    ImagePart,
    LLMMessage,
    LLMResponse,
    ToolCall,
    ToolDefinition,
)

def ProviderConfig(
    name: str = "",
    provider: str = "",
    provider_type: str = "",
    base_url: str = "",
    api_key: str = "",
    api_keys: Optional[List[str]] = None,
    model: str = "",
    **kwargs
) -> CoreProviderConfig:
    actual_name = name or provider or "custom"
    actual_type = provider_type or provider or actual_name
    keys = api_keys or ([api_key] if api_key else [])
    return CoreProviderConfig(
        name=actual_name,
        provider_type=actual_type,
        base_url=base_url,
        api_keys=keys,
        model=model,
        **kwargs
    )


def _tool_field(tool: Dict[str, Any], key: str, default: Any = "") -> Any:
    """Read a field from a tool schema in either supported shape.

    Tool schemas arrive either flat ({"name": ...}) or wrapped
    ({"function": {"name": ...}}). The old code did
    t.get("function", {}).get("name", "") which raised AttributeError when
    "function" was present but was not an object.
    """
    value = tool.get(key)
    if value not in (None, ""):
        return value
    inner = tool.get("function")
    if isinstance(inner, dict):
        value = inner.get(key)
        if value not in (None, ""):
            return value
    return default


def _tool_definitions(tools: List[Dict[str, Any]]) -> Optional[List[ToolDefinition]]:
    if not tools:
        return None
    defs = [
        ToolDefinition(
            name=_tool_field(t, "name"),
            description=_tool_field(t, "description"),
            parameters=_tool_field(t, "parameters", {}) or {},
        )
        for t in tools if isinstance(t, dict)
    ]
    return defs or None


def normalize_tools_for_openai(tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Converts tools into OpenAI format using OpenAIBaseAdapter formatting."""
    tool_defs = []
    for t in tools:
        if not isinstance(t, dict):
            continue
        if t.get("type") == "function" and "function" in t:
            fn = t["function"]
            tool_defs.append(ToolDefinition(
                name=fn.get("name", ""),
                description=fn.get("description", ""),
                parameters=fn.get("parameters", {})
            ))
        else:
            tool_defs.append(ToolDefinition(
                name=t.get("name", ""),
                description=t.get("description", ""),
                parameters=t.get("parameters", {})
            ))
    adapter = OpenAIBaseAdapter(CoreProviderConfig(name="dummy"))
    return adapter.format_tools(tool_defs)


def parse_tool_calls_from_response(response: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Parses tool calls from an OpenAI-compatible response object or dict."""
    choices = response.get("choices") or []
    if not choices:
        return []
    message = choices[0].get("message") or {}
    adapter = OpenAIBaseAdapter(CoreProviderConfig(name="dummy"))
    tool_calls = adapter.parse_tool_calls(message)
    return [
        {"name": tc.name, "arguments": tc.arguments, "id": tc.id}
        for tc in tool_calls
    ]


class UniversalLLMRouter:
    """Wrapper class preserving legacy interface expected by hybrid branch tools."""

    def __init__(self, logger_fn: Callable[[str], None] = print, router: Optional[LLMRouter] = None):
        self.router = router or LLMRouter(logger_fn=logger_fn)

    def execute_request(
        self,
        config: ProviderConfig,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> Dict[str, Any]:
        """Direct execution against a specific provider config."""
        adapter = self.router.get_adapter(config)
        llm_messages = []
        for m in messages:
            llm_messages.append(LLMMessage(role=m.get("role", "user"), content=m.get("content", "")))

        tool_defs = _tool_definitions(tools)

        res = adapter.chat(
            messages=llm_messages,
            tools=tool_defs,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        return {
            "content": res.content,
            "tool_calls": [
                {"name": tc.name, "arguments": tc.arguments, "id": tc.id}
                for tc in res.tool_calls
            ],
            "provider_used": res.provider,
            "model_used": res.model,
            "raw": res.raw,
        }

    def route_with_fallback(
        self,
        messages: List[Dict[str, Any]],
        chain: Optional[List[ProviderConfig]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        task: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Routes with intelligent fallback using LLMRouter."""
        llm_messages = []
        for m in messages:
            role = m.get("role", "user")
            content = m.get("content", "")
            images = m.get("images", [])
            if images:
                parts: List[Any] = [content]
                for img_b64 in images:
                    parts.append(ImagePart.from_base64(img_b64))
                llm_messages.append(LLMMessage(role=role, content=parts))
            else:
                llm_messages.append(LLMMessage(role=role, content=content))

        tool_defs = _tool_definitions(tools)

        res = self.router.route(
            messages=llm_messages,
            tools=tool_defs,
            task=task,
            candidate_providers=chain,
            **kwargs
        )

        return {
            "content": res.content,
            "tool_calls": [
                {"name": tc.name, "arguments": tc.arguments, "id": tc.id}
                for tc in res.tool_calls
            ],
            "provider_used": res.provider,
            "model_used": res.model,
            "raw": res.raw,
        }
