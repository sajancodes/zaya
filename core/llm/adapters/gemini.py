"""Native Gemini REST adapter with KeyPool rotation and multimodal support."""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, Iterator, List, Optional

import requests

from core.llm.adapters.base import BaseAdapter
from core.llm.types import (
    AuthenticationError,
    ImagePart,
    InvalidRequestError,
    LLMError,
    LLMMessage,
    LLMResponse,
    ProviderUnavailableError,
    RateLimitError,
    StreamChunk,
    TimeoutError,
    ToolCall,
    ToolDefinition,
)

logger = logging.getLogger("core.llm.adapters.gemini")


class GeminiAdapter(BaseAdapter):
    """Native Gemini REST adapter supporting function calling and multimodal vision."""

    def supports_multimodal(self) -> bool:
        return True

    def get_api_key(self) -> str:
        # Check if core.gemini_keys pool is available
        try:
            from core.gemini_keys import pool
            key = pool.select(resource="text")
            if key:
                return key
        except Exception:
            pass
        return self.config.api_key

    def format_contents(self, messages: List[LLMMessage]) -> tuple[Optional[Dict[str, Any]], List[Dict[str, Any]]]:
        system_instruction = None
        contents = []

        for msg in messages:
            if msg.role == "system":
                system_instruction = {
                    "parts": [{"text": str(msg.content)}]
                }
                continue

            role = "user" if msg.role == "user" else "model"
            parts: List[Dict[str, Any]] = []

            if isinstance(msg.content, str):
                parts.append({"text": msg.content})
            elif isinstance(msg.content, list):
                for p in msg.content:
                    if isinstance(p, str):
                        parts.append({"text": p})
                    elif isinstance(p, ImagePart):
                        parts.append({
                            "inlineData": {
                                "mimeType": p.mime_type,
                                "data": p.to_base64()
                            }
                        })
            elif msg.role == "tool":
                role = "user"
                parts.append({
                    "functionResponse": {
                        "name": msg.name or "tool_result",
                        "response": {"output": str(msg.content)}
                    }
                })

            if msg.tool_calls:
                for tc in msg.tool_calls:
                    parts.append({
                        "functionCall": {
                            "name": tc.name,
                            "args": tc.arguments
                        }
                    })

            if parts:
                contents.append({"role": role, "parts": parts})

        return system_instruction, contents

    def format_tools(self, tools: List[ToolDefinition]) -> List[Dict[str, Any]]:
        decls = []
        for t in tools:
            params = t.parameters or {"type": "object", "properties": {}}
            decls.append({
                "name": t.name,
                "description": t.description,
                "parameters": params
            })
        return [{"functionDeclarations": decls}]

    def chat(
        self,
        messages: List[LLMMessage],
        tools: Optional[List[ToolDefinition]] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        timeout_sec: Optional[float] = None,
        **kwargs
    ) -> LLMResponse:
        key = self.get_api_key()
        if not key:
            raise AuthenticationError("No Gemini API key available", provider="gemini", model=self.config.model)

        model = self.config.model or "gemini-2.5-flash"
        base = self.config.base_url.rstrip("/")
        url = f"{base}/v1beta/models/{model}:generateContent?key={key}"

        system_instruction, contents = self.format_contents(messages)

        payload: Dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            }
        }
        if system_instruction:
            payload["systemInstruction"] = system_instruction
        if tools:
            payload["tools"] = self.format_tools(tools)

        timeout = timeout_sec or self.config.timeout_sec
        start_time = time.monotonic()

        try:
            resp = requests.post(url, json=payload, timeout=timeout)
        except requests.exceptions.Timeout as e:
            raise TimeoutError(f"Gemini request timed out after {timeout}s", provider="gemini", raw_error=e)
        except requests.exceptions.ConnectionError as e:
            raise ProviderUnavailableError(f"Connection to Gemini failed: {e}", provider="gemini", raw_error=e)
        except Exception as e:
            raise LLMError(f"Gemini error: {e}", provider="gemini", raw_error=e)

        latency_ms = (time.monotonic() - start_time) * 1000.0

        if resp.status_code != 200:
            # Report quota or permission failures to key pool
            try:
                from core.gemini_keys import pool
                pool.limited(key, resp.text, resource="text")
            except Exception:
                pass
            raise self.classify_http_error(resp.status_code, resp.text, dict(resp.headers))

        try:
            data = resp.json()
        except Exception as e:
            raise LLMError(f"Malformed JSON from Gemini: {resp.text[:200]}", provider="gemini", raw_error=e)

        candidates = data.get("candidates", [])
        if not candidates:
            return LLMResponse(content="", provider="gemini", model=model, latency_ms=latency_ms, raw=data)

        first = candidates[0]
        content_obj = first.get("content", {})
        parts = content_obj.get("parts", [])

        content_texts = []
        tool_calls = []

        for p in parts:
            if "text" in p:
                content_texts.append(p["text"])
            elif "functionCall" in p:
                fc = p["functionCall"]
                name = fc.get("name", "")
                args = fc.get("args", {})
                tool_calls.append(ToolCall(name=name, arguments=args))

        finish_reason = first.get("finishReason", "STOP")
        usage = data.get("usageMetadata", {})

        return LLMResponse(
            content="".join(content_texts),
            tool_calls=tool_calls,
            provider="gemini",
            model=model,
            finish_reason=finish_reason,
            usage=usage,
            raw=data,
            latency_ms=latency_ms,
        )

    def stream_chat(
        self,
        messages: List[LLMMessage],
        tools: Optional[List[ToolDefinition]] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        timeout_sec: Optional[float] = None,
        **kwargs
    ) -> Iterator[StreamChunk]:
        # Gemini SSE stream support via :streamGenerateContent?alt=sse
        key = self.get_api_key()
        if not key:
            raise AuthenticationError("No Gemini API key available", provider="gemini")

        model = self.config.model or "gemini-2.5-flash"
        base = self.config.base_url.rstrip("/")
        url = f"{base}/v1beta/models/{model}:streamGenerateContent?key={key}&alt=sse"

        system_instruction, contents = self.format_contents(messages)
        payload: Dict[str, Any] = {
            "contents": contents,
            "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens}
        }
        if system_instruction:
            payload["systemInstruction"] = system_instruction
        if tools:
            payload["tools"] = self.format_tools(tools)

        timeout = timeout_sec or self.config.timeout_sec
        try:
            resp = requests.post(url, json=payload, timeout=timeout, stream=True)
        except requests.exceptions.Timeout as e:
            raise TimeoutError("Gemini streaming timed out", provider="gemini", raw_error=e)
        except requests.exceptions.ConnectionError as e:
            raise ProviderUnavailableError("Gemini connection failed", provider="gemini", raw_error=e)

        if resp.status_code != 200:
            raise self.classify_http_error(resp.status_code, resp.text, dict(resp.headers))

        for line in resp.iter_lines(decode_unicode=True):
            if not line:
                continue
            if isinstance(line, bytes):
                line = line.decode("utf-8", errors="replace")
            line = line.strip()
            if line.startswith("data: "):
                raw = line[6:].strip()
                try:
                    chunk = json.loads(raw)
                    cands = chunk.get("candidates", [])
                    if cands:
                        parts = cands[0].get("content", {}).get("parts", [])
                        for p in parts:
                            if "text" in p:
                                yield StreamChunk(delta_text=p["text"])
                except Exception:
                    continue
