"""Tests for the deep_process action that lets Zaya delegate to hydrogen.

The realtime conversation stays on gemini-3.8-live; this action is the explicit
bridge Zaya chooses when a request needs more reasoning than a spoken turn
should spend.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

import actions.deep_process as deep_process_action
from core import gemini
from core.action_loader import _validate


def test_tool_is_discoverable():
    record = _validate(deep_process_action.TOOL, "deep_process.py")
    assert record.valid, record.error
    assert record.name == "deep_process"
    assert record.handler is deep_process_action.deep_process


def test_description_tells_zaya_when_to_delegate():
    description = deep_process_action.TOOL["description"]
    assert "Gemini 4 Hydrogen" in description
    assert "self-contained" in description
    assert "Do not use it for simple questions" in description


def test_answer_is_returned_with_the_processing_model(monkeypatch):
    seen = {}

    def fake_call(contents, **kwargs):
        seen["contents"] = contents
        seen.update(kwargs)
        return SimpleNamespace(text="the answer", model="gemini-4-hydrogen")

    monkeypatch.setattr(gemini, "call", fake_call)
    result = deep_process_action.deep_process({"request": "audit these locks"})

    assert result.status == "success"
    assert result.summary == "the answer"
    assert result.data["model"] == gemini.PROCESS_MODEL
    assert result.data["model"] == "gemini-4-hydrogen"
    assert result.data["answered_by"] == "gemini-4-hydrogen"
    assert result.data["used_fallback"] is False
    assert seen["contents"] == "audit these locks"
    assert seen["tier"] == gemini.SMART


def test_fallback_answer_is_labelled(monkeypatch):
    monkeypatch.setattr(
        gemini, "call",
        lambda *args, **kwargs: SimpleNamespace(
            text="answer", model="models/gemini-3.8-live"))
    result = deep_process_action.deep_process({"request": "x"})
    assert result.status == "success"
    assert result.data["answered_by"] == "models/gemini-3.8-live"
    assert result.data["used_fallback"] is True


@pytest.mark.parametrize("depth,budget,timeout_ms", [
    ("quick", 256, 45_000),
    ("standard", 1024, 75_000),
    ("deep", 8192, 90_000),
])
def test_depth_controls_effort(monkeypatch, depth, budget, timeout_ms):
    seen = {}

    def fake_call(contents, **kwargs):
        seen.update(kwargs)
        return SimpleNamespace(text="ok", model="gemini-4-hydrogen")

    monkeypatch.setattr(gemini, "call", fake_call)
    deep_process_action.deep_process({"request": "x", "depth": depth})

    assert seen["config"].thinking_config.thinking_budget == budget
    assert seen["timeout_ms"] == timeout_ms


def test_unknown_depth_falls_back_to_standard(monkeypatch):
    seen = {}
    monkeypatch.setattr(
        gemini, "call",
        lambda contents, **kwargs: seen.update(kwargs) or SimpleNamespace(
            text="ok", model="gemini-4-hydrogen"))
    deep_process_action.deep_process({"request": "x", "depth": "enormous"})
    assert seen["timeout_ms"] == 75_000


def test_empty_request_does_not_call_the_model(monkeypatch):
    called = []
    monkeypatch.setattr(
        gemini, "call", lambda *args, **kwargs: called.append(1))
    result = deep_process_action.deep_process({"request": "   "})
    assert result.status == "failed"
    assert called == []


def test_empty_answer_is_a_retryable_failure(monkeypatch):
    monkeypatch.setattr(gemini, "call", lambda *args, **kwargs: None)
    result = deep_process_action.deep_process({"request": "x"})
    assert result.status == "failed"
    assert result.retryable
    assert result.data["model"] == "gemini-4-hydrogen"


def test_model_error_is_reported_instead_of_raising(monkeypatch):
    def broken(*args, **kwargs):
        raise RuntimeError("hydrogen is down")

    monkeypatch.setattr(gemini, "call", broken)
    result = deep_process_action.deep_process({"request": "x"})
    assert result.status == "failed"
    assert result.retryable
    assert "hydrogen is down" in result.summary
