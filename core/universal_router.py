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

# Re-export ProviderConfig for backward compatibility
ProviderConfig = CoreProviderConfig


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
