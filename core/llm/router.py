"""Unified LLMRouter orchestrator for Zaya.
Created and developed by Sajan Rai for Zaya.
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any, Callable, Dict, Iterator, List, Optional

from core.llm.adapters import ADAPTER_MAP, BaseAdapter
from core.llm.health import CooldownTracker, ProviderHealth
from core.llm.policies import RetryPolicy, RoutingPolicy
from core.llm.registry import ProviderConfig, ProviderRegistry
from core.llm.types import (
    AuthenticationError,
    ImagePart,
    InvalidRequestError,
    LLMError,
    LLMMessage,
    LLMResponse,
    RateLimitError,
    RecoverableError,
    StreamChunk,
    ToolCall,
    ToolDefinition,
)

logger = logging.getLogger("core.llm.router")


class LLMRouter:
    """The central unified multi-provider LLM router with failover, health tracking, and metrics."""

    def __init__(
        self,
        registry: Optional[ProviderRegistry] = None,
        health: Optional[ProviderHealth] = None,
        cooldown: Optional[CooldownTracker] = None,
        retry_policy: Optional[RetryPolicy] = None,
        logger_fn: Optional[Callable[[str], None]] = None,
    ):
        if registry is None:
            self.registry = ProviderRegistry()
            self.registry.load_from_config()
        else:
            self.registry = registry
        self.health = health or ProviderHealth()
        self.cooldown = cooldown or CooldownTracker()
        self.retry_policy = retry_policy or RetryPolicy()
        self.routing_policy = RoutingPolicy(self.registry, self.health, self.cooldown)
        self.logger_fn = logger_fn or (lambda msg: logger.info(msg))
        self._adapter_cache: Dict[str, BaseAdapter] = {}

    def get_adapter(self, config: ProviderConfig) -> BaseAdapter:
        if config.name not in self._adapter_cache:
            cls = ADAPTER_MAP.get(config.provider_type, ADAPTER_MAP["compatible"])
            self._adapter_cache[config.name] = cls(config)
        return self._adapter_cache[config.name]

    def has_multimodal_content(self, messages: List[LLMMessage]) -> bool:
        for m in messages:
            if isinstance(m.content, list):
                for part in m.content:
                    if isinstance(part, ImagePart):
                        return True
        return False

    def route(
        self,
        messages: List[LLMMessage],
        tools: Optional[List[ToolDefinition]] = None,
        task: Optional[str] = None,
        preferred_provider: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        timeout_sec: Optional[float] = None,
        **kwargs
    ) -> LLMResponse:
        """Routes chat request through candidate providers with intelligent failover."""
        request_id = str(uuid.uuid4())[:8]
        require_multimodal = self.has_multimodal_content(messages)

        candidates = self.routing_policy.get_candidate_providers(
            task=task,
            preferred_provider=preferred_provider,
            require_multimodal=require_multimodal,
        )

        if not candidates:
            raise LLMError(f"No available or healthy providers found for task '{task}' (multimodal={require_multimodal}).")

        last_error: Optional[Exception] = None

        for config in candidates:
            adapter = self.get_adapter(config)
            provider_name = config.name

            # Try retries on this provider if retryable
            for attempt in range(max(0, self.retry_policy.max_retries) + 1):
                try:
                    self.logger_fn(
                        f"[LLMRouter:{request_id}] Dispatching to {provider_name} (model={config.model}, attempt={attempt + 1})"
                    )
                    start_time = time.monotonic()
                    response = adapter.chat(
                        messages=messages,
                        tools=tools,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        timeout_sec=timeout_sec,
                        **kwargs
                    )
                    latency_ms = (time.monotonic() - start_time) * 1000.0

                    self.health.record_success(provider_name, latency_ms)
                    self.logger_fn(
                        f"[LLMRouter:{request_id}] Success from {provider_name} in {latency_ms:.1f}ms"
                    )
                    return response

                except InvalidRequestError as e:
                    # Client errors (400, bad schema, bad json) must NOT trigger fallback!
                    self.health.record_failure(provider_name, str(e))
                    self.logger_fn(f"[LLMRouter:{request_id}] Invalid request error on {provider_name}: {e}. Surfacing immediately.")
                    raise

                except AuthenticationError as e:
                    # Key invalid or rotated: try key rotation on this provider if it has multiple keys
                    self.health.record_failure(provider_name, str(e))
                    if len(config.api_keys) > 1 and attempt < self.retry_policy.max_retries:
                        config.rotate_key()
                        self.logger_fn(f"[LLMRouter:{request_id}] Rotated API key for {provider_name}. Retrying...")
                        continue
                    # Else cool this provider and fall back
                    self.cooldown.cool(provider_name, 3600.0)
                    last_error = e
                    break

                except RateLimitError as e:
                    self.health.record_failure(provider_name, str(e))
                    delay = self.retry_policy.calculate_delay(attempt, error=e)
                    if attempt < self.retry_policy.max_retries and delay <= 2.0:
                        self.logger_fn(f"[LLMRouter:{request_id}] Rate limited on {provider_name}. Backing off {delay:.1f}s...")
                        self.retry_policy.sleep_fn(delay)
                        continue
                    # Cooldown provider and fall back
                    self.cooldown.cool(provider_name, e.retry_after)
                    self.logger_fn(f"[LLMRouter:{request_id}] Provider {provider_name} cooling for {e.retry_after}s. Falling back...")
                    last_error = e
                    break

                except RecoverableError as e:
                    self.health.record_failure(provider_name, str(e))
                    if self.retry_policy.is_retryable(e) and attempt < self.retry_policy.max_retries:
                        delay = self.retry_policy.calculate_delay(attempt, error=e)
                        self.logger_fn(f"[LLMRouter:{request_id}] Recoverable error on {provider_name}: {e}. Backing off {delay:.1f}s...")
                        self.retry_policy.sleep_fn(delay)
                        continue
                    # Fall back to next provider
                    self.cooldown.cool(provider_name, 15.0)
                    self.logger_fn(f"[LLMRouter:{request_id}] Provider {provider_name} failed: {e}. Falling back to next candidate...")
                    last_error = e
                    break

                except Exception as e:
                    # Non-LLM unexpected code exception: do not mask programming bugs
                    self.health.record_failure(provider_name, str(e))
                    self.logger_fn(f"[LLMRouter:{request_id}] Unexpected exception on {provider_name}: {e}")
                    raise

        raise LLMError(f"All candidate LLM providers failed for task '{task}'. Last error: {last_error}", raw_error=last_error)

    def stream_route(
        self,
        messages: List[LLMMessage],
        tools: Optional[List[ToolDefinition]] = None,
        task: Optional[str] = None,
        preferred_provider: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        timeout_sec: Optional[float] = None,
        **kwargs
    ) -> Iterator[StreamChunk]:
        """Routes streaming request to first eligible provider."""
        candidates = self.routing_policy.get_candidate_providers(
            task=task,
            preferred_provider=preferred_provider,
        )
        if not candidates:
            raise LLMError(f"No available or healthy providers found for streaming task '{task}'.")

        last_error = None
        for config in candidates:
            adapter = self.get_adapter(config)
            emitted = False
            try:
                stream = adapter.stream_chat(
                    messages=messages,
                    tools=tools,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout_sec=timeout_sec,
                    **kwargs
                )
                for chunk in stream:
                    emitted = emitted or bool(chunk.delta_text or chunk.tool_calls)
                    yield chunk
                return
            except (RateLimitError, RecoverableError) as e:
                self.health.record_failure(config.name, str(e))
                self.cooldown.cool(config.name, 30.0)
                if emitted:
                    # The consumer has already seen part of this answer. A new
                    # provider cannot retract it; report interruption instead
                    # of concatenating an unrelated replacement response.
                    raise
                last_error = e
                continue
            except Exception:
                raise

        raise LLMError(f"All streaming candidates failed. Last error: {last_error}", raw_error=last_error)


_default_router: Optional[LLMRouter] = None


def get_default_router() -> LLMRouter:
    global _default_router
    if _default_router is None:
        _default_router = LLMRouter()
    return _default_router
