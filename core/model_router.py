"""Intelligent Model Routing, Health Registry, and Dynamic Fallback Ladder for Zaya.
Created and developed by Sajan Rai for Zaya.

Provides capability-aware, cost-aware, and latency-measured model selection across
providers (Gemini, OpenAI, Anthropic, Groq, Local/Ollama). Automatically routes
around rate limits, outages, and timeouts with transparent justification logs.
"""
from __future__ import annotations

import enum
import logging
import threading
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class Provider(str, enum.Enum):
    GEMINI = "gemini"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GROQ = "groq"
    OLLAMA = "ollama"
    MOCK = "mock"


class ErrorCategory(str, enum.Enum):
    RATE_LIMIT = "rate_limit"          # 429: quota/rate limit exhausted
    OVERLOADED = "overloaded"          # 503: server overloaded / high traffic
    AUTH_ERROR = "auth_error"          # 401/403: invalid or missing API key
    TIMEOUT = "timeout"                # request deadline exceeded
    UNAVAILABLE = "unavailable"        # service down or endpoint unreachable
    MODEL_NOT_FOUND = "not_found"      # model ID deprecated or unsupported
    UNKNOWN = "unknown"                # unclassified failure


class ComplexityTier(str, enum.Enum):
    LIGHT = "light"                    # quick classification, formatting, short Q&A
    STANDARD = "standard"              # typical voice dialog, general tools
    COMPLEX = "complex"                # code generation, multi-step planning, analysis
    REASONING = "reasoning"            # deep logic, architecture, debugging


@dataclass
class ModelSpec:
    """Specification of an available LLM."""
    id: str
    name: str
    provider: Provider
    context_window: int = 128000
    supports_vision: bool = False
    supports_tools: bool = True
    supports_streaming: bool = True
    complexity_rank: int = 2           # 1 (light) to 4 (reasoning)
    cost_tier: int = 1                 # 0 (free/local), 1 (cheap), 2 (standard), 3 (premium)
    enabled: bool = True
    priority: int = 10                 # Lower number = higher priority preference


@dataclass
class ModelHealth:
    """Dynamic health and telemetry metrics for a model."""
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    consecutive_failures: int = 0
    average_latency_ms: float = 0.0
    last_call_timestamp: float = 0.0
    cooldown_until: float = 0.0
    last_error_category: Optional[ErrorCategory] = None
    last_error_message: str = ""
    auth_valid: bool = True

    @property
    def reliability(self) -> float:
        if self.total_calls == 0:
            return 1.0  # optimistic prior for untried models
        return max(0.0, min(1.0, self.successful_calls / self.total_calls))

    @property
    def is_in_cooldown(self) -> bool:
        return time.time() < self.cooldown_until

    def remaining_cooldown_sec(self) -> float:
        return max(0.0, self.cooldown_until - time.time())


@dataclass
class RoutingDecision:
    """Transparent justification of why a model was chosen or skipped."""
    selected_model: Optional[ModelSpec]
    reason: str
    candidates_evaluated: List[dict] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)


# ── Default Model Catalog ───────────────────────────────────────────────────

DEFAULT_MODELS: List[ModelSpec] = [
    # Gemini Tier (Native Google AI)
    ModelSpec(
        id="gemini-2.5-flash",
        name="Gemini 2.5 Flash",
        provider=Provider.GEMINI,
        context_window=1000000,
        supports_vision=True,
        supports_tools=True,
        complexity_rank=2,
        cost_tier=1,
        priority=1,
    ),
    ModelSpec(
        id="gemini-2.5-pro",
        name="Gemini 2.5 Pro",
        provider=Provider.GEMINI,
        context_window=2000000,
        supports_vision=True,
        supports_tools=True,
        complexity_rank=4,
        cost_tier=2,
        priority=2,
    ),
    ModelSpec(
        id="gemini-2.0-flash",
        name="Gemini 2.0 Flash",
        provider=Provider.GEMINI,
        context_window=1000000,
        supports_vision=True,
        supports_tools=True,
        complexity_rank=2,
        cost_tier=1,
        priority=3,
    ),
    # Groq Tier (Ultra Low Latency)
    ModelSpec(
        id="groq/llama-3.3-70b-versatile",
        name="Llama 3.3 70B (Groq)",
        provider=Provider.GROQ,
        context_window=128000,
        supports_vision=False,
        supports_tools=True,
        complexity_rank=3,
        cost_tier=1,
        priority=4,
    ),
    ModelSpec(
        id="groq/llama-3.1-8b-instant",
        name="Llama 3.1 8B Instant (Groq)",
        provider=Provider.GROQ,
        context_window=128000,
        supports_vision=False,
        supports_tools=True,
        complexity_rank=1,
        cost_tier=1,
        priority=5,
    ),
    # Local / Ollama Tier (Zero Cost, Offline Capable)
    ModelSpec(
        id="ollama/llama3.2:latest",
        name="Llama 3.2 (Local Ollama)",
        provider=Provider.OLLAMA,
        context_window=32000,
        supports_vision=False,
        supports_tools=True,
        complexity_rank=1,
        cost_tier=0,
        priority=6,
    ),
    ModelSpec(
        id="ollama/qwen2.5-coder:7b",
        name="Qwen 2.5 Coder 7B (Local)",
        provider=Provider.OLLAMA,
        context_window=32000,
        supports_vision=False,
        supports_tools=True,
        complexity_rank=3,
        cost_tier=0,
        priority=7,
    ),
    # OpenAI Backup Tier
    ModelSpec(
        id="openai/gpt-4o",
        name="GPT-4o (OpenAI)",
        provider=Provider.OPENAI,
        context_window=128000,
        supports_vision=True,
        supports_tools=True,
        complexity_rank=4,
        cost_tier=3,
        priority=8,
    ),
    ModelSpec(
        id="openai/gpt-4o-mini",
        name="GPT-4o Mini (OpenAI)",
        provider=Provider.OPENAI,
        context_window=128000,
        supports_vision=True,
        supports_tools=True,
        complexity_rank=2,
        cost_tier=1,
        priority=9,
    ),
]


class ModelRouter:
    """Dynamic, measured model router with automated fallback and health tracking."""

    def __init__(self, models: Optional[List[ModelSpec]] = None) -> None:
        self._lock = threading.RLock()
        self._models: Dict[str, ModelSpec] = {}
        self._health: Dict[str, ModelHealth] = {}
        self._history: List[RoutingDecision] = []

        initial = models if models is not None else DEFAULT_MODELS
        for spec in initial:
            self.register_model(spec)

    # ── Model Registry Management ───────────────────────────────────────────

    def register_model(self, spec: ModelSpec) -> None:
        """Register or update a model specification."""
        with self._lock:
            self._models[spec.id] = spec
            if spec.id not in self._health:
                self._health[spec.id] = ModelHealth()

    def unregister_model(self, model_id: str) -> bool:
        """Remove a model from the registry."""
        with self._lock:
            if model_id in self._models:
                del self._models[model_id]
                self._health.pop(model_id, None)
                return True
            return False

    def get_model(self, model_id: str) -> Optional[ModelSpec]:
        with self._lock:
            return self._models.get(model_id)

    def get_health(self, model_id: str) -> Optional[ModelHealth]:
        with self._lock:
            return self._health.get(model_id)

    def list_models(self) -> List[dict]:
        with self._lock:
            res = []
            for m_id, spec in self._models.items():
                h = self._health.get(m_id, ModelHealth())
                item = asdict(spec)
                item["health"] = asdict(h)
                item["reliability"] = h.reliability
                item["in_cooldown"] = h.is_in_cooldown
                res.append(item)
            return sorted(res, key=lambda x: (x["priority"], -x["reliability"]))

    # ── Routing Logic ───────────────────────────────────────────────────────

    def route(
        self,
        complexity: ComplexityTier = ComplexityTier.STANDARD,
        requires_vision: bool = False,
        requires_tools: bool = True,
        preferred_provider: Optional[Provider] = None,
        max_cost_tier: int = 3,
    ) -> RoutingDecision:
        """Select the optimal model based on requirements, health, and latency."""
        with self._lock:
            evaluations = []
            candidates: List[Tuple[float, ModelSpec]] = []

            rank_target = {
                ComplexityTier.LIGHT: 1,
                ComplexityTier.STANDARD: 2,
                ComplexityTier.COMPLEX: 3,
                ComplexityTier.REASONING: 4,
            }.get(complexity, 2)

            for model_id, spec in self._models.items():
                health = self._health[model_id]
                eval_record = {"model_id": model_id, "eligible": True, "rejection_reason": ""}

                # 1. Enabled check
                if not spec.enabled:
                    eval_record["eligible"] = False
                    eval_record["rejection_reason"] = "Model disabled by configuration"
                    evaluations.append(eval_record)
                    continue

                # 2. Authentication check
                if not health.auth_valid:
                    eval_record["eligible"] = False
                    eval_record["rejection_reason"] = "Provider authentication failed"
                    evaluations.append(eval_record)
                    continue

                # 3. Cooldown check
                if health.is_in_cooldown:
                    rem = round(health.remaining_cooldown_sec(), 1)
                    eval_record["eligible"] = False
                    eval_record["rejection_reason"] = f"In cooldown ({rem}s remaining, last error: {health.last_error_category})"
                    evaluations.append(eval_record)
                    continue

                # 4. Capability check: Vision
                if requires_vision and not spec.supports_vision:
                    eval_record["eligible"] = False
                    eval_record["rejection_reason"] = "Does not support vision"
                    evaluations.append(eval_record)
                    continue

                # 5. Capability check: Tools
                if requires_tools and not spec.supports_tools:
                    eval_record["eligible"] = False
                    eval_record["rejection_reason"] = "Does not support tool calls"
                    evaluations.append(eval_record)
                    continue

                # 6. Cost ceiling
                if spec.cost_tier > max_cost_tier:
                    eval_record["eligible"] = False
                    eval_record["rejection_reason"] = f"Cost tier {spec.cost_tier} exceeds ceiling {max_cost_tier}"
                    evaluations.append(eval_record)
                    continue

                # Compute Score: lower score = better candidate
                # Score combines: priority + complexity distance + latency penalty + unreliability penalty
                complexity_dist = max(0, rank_target - spec.complexity_rank) * 5.0
                if spec.complexity_rank < rank_target and complexity == ComplexityTier.REASONING:
                    # Penalize light models heavily for deep reasoning tasks
                    complexity_dist += 15.0

                provider_bonus = -3.0 if preferred_provider and spec.provider == preferred_provider else 0.0
                latency_penalty = min(5.0, health.average_latency_ms / 500.0)
                reliability_penalty = (1.0 - health.reliability) * 10.0
                consecutive_fail_penalty = health.consecutive_failures * 4.0

                score = (
                    spec.priority * 1.5
                    + complexity_dist
                    + provider_bonus
                    + latency_penalty
                    + reliability_penalty
                    + consecutive_fail_penalty
                )

                eval_record["score"] = round(score, 2)
                eval_record["reliability"] = round(health.reliability, 3)
                eval_record["avg_latency_ms"] = round(health.average_latency_ms, 1)
                evaluations.append(eval_record)
                candidates.append((score, spec))

            if not candidates:
                # Emergency fallback: pick any enabled model even if in cooldown or lower complexity
                for model_id, spec in self._models.items():
                    if spec.enabled:
                        decision = RoutingDecision(
                            selected_model=spec,
                            reason="Emergency fallback: all preferred models are in cooldown or ineligible.",
                            candidates_evaluated=evaluations,
                        )
                        self._history.append(decision)
                        return decision

                decision = RoutingDecision(
                    selected_model=None,
                    reason="No model available. All models disabled or unregistered.",
                    candidates_evaluated=evaluations,
                )
                self._history.append(decision)
                return decision

            # Sort by ascending score
            candidates.sort(key=lambda x: x[0])
            best_spec = candidates[0][1]
            reason = (
                f"Selected {best_spec.name} ({best_spec.id}) for complexity '{complexity.value}' "
                f"[Score: {candidates[0][0]:.2f}, Reliability: {self._health[best_spec.id].reliability:.1%}, "
                f"Avg Latency: {self._health[best_spec.id].average_latency_ms:.0f}ms]."
            )

            decision = RoutingDecision(
                selected_model=best_spec,
                reason=reason,
                candidates_evaluated=evaluations,
            )
            self._history.append(decision)
            return decision

    # ── Telemetry & Health Reporting ────────────────────────────────────────

    def record_success(self, model_id: str, latency_ms: float) -> None:
        """Record a successful execution for telemetry."""
        with self._lock:
            h = self._health.get(model_id)
            if not h:
                return
            h.total_calls += 1
            h.successful_calls += 1
            h.consecutive_failures = 0
            h.last_call_timestamp = time.time()

            # Exponential moving average for latency
            if h.average_latency_ms <= 0:
                h.average_latency_ms = latency_ms
            else:
                h.average_latency_ms = (h.average_latency_ms * 0.7) + (latency_ms * 0.3)

    def record_failure(
        self,
        model_id: str,
        category: ErrorCategory,
        error_message: str = "",
        cooldown_seconds: Optional[float] = None,
    ) -> None:
        """Record a failure and apply appropriate category-specific backoff."""
        with self._lock:
            h = self._health.get(model_id)
            if not h:
                return
            h.total_calls += 1
            h.failed_calls += 1
            h.consecutive_failures += 1
            h.last_call_timestamp = time.time()
            h.last_error_category = category
            h.last_error_message = error_message[:500]

            # Determine cooldown based on failure category
            if cooldown_seconds is not None:
                cd = cooldown_seconds
            elif category == ErrorCategory.RATE_LIMIT:
                # Rate limit cooldown: exponential backoff from 30s up to 300s
                cd = min(300.0, 30.0 * (1.8 ** min(4, h.consecutive_failures - 1)))
            elif category == ErrorCategory.OVERLOADED:
                # Overload cooldown: shorter 15s to 60s
                cd = min(60.0, 15.0 * h.consecutive_failures)
            elif category == ErrorCategory.AUTH_ERROR:
                # Auth error: long cooldown and mark invalid
                h.auth_valid = False
                cd = 3600.0
            elif category == ErrorCategory.TIMEOUT:
                cd = 10.0 * h.consecutive_failures
            else:
                cd = 5.0

            h.cooldown_until = time.time() + cd
            logger.warning(
                "[ModelRouter] Model %s failed (%s): %s. Cooldown: %.1fs",
                model_id, category.value, error_message[:100], cd
            )

    def execute_with_fallback(
        self,
        caller_fn: Callable[[ModelSpec], Any],
        complexity: ComplexityTier = ComplexityTier.STANDARD,
        requires_vision: bool = False,
        requires_tools: bool = True,
        max_attempts: int = 3,
    ) -> Tuple[Any, RoutingDecision]:
        """Execute a call using dynamic fallback if the primary candidate fails."""
        attempt = 0
        tried_ids = set()

        while attempt < max_attempts:
            attempt += 1
            decision = self.route(
                complexity=complexity,
                requires_vision=requires_vision,
                requires_tools=requires_tools,
            )
            spec = decision.selected_model
            if not spec or spec.id in tried_ids:
                break
            tried_ids.add(spec.id)

            t0 = time.monotonic()
            try:
                result = caller_fn(spec)
                latency_ms = (time.monotonic() - t0) * 1000.0
                self.record_success(spec.id, latency_ms)
                return result, decision
            except Exception as exc:
                err_str = str(exc).lower()
                cat = ErrorCategory.UNKNOWN
                if "429" in err_str or "quota" in err_str or "rate limit" in err_str:
                    cat = ErrorCategory.RATE_LIMIT
                elif "503" in err_str or "overloaded" in err_str:
                    cat = ErrorCategory.OVERLOADED
                elif "401" in err_str or "403" in err_str or "auth" in err_str or "api key" in err_str:
                    cat = ErrorCategory.AUTH_ERROR
                elif "timeout" in err_str or "timed out" in err_str:
                    cat = ErrorCategory.TIMEOUT

                self.record_failure(spec.id, cat, str(exc))

        raise RuntimeError(f"All model candidates failed after {attempt} attempts: {tried_ids}")

    def reset_cooldowns(self) -> None:
        """Reset all model cooldowns to test or recover immediately."""
        with self._lock:
            for h in self._health.values():
                h.cooldown_until = 0.0
                h.consecutive_failures = 0
                h.auth_valid = True


# ── Global Singleton ─────────────────────────────────────────────────────────

_router: Optional[ModelRouter] = None
_router_lock = threading.Lock()


def get_model_router() -> ModelRouter:
    global _router
    with _router_lock:
        if _router is None:
            _router = ModelRouter()
        return _router
