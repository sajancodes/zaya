"""
Universal Multi-Provider LLM Router and Combiner for Zaya.

Supports:
- OpenAI (official)
- OpenRouter (openrouter.ai)
- 9Router (api.9router.com)
- Ollama (local /api/chat)
- Custom OpenAI-compatible endpoints (LM Studio, Jan, LocalAI, vLLM, DeepSeek, Groq, etc.)
- Gemini (REST/OpenAI compatibility endpoints)

Features:
- Automatic failover chaining: if a provider hits 429, 502, or connection timeout,
  transparently fails over to the next provider in the chain.
- Universal tool declaration normalization (Gemini <-> OpenAI function format).
- BYOK (Bring-Your-Own-Key) credential handling.
"""
from __future__ import annotations

import json
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
import requests

logger = logging.getLogger("Zaya.UniversalRouter")

def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

BASE_DIR = get_base_dir()
CONFIG_PATH = BASE_DIR / "config" / "api_keys.json"

PROVIDER_BASE_URLS = {
    "openai": "https://api.openai.com/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "9router": "https://api.9router.com/v1",
    "ollama": "http://localhost:11434/api",
    "groq": "https://api.groq.com/openai/v1",
    "deepseek": "https://api.deepseek.com/v1",
}

DEFAULT_MODELS = {
    "openai": "gpt-4o-mini",
    "openrouter": "google/gemini-2.5-flash",
    "9router": "gpt-4o-mini",
    "ollama": "llama3.2",
    "groq": "llama-3.3-70b-versatile",
    "deepseek": "deepseek-chat",
}

@dataclass
class ProviderConfig:
    provider: str
    base_url: str = ""
    api_key: str = ""
    model: str = ""
    extra_headers: Dict[str, str] = field(default_factory=dict)
    timeout_sec: float = 30.0

    def __post_init__(self):
        if not self.base_url:
            self.base_url = PROVIDER_BASE_URLS.get(self.provider.lower(), "")
        if not self.model:
            self.model = DEFAULT_MODELS.get(self.provider.lower(), "gpt-4o-mini")


def normalize_tools_for_openai(tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Converts Zaya/Gemini style function schemas into OpenAI tool specifications."""
    out = []
    for t in tools:
        if not isinstance(t, dict):
            continue
        # If already in OpenAI format
        if t.get("type") == "function" and "function" in t:
            out.append(t)
            continue

        name = t.get("name", "")
        desc = t.get("description", "")
        params = t.get("parameters", {})

        # Lowercase schema type strings (e.g. OBJECT -> object)
        def _lower_types(d: Any) -> Any:
            if isinstance(d, dict):
                res = {}
                for k, v in d.items():
                    if k == "type" and isinstance(v, str):
                        res[k] = v.lower()
                    else:
                        res[k] = _lower_types(v)
                return res
            elif isinstance(d, list):
                return [_lower_types(x) for x in d]
            return d

        clean_params = _lower_types(params)
        if "type" not in clean_params:
            clean_params["type"] = "object"

        out.append({
            "type": "function",
            "function": {
                "name": name,
                "description": desc,
                "parameters": clean_params
            }
        })
    return out


def parse_tool_calls_from_response(resp_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extracts function tool calls from an OpenAI-compatible JSON response."""
    calls = []
    try:
        choices = resp_data.get("choices", [])
        if not choices:
            return calls
        message = choices[0].get("message", {})
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
            else:
                args = raw_args
            calls.append({"name": name, "arguments": args, "id": rc.get("id")})
    except Exception as e:
        logger.warning(f"Failed to parse tool calls: {e}")
    return calls


def load_provider_chain() -> List[ProviderConfig]:
    """Reads config/api_keys.json and constructs an ordered fallback list of ProviderConfigs."""
    try:
        if CONFIG_PATH.exists():
            cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        else:
            cfg = {}
    except Exception:
        cfg = {}

    chain = []
    primary_name = cfg.get("llm_provider", "openai").strip().lower()
    fallback_names = cfg.get("fallback_providers", ["9router", "openrouter", "ollama"])

    # Build unique ordered list
    ordered_providers = [primary_name] + [p.lower() for p in fallback_names if p.lower() != primary_name]

    for p in ordered_providers:
        # Determine API key
        key = (
            cfg.get(f"{p}_api_key")
            or cfg.get(f"{p}_key")
            or (cfg.get("api_key") if p in ("gemini", "openai") else None)
            or os.environ.get(f"{p.upper()}_API_KEY")
            or ""
        )
        base_url = cfg.get(f"{p}_url") or cfg.get(f"{p}_base_url") or PROVIDER_BASE_URLS.get(p, "")
        model = cfg.get(f"{p}_model") or cfg.get("llm_model") or DEFAULT_MODELS.get(p, "gpt-4o-mini")

        headers = {}
        if p == "openrouter":
            headers["HTTP-Referer"] = "https://github.com/sajancodes/zaya"
            headers["X-Title"] = "Zaya Assistant"
        elif p == "9router":
            headers["X-Client"] = "Zaya-IRIS-Engine"

        # If it's a remote provider requiring a key and key is missing, skip unless local ollama
        if p != "ollama" and not key and not base_url.startswith("http://localhost"):
            continue

        chain.append(ProviderConfig(
            provider=p,
            base_url=base_url,
            api_key=key,
            model=model,
            extra_headers=headers
        ))

    # If chain is empty, add a default local fallback
    if not chain:
        chain.append(ProviderConfig(
            provider="ollama",
            base_url="http://localhost:11434/api",
            model="llama3.2"
        ))

    return chain


class UniversalLLMRouter:
    """Manages execution and auto-fallback across LLM endpoints."""

    def __init__(self, logger_fn: Callable[[str], None] = print):
        self.logger_fn = logger_fn

    def execute_request(
        self,
        config: ProviderConfig,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024
    ) -> Dict[str, Any]:
        """Sends chat completion request to a specific provider config."""
        url = config.base_url.rstrip("/")
        if not url.endswith("/chat/completions"):
            url = f"{url}/chat/completions"

        headers = {
            "Content-Type": "application/json",
            **config.extra_headers
        }
        if config.api_key:
            headers["Authorization"] = f"Bearer {config.api_key}"

        payload: Dict[str, Any] = {
            "model": config.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        if tools:
            payload["tools"] = normalize_tools_for_openai(tools)
            payload["tool_choice"] = "auto"

        resp = requests.post(url, headers=headers, json=payload, timeout=config.timeout_sec)
        if resp.status_code != 200:
            raise RuntimeError(f"Provider {config.provider} returned HTTP {resp.status_code}: {resp.text[:300]}")

        data = resp.json()
        content = ""
        tool_calls = []
        try:
            choices = data.get("choices", [])
            if choices:
                msg = choices[0].get("message", {})
                content = msg.get("content") or ""
            tool_calls = parse_tool_calls_from_response(data)
        except Exception:
            pass

        return {
            "content": content,
            "tool_calls": tool_calls,
            "provider_used": config.provider,
            "model_used": config.model,
            "raw": data
        }

    def route_with_fallback(
        self,
        messages: List[Dict[str, str]],
        chain: Optional[List[ProviderConfig]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Executes request trying providers in sequence until one succeeds."""
        active_chain = chain or load_provider_chain()
        last_error = None

        for cfg in active_chain:
            try:
                self.logger_fn(f"[UniversalRouter] Dispatching to {cfg.provider} ({cfg.model})...")
                res = self.execute_request(cfg, messages, tools=tools, **kwargs)
                return res
            except Exception as e:
                self.logger_fn(f"[UniversalRouter] Provider {cfg.provider} failed: {e}. Trying next provider in chain...")
                last_error = e

        raise RuntimeError(f"All LLM providers in fallback chain failed. Last error: {last_error}")
