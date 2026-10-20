"""Retry and routing policies for the LLM router."""

from __future__ import annotations

import logging
import random
import time
from typing import Callable, List, Optional, TypeVar

from core.llm.health import CooldownTracker, ProviderHealth
from core.llm.registry import ProviderConfig, ProviderRegistry
from core.llm.types import (
    LLMError,
    RateLimitError,
    ProviderUnavailableError,
    TimeoutError,
    RecoverableError,
)

logger = logging.getLogger("core.llm.policies")
T = TypeVar("T")


class RetryPolicy:
    """Manages retry attempts and exponential backoff for a single provider."""

    def __init__(
        self,
        max_retries: int = 2,
        initial_backoff_sec: float = 0.5,
        backoff_multiplier: float = 2.0,
        max_backoff_sec: float = 5.0,
        jitter: bool = True,
        sleep_fn: Callable[[float], None] = time.sleep,
    ):
        self.max_retries = max_retries
        self.initial_backoff_sec = initial_backoff_sec
        self.backoff_multiplier = backoff_multiplier
        self.max_backoff_sec = max_backoff_sec
        self.jitter = jitter
        self.sleep_fn = sleep_fn

    def calculate_delay(self, attempt: int, error: Optional[Exception] = None) -> float:
        if isinstance(error, RateLimitError) and error.retry_after > 0:
            return min(error.retry_after, self.max_backoff_sec)
        delay = self.initial_backoff_sec * (self.backoff_multiplier ** attempt)
        if self.jitter:
            delay = delay * (0.5 + random.random())
        return min(delay, self.max_backoff_sec)

    def is_retryable(self, error: Exception) -> bool:
        return isinstance(error, (RateLimitError, ProviderUnavailableError, TimeoutError))


class RoutingPolicy:
    """Selects and orders candidate providers according to health, task, and config."""

    def __init__(
        self,
        registry: ProviderRegistry,
        health: ProviderHealth,
        cooldown: CooldownTracker,
    ):
        self.registry = registry
        self.health = health
        self.cooldown = cooldown

    def get_candidate_providers(
        self,
        task: Optional[str] = None,
        preferred_provider: Optional[str] = None,
        require_multimodal: bool = False,
    ) -> List[ProviderConfig]:
        """Returns ordered list of available ProviderConfigs eligible for routing."""
        all_providers = list(self.registry.providers.values())
        if not all_providers:
            return []

        def sort_key(p: ProviderConfig):
            # 1. Explicitly preferred provider gets highest priority
            is_preferred = 0 if (preferred_provider and p.name == preferred_provider) else 1
            # 2. Primary configured provider
            is_primary = 0 if p.name == self.registry.primary_provider else 1
            # 3. Task affinity match
            task_match = 0 if (task and task in p.task_affinity) else 1
            # 4. Fallback chain index if defined
            try:
                fallback_idx = self.registry.fallback_chain.index(p.name)
            except ValueError:
                fallback_idx = 999
            # 5. Native priority
            return (is_preferred, task_match, is_primary, fallback_idx, p.priority)

        sorted_providers = sorted(all_providers, key=sort_key)

        candidates = []
        for p in sorted_providers:
            # Check cooldown
            if self.cooldown.is_cooling(p.name):
                logger.debug(f"Skipping {p.name}: cooling down")
                continue
            # Check circuit breaker
            if not self.health.allow_request(p.name):
                logger.debug(f"Skipping {p.name}: circuit breaker open")
                continue
            # If multimodal is required, ensure provider supports it
            if require_multimodal and p.provider_type not in ("gemini", "openai", "openrouter"):
                continue
            candidates.append(p)

        return candidates
