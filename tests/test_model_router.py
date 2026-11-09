"""Tests for Intelligent Model Routing and Dynamic Health Registry.
Created and developed by Sajan Rai for Zaya.
"""
from __future__ import annotations

import os
import time
import pytest

os.environ.setdefault("TRUST_LOCAL_OWNER", "1")

from core.model_router import (
    ComplexityTier,
    ErrorCategory,
    ModelHealth,
    ModelRouter,
    ModelSpec,
    Provider,
    RoutingDecision,
)
from actions.model_routing_action import model_routing_action


@pytest.fixture
def test_router():
    models = [
        ModelSpec("fast-flash", "Fast Flash", Provider.GEMINI, complexity_rank=2, cost_tier=1, priority=1, supports_vision=True),
        ModelSpec("deep-pro", "Deep Pro", Provider.GEMINI, complexity_rank=4, cost_tier=2, priority=2, supports_vision=True),
        ModelSpec("local-llama", "Local Llama", Provider.OLLAMA, complexity_rank=1, cost_tier=0, priority=3, supports_vision=False),
        ModelSpec("groq-fast", "Groq Instant", Provider.GROQ, complexity_rank=2, cost_tier=1, priority=4, supports_vision=False),
    ]
    return ModelRouter(models)


class TestModelRouter:
    def test_route_standard_task(self, test_router):
        decision = test_router.route(complexity=ComplexityTier.STANDARD)
        assert decision.selected_model is not None
        assert decision.selected_model.id == "fast-flash"
        assert "Selected Fast Flash" in decision.reason

    def test_route_deep_reasoning_task(self, test_router):
        decision = test_router.route(complexity=ComplexityTier.REASONING)
        assert decision.selected_model is not None
        assert decision.selected_model.id == "deep-pro"

    def test_route_requires_vision_filters_non_vision(self, test_router):
        # Even if low complexity, only vision-capable models can be chosen
        decision = test_router.route(complexity=ComplexityTier.LIGHT, requires_vision=True)
        assert decision.selected_model is not None
        assert decision.selected_model.supports_vision is True

    def test_rate_limit_triggers_cooldown_and_fallback(self, test_router):
        # Initial route chooses fast-flash
        d1 = test_router.route(complexity=ComplexityTier.STANDARD)
        assert d1.selected_model.id == "fast-flash"

        # Record a 429 rate limit
        test_router.record_failure("fast-flash", ErrorCategory.RATE_LIMIT, "429 Too Many Requests")

        # Next route automatically routes around fast-flash to deep-pro or groq-fast
        d2 = test_router.route(complexity=ComplexityTier.STANDARD)
        assert d2.selected_model.id != "fast-flash"
        assert d2.selected_model.id in {"deep-pro", "groq-fast"}

    def test_auth_error_permanently_blocks_until_reset(self, test_router):
        test_router.record_failure("deep-pro", ErrorCategory.AUTH_ERROR, "Invalid API key")
        health = test_router.get_health("deep-pro")
        assert health.auth_valid is False

        # Deep reasoning should skip deep-pro
        d = test_router.route(complexity=ComplexityTier.REASONING)
        assert d.selected_model.id != "deep-pro"

    def test_latency_telemetry_and_moving_average(self, test_router):
        test_router.record_success("fast-flash", latency_ms=100.0)
        h = test_router.get_health("fast-flash")
        assert h.average_latency_ms == 100.0

        test_router.record_success("fast-flash", latency_ms=200.0)
        # 100 * 0.7 + 200 * 0.3 = 70 + 60 = 130
        assert round(h.average_latency_ms, 1) == 130.0

    def test_execute_with_fallback_recovers(self, test_router):
        attempts = []

        def mock_caller(spec: ModelSpec):
            attempts.append(spec.id)
            if spec.id == "fast-flash":
                raise RuntimeError("429 Quota Exceeded")
            return f"Success with {spec.id}"

        result, decision = test_router.execute_with_fallback(
            mock_caller, complexity=ComplexityTier.STANDARD
        )
        assert result.startswith("Success with")
        assert attempts[0] == "fast-flash"
        assert len(attempts) == 2


class TestModelRoutingAction:
    def test_action_list(self):
        res = model_routing_action({"action": "list"})
        assert res.status == "success"
        assert "Model Router:" in res.summary

    def test_action_route_simulation(self):
        res = model_routing_action({"action": "route", "complexity": "reasoning"})
        assert res.status == "success"
        assert "selected_model" in res.data

    def test_action_enable_disable(self):
        res = model_routing_action({"action": "disable", "model_id": "gemini-2.5-flash"})
        assert res.status == "success"
        assert "disabled" in res.summary

        res = model_routing_action({"action": "enable", "model_id": "gemini-2.5-flash"})
        assert res.status == "success"
        assert "enabled" in res.summary
