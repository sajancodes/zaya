"""Ollama adapter supporting both native /api/chat and OpenAI-compatible /v1 endpoints."""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, Iterator, List, Optional

import requests

from core.llm.adapters.base import BaseAdapter
from core.llm.adapters.openai_base import OpenAIBaseAdapter
from core.llm.types import (
    ImagePart,
    LLMError,
    LLMMessage,
    LLMResponse,
    ProviderUnavailableError,
    StreamChunk,
    TimeoutError,
    ToolCall,
    ToolDefinition,
)

logger = logging.getLogger("core.llm.adapters.ollama")


class OllamaAdapter(BaseAdapter):
    """Adapter for Ollama with clean native /api/chat and /v1 endpoint resolution."""

    def __init__(self, config):
        super().__init__(config)
        self._openai_delegate = OpenAIBaseAdapter(config)

    def is_openai_mode(self) -> bool:
        url = self.config.base_url.lower()
        return "/v1" in url or "completions" in url

    def get_native_url(self) -> str:
        base = self.config.base_url.rstrip("/")
        if base.endswith("/api"):
            return f"{base}/chat"
        elif base.endswith("/api/chat"):
            return base
        return f"{base}/api/chat"

    def format_native_messages(self, messages: List[LLMMessage]) -> List[Dict[str, Any]]:
        formatted = []
        for msg in messages:
            item: Dict[str, Any] = {"role": msg.role}
            images = []
            if isinstance(msg.content, str):
                item["content"] = msg.content
            elif isinstance(msg.content, list):
                text_parts = []
                for p in msg.content:
                    if isinstance(p, str):
                        text_parts.append(p)
                    elif isinstance(p, ImagePart):
                        images.append(p.to_base64())
                item["content"] = "\n".join(text_parts)
            else:
                item["content"] = str(msg.content)

            if images:
                item["images"] = images
            formatted.append(item)
        return formatted

    def format_native_tools(self, tools: List[ToolDefinition]) -> List[Dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters or {"type": "object", "properties": {}},
                }
            }
            for t in tools
        ]

    def chat(
        self,
        messages: List[LLMMessage],
        tools: Optional[List[ToolDefinition]] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        timeout_sec: Optional[float] = None,
        **kwargs
    ) -> LLMResponse:
        if self.is_openai_mode():
            return self._openai_delegate.chat(
                messages, tools=tools, temperature=temperature, max_tokens=max_tokens, timeout_sec=timeout_sec, **kwargs
            )

        # Native /api/chat implementation
        url = self.get_native_url()
        payload: Dict[str, Any] = {
            "model": self.config.model,
            "messages": self.format_native_messages(messages),
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            }
        }
        if tools:
            payload["tools"] = self.format_native_tools(tools)

        timeout = timeout_sec or self.config.timeout_sec
        start_time = time.monotonic()

        try:
            resp = requests.post(url, json=payload, timeout=timeout)
        except requests.exceptions.Timeout as e:
            raise TimeoutError(f"Ollama request timed out after {timeout}s", provider="ollama", raw_error=e)
        except requests.exceptions.ConnectionError as e:
            raise ProviderUnavailableError(
                f"Ollama service is unreachable at {url}. Ensure Ollama is running (`ollama serve`).",
                provider="ollama",
                raw_error=e
            )
        except Exception as e:
            raise LLMError(f"Ollama communication failure: {e}", provider="ollama", raw_error=e)

        latency_ms = (time.monotonic() - start_time) * 1000.0

        if resp.status_code != 200:
            raise self.classify_http_error(resp.status_code, resp.text, dict(resp.headers))

        try:
            data = resp.json()
        except Exception as e:
            raise LLMError(f"Malformed JSON from Ollama: {resp.text[:200]}", provider="ollama", raw_error=e)

        msg = data.get("message", {})
        content = msg.get("content") or ""
        tool_calls = []
        for rc in msg.get("tool_calls", []):
            fn = rc.get("function", {})
            name = fn.get("name", "")
            args = fn.get("arguments", {})
            tool_calls.append(ToolCall(name=name, arguments=args, id=rc.get("id", "")))

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            provider="ollama",
            model=self.config.model,
            finish_reason="stop" if data.get("done") else "length",
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
        if self.is_openai_mode():
            yield from self._openai_delegate.stream_chat(
                messages, tools=tools, temperature=temperature, max_tokens=max_tokens, timeout_sec=timeout_sec, **kwargs
            )
            return

        url = self.get_native_url()
        payload: Dict[str, Any] = {
            "model": self.config.model,
            "messages": self.format_native_messages(messages),
            "stream": True,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            }
        }
        if tools:
            payload["tools"] = self.format_native_tools(tools)

        timeout = timeout_sec or self.config.timeout_sec

        try:
            resp = requests.post(url, json=payload, timeout=timeout, stream=True)
        except requests.exceptions.Timeout as e:
            raise TimeoutError("Ollama streaming timed out", provider="ollama", raw_error=e)
        except requests.exceptions.ConnectionError as e:
            raise ProviderUnavailableError("Ollama service unreachable", provider="ollama", raw_error=e)
        except Exception as e:
            raise LLMError(f"Ollama communication failure: {e}", provider="ollama", raw_error=e)

        try:
            if resp.status_code != 200:
                raise self.classify_http_error(resp.status_code, resp.text, dict(resp.headers))
            for line in resp.iter_lines(decode_unicode=True):
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                except (ValueError, TypeError):
                    continue
                delta_text = chunk.get("message", {}).get("content", "")
                done = chunk.get("done", False)
                calls = []
                for raw_call in chunk.get('message', {}).get('tool_calls') or []:
                    call = raw_call.get('function') or {}
                    args = call.get('arguments') or {}
                    if not isinstance(args, dict):
                        try:
                            args = json.loads(args)
                        except (TypeError, ValueError) as error:
                            raise LLMError('Invalid streamed tool arguments', provider='ollama') from error
                    if not isinstance(args, dict) or not call.get('name'):
                        raise LLMError('Invalid streamed tool call', provider='ollama')
                    calls.append(ToolCall(name=call['name'], arguments=args, id=raw_call.get('id', '')))
                yield StreamChunk(delta_text=delta_text, tool_calls=calls, finish_reason="stop" if done else None)
                if done:
                    break
        except requests.exceptions.Timeout as error:
            raise TimeoutError('Ollama stream timed out', provider='ollama', raw_error=error) from error
        except requests.exceptions.ConnectionError as error:
            raise ProviderUnavailableError('Ollama stream disconnected', provider='ollama', raw_error=error) from error
        except requests.exceptions.RequestException as error:
            raise ProviderUnavailableError('Ollama stream interrupted', provider='ollama', raw_error=error) from error
        finally:
            closer = getattr(resp, "close", None)
            if callable(closer):
                closer()
