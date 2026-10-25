"""Provider health, cooldown tracking, and circuit breaker implementation."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional


class CircuitState(str, Enum):
    CLOSED = "closed"        # Healthy, requests flow through
    OPEN = "open"            # Failing, requests blocked
    HALF_OPEN = "half_open"  # Testing recovery with a single probe request


@dataclass
class ProviderMetrics:
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    consecutive_failures: int = 0
    total_latency_ms: float = 0.0
    last_success_time: float = 0.0
    last_failure_time: float = 0.0
    last_error: str = ""

    @property
    def average_latency_ms(self) -> float:
        if self.successful_requests == 0:
            return 0.0
        return self.total_latency_ms / self.successful_requests


class CooldownTracker:
    """Thread-safe cooldown management for providers and keys."""

    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self._lock = threading.Lock()
        self._blocked_until: Dict[str, float] = {}

    def cool(self, entity_id: str, duration_sec: float) -> None:
        with self._lock:
            target = self.clock() + max(1.0, duration_sec)
            self._blocked_until[entity_id] = max(self._blocked_until.get(entity_id, 0.0), target)

    def is_cooling(self, entity_id: str) -> bool:
        with self._lock:
            expiry = self._blocked_until.get(entity_id, 0.0)
            return expiry > self.clock()

    def remaining_cooldown(self, entity_id: str) -> float:
        with self._lock:
            expiry = self._blocked_until.get(entity_id, 0.0)
            rem = expiry - self.clock()
            return max(0.0, rem)

    def clear(self, entity_id: str) -> None:
        with self._lock:
            self._blocked_until.pop(entity_id, None)


class ProviderHealth:
    """Tracks health metrics and circuit breaker state per provider."""

    def __init__(
        self,
        failure_threshold: int = 3,
        recovery_timeout_sec: float = 30.0,
        clock=time.monotonic,
        half_open_probe_timeout_sec: float = 30.0
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout_sec = recovery_timeout_sec
        # How long a half-open probe may go unanswered before another one is
        # issued. Kept separate from recovery_timeout_sec: that one is the
        # wait BEFORE the first probe, and a zero there must not turn the
        # half-open state into an unlimited pass.
        self.half_open_probe_timeout_sec = half_open_probe_timeout_sec
        self.clock = clock
        self._lock = threading.Lock()
        self.metrics: Dict[str, ProviderMetrics] = {}
        self.circuit_state: Dict[str, CircuitState] = {}
        self.opened_at: Dict[str, float] = {}
        # When a provider was handed a trial request while half-open. One
        # probe at a time: the circuit is a brake, not a suggestion.
        self._half_open_probe_at: Dict[str, float] = {}

    def _get_metrics(self, provider_id: str) -> ProviderMetrics:
        if provider_id not in self.metrics:
            self.metrics[provider_id] = ProviderMetrics()
        return self.metrics[provider_id]

    def allow_request(self, provider_id: str) -> bool:
        """Determines if the circuit breaker permits sending a request."""
        with self._lock:
            state = self.circuit_state.get(provider_id, CircuitState.CLOSED)
            if state == CircuitState.CLOSED:
                return True
            now = self.clock()
            if state == CircuitState.OPEN:
                elapsed = now - self.opened_at.get(provider_id, 0.0)
                if elapsed >= self.recovery_timeout_sec:
                    self.circuit_state[provider_id] = CircuitState.HALF_OPEN
                    self._half_open_probe_at[provider_id] = now
                    return True
                return False
            # HALF_OPEN allows exactly one trial request at a time. The old
            # code returned True unconditionally, so a half-open provider
            # took an unlimited share of the traffic it was supposed to be
            # probing with. A probe that never reports back (the request was
            # never actually dispatched) is retried after the probe timeout,
            # so a lost probe cannot wedge the provider shut forever.
            issued = self._half_open_probe_at.get(provider_id)
            if issued is not None and (now - issued) < self.half_open_probe_timeout_sec:
                return False
            self._half_open_probe_at[provider_id] = now
            return True

    def record_success(self, provider_id: str, latency_ms: float) -> None:
        with self._lock:
            m = self._get_metrics(provider_id)
            m.total_requests += 1
            m.successful_requests += 1
            m.consecutive_failures = 0
            m.total_latency_ms += latency_ms
            m.last_success_time = self.clock()
            self.circuit_state[provider_id] = CircuitState.CLOSED
            self._half_open_probe_at.pop(provider_id, None)

    def record_failure(self, provider_id: str, error_msg: str) -> None:
        with self._lock:
            m = self._get_metrics(provider_id)
            m.total_requests += 1
            m.failed_requests += 1
            m.consecutive_failures += 1
            m.last_failure_time = self.clock()
            m.last_error = error_msg

            if m.consecutive_failures >= self.failure_threshold:
                self.circuit_state[provider_id] = CircuitState.OPEN
                self.opened_at[provider_id] = self.clock()
                self._half_open_probe_at.pop(provider_id, None)
