"""Tests for Metacognitive Engine and Metacognition Action.
Created and developed by Sajan Rai for Zaya.
"""
from __future__ import annotations

import tempfile
from pathlib import Path
import pytest

from core.execution_policy import TRUST_EXTERNAL_MESSAGE, with_trust
from core.metacognition import MetacognitiveEngine
from actions.metacognition_action import metacognition


@pytest.fixture
def temp_metacog():
    with tempfile.TemporaryDirectory() as td:
        storage_path = Path(td) / "test_tool_reliability.json"
        engine = MetacognitiveEngine(storage_path=storage_path)
        yield engine


def test_recording_and_metrics_calculation(temp_metacog):
    engine = temp_metacog
    # Record two successes
    engine.record_execution("repo_sentinel", duration_ms=100.0, success=True)
    engine.record_execution("repo_sentinel", duration_ms=200.0, success=True)

    h = engine.check_tool_health("repo_sentinel")
    assert h["status"] == "healthy"
    assert h["can_execute"] is True
    assert h["success_rate"] == 1.0
    assert h["avg_latency_ms"] == 150.0


def test_circuit_breaker_tripping_and_reset(temp_metacog):
    engine = temp_metacog
    # 1 failure -> healthy
    engine.record_execution("flaky_api", duration_ms=50.0, success=False, error_message="Timeout")
    assert engine.check_tool_health("flaky_api")["status"] == "healthy"

    # 2 failures -> degraded
    engine.record_execution("flaky_api", duration_ms=50.0, success=False, error_message="Timeout")
    assert engine.check_tool_health("flaky_api")["status"] == "degraded"

    # 3 failures -> tripped
    engine.record_execution("flaky_api", duration_ms=50.0, success=False, error_message="Timeout")
    h_tripped = engine.check_tool_health("flaky_api")
    assert h_tripped["status"] == "tripped"
    assert h_tripped["can_execute"] is False

    # Manual reset
    ok = engine.reset_tool("flaky_api")
    assert ok is True
    assert engine.check_tool_health("flaky_api")["status"] == "healthy"


def test_diagnostic_report_generation(temp_metacog):
    engine = temp_metacog
    engine.record_execution("tool_a", duration_ms=50.0, success=True)
    engine.record_execution("tool_b", duration_ms=150.0, success=False, error_message="Err")

    report = engine.generate_diagnostic_report()
    assert report["total_tools"] == 2
    assert report["healthy_count"] == 2  # tool_b has only 1 failure so still healthy
    assert report["total_invocations"] == 2
    assert report["overall_success_rate"] == 0.5


def test_metacognition_action_handler(temp_metacog, monkeypatch):
    monkeypatch.setattr("actions.metacognition_action.get_metacognitive_engine", lambda: temp_metacog)

    # Record action
    rec_res = metacognition({
        "action": "record",
        "tool": "smart_home",
        "duration_ms": 75.0,
        "success": True,
    })
    assert rec_res.status == "success"

    # Health action
    h_res = metacognition({"action": "health", "tool": "smart_home"})
    assert h_res.status == "success"
    assert h_res.data["status"] == "healthy"

    # Diagnose action
    diag_res = metacognition({"action": "diagnose"})
    assert diag_res.status == "success"
    assert "Metacognitive health" in diag_res.summary

    # Reset action
    rst_res = metacognition({"action": "reset", "tool": "smart_home"})
    assert rst_res.status == "success"

    # Unauthorized access check
    with with_trust(TRUST_EXTERNAL_MESSAGE):
        with pytest.raises(PermissionError):
            metacognition({"action": "diagnose"})
