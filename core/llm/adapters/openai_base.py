"""OpenAI-compatible base adapter."""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, Iterator, List, Optional

import requests

from core.llm.adapters.base import BaseAdapter
from core.llm.registry import ProviderConfig
from core.llm.types import (
    ImagePart,
    InvalidRequestError,
    LLMError,
    LLMMessage,
    LLMResponse,
    ProviderUnavailableError,
    RecoverableError,
    StreamChunk,
    TimeoutError,
    ToolCall,
    ToolDefinition,
)

logger = logging.getLogger("core.llm.adapters.openai_base")


class OpenAIBaseAdapter(BaseAdapter):
    """Adapter for endpoints following OpenAI /v1/chat/completions specification."""

    def get_chat_url(self) -> str:
        base = self.config.base_url.rstrip("/")
        if not base.endswith("/chat/completions"):
            return f"{base}/chat/completions"
        return base

    def get_headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            **self.config.headers,
        }
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        return headers

    def format_messages(self, messages: List[LLMMessage]) -> List[Dict[str, Any]]:
        formatted = []
        for msg in messages:
            item: Dict[str, Any] = {"role": msg.role}
            if msg.name:
                item["name"] = msg.name
            if msg.tool_call_id:
                item["tool_call_id"] = msg.tool_call_id

            if isinstance(msg.content, str):
                item["content"] = msg.content
            elif isinstance(msg.content, list):
                # Multimodal content parts
                parts = []
                for p in msg.content:
                    if isinstance(p, str):
                        parts.append({"type": "text", "text": p})
                    elif isinstance(p, ImagePart):
                        parts.append({
                            "type": "image_url",
                            "image_url": {"url": p.to_data_uri()}
                        })
                item["content"] = parts
            else:
                item["content"] = str(msg.content)

            if msg.tool_calls:
                item["tool_calls"] = [
                    {
                        "id": tc.id or f"call_{i}",
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments) if isinstance(tc.arguments, dict) else str(tc.arguments)
                        }
                    }
                    for i, tc in enumerate(msg.tool_calls)
                ]
            formatted.append(item)
        return formatted

    def format_tools(self, tools: List[ToolDefinition]) -> List[Dict[str, Any]]:
        formatted = []
        for t in tools:
            params = t.parameters or {"type": "object", "properties": {}}
            # Ensure type: "object"
            if isinstance(params, dict) and "type" not in params:
                params = {"type": "object", **params}
            formatted.append({
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": params,
                }
            })
        return formatted

    def parse_tool_calls(self, message: Dict[str, Any]) -> List[ToolCall]:
        calls = []
        raw_calls = message.get("tool_calls", [])
        for rc in raw_calls:
            fn = rc.get("function", {})
            name = fn.get("name", "")
            raw_args = fn.get("arguments", "{}")
            if isinstance(raw_args, str):
                try:
                    args = json.loads(raw_args)
                except Exception:
                    args = {"raw": raw_args}
            elif isinstance(raw_args, dict):
                args = raw_args
            else:
                args = {}
            calls.append(ToolCall(name=name, arguments=args, id=rc.get("id", "")))
        return calls

    def chat(
        self,
        messages: List[LLMMessage],
        tools: Optional[List[ToolDefinition]] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        timeout_sec: Optional[float] = None,
        **kwargs
    ) -> LLMResponse:
        url = self.get_chat_url()
        headers = self.get_headers()
        payload: Dict[str, Any] = {
            "model": self.config.model,
            "messages": self.format_messages(messages),
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            payload["tools"] = self.format_tools(tools)
            payload["tool_choice"] = kwargs.get("tool_choice", "auto")

        timeout = timeout_sec or self.config.timeout_sec
        start_time = time.monotonic()

        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
        except requests.exceptions.Timeout as e:
            raise TimeoutError(f"Request to {self.config.name} timed out after {timeout}s", provider=self.config.name, raw_error=e)
        except requests.exceptions.ConnectionError as e:
            raise ProviderUnavailableError(f"Connection to {self.config.name} failed: {e}", provider=self.config.name, raw_error=e)
        except Exception as e:
            raise LLMError(f"Unexpected network error communicating with {self.config.name}: {e}", provider=self.config.name, raw_error=e)

        latency_ms = (time.monotonic() - start_time) * 1000.0

        if resp.status_code != 200:
            raise self.classify_http_error(resp.status_code, resp.text, dict(resp.headers))

        try:
            data = resp.json()
        except Exception as e:
            raise LLMError(f"Malformed JSON response from {self.config.name}: {resp.text[:200]}", provider=self.config.name, raw_error=e)

        choices = data.get("choices", [])
        if not choices:
            return LLMResponse(content="", provider=self.config.name, model=self.config.model, latency_ms=latency_ms, raw=data)

        first_choice = choices[0]
        msg = first_choice.get("message", {})
        content = msg.get("content") or ""
        tool_calls = self.parse_tool_calls(msg)
        finish_reason = first_choice.get("finish_reason") or "stop"
        usage = data.get("usage", {})

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            provider=self.config.name,
            model=self.config.model,
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
        url = self.get_chat_url()
        headers = self.get_headers()
        payload: Dict[str, Any] = {
            "model": self.config.model,
            "messages": self.format_messages(messages),
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        if tools:
            payload["tools"] = self.format_tools(tools)
            payload["tool_choice"] = kwargs.get("tool_choice", "auto")

        timeout = timeout_sec or self.config.timeout_sec

        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=timeout, stream=True)
        except requests.exceptions.Timeout as e:
            raise TimeoutError(f"Streaming request to {self.config.name} timed out", provider=self.config.name, raw_error=e)
        except requests.exceptions.ConnectionError as e:
            raise ProviderUnavailableError(f"Streaming connection to {self.config.name} failed: {e}", provider=self.config.name, raw_error=e)
        except Exception as e:
            # The non-streaming path wraps everything else in LLMError; the
            # streaming path used to let raw requests exceptions escape, so
            # the router's error handling never saw them.
            raise LLMError(f"Unexpected network error communicating with {self.config.name}: {e}", provider=self.config.name, raw_error=e)

        pending = {}
        def take_calls():
            calls = []
            for index in sorted(pending):
                value = pending[index]
                try:
                    arguments = json.loads(value['arguments'] or '{}')
                except ValueError as error:
                    raise InvalidRequestError('Incomplete streamed tool arguments', provider=self.config.name) from error
                if not value['name'] or not isinstance(arguments, dict):
                    raise InvalidRequestError('Invalid streamed tool call', provider=self.config.name)
                calls.append(ToolCall(name=value['name'], arguments=arguments, id=value['id']))
            pending.clear()
            return calls

        try:
            if resp.status_code != 200:
                raise self.classify_http_error(resp.status_code, resp.text, dict(resp.headers))
            for line in resp.iter_lines(decode_unicode=True):
                if not line:
                    continue
                if isinstance(line, bytes):
                    line = line.decode("utf-8", errors="replace")
                line = line.strip()
                if line.startswith("data: "):
                    raw_data = line[6:].strip()
                    if raw_data == "[DONE]":
                        break
                    try:
                        chunk_json = json.loads(raw_data)
                    except (ValueError, TypeError):
                        continue
                    choices = chunk_json.get("choices", [])
                    if choices:
                        delta = choices[0].get("delta", {})
                        delta_text = delta.get("content") or ""
                        finish_reason = choices[0].get("finish_reason")
                        for part in delta.get('tool_calls') or []:
                            value = pending.setdefault(part.get('index', 0), {'name': '', 'id': '', 'arguments': ''})
                            value['id'] = part.get('id') or value['id']
                            function = part.get('function') or {}
                            value['name'] += function.get('name') or ''
                            fragment = function.get('arguments')
                            if isinstance(fragment, dict):
                                value['arguments'] = json.dumps(fragment)
                            elif isinstance(fragment, str):
                                value['arguments'] += fragment
                        calls = take_calls() if finish_reason and pending else []
                        yield StreamChunk(delta_text=delta_text, tool_calls=calls, finish_reason=finish_reason)
            if pending:
                yield StreamChunk(tool_calls=take_calls(), finish_reason='tool_calls')
        except requests.exceptions.Timeout as error:
            raise TimeoutError('Streaming response timed out', provider=self.config.name, raw_error=error) from error
        except requests.exceptions.ConnectionError as error:
            raise ProviderUnavailableError('Streaming response disconnected', provider=self.config.name, raw_error=error) from error
        except requests.exceptions.RequestException as error:
            raise ProviderUnavailableError('Streaming response interrupted', provider=self.config.name, raw_error=error) from error
        finally:
            # A streamed response holds the connection open until it is
            # closed; without this the socket leaked on every stream.
            closer = getattr(resp, "close", None)
            if callable(closer):
                closer()
