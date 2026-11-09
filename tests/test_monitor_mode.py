"""Tests for Monitor Mode — periodic screen surveillance engine.
Created and developed by Sajan Rai for Zaya.
"""
from __future__ import annotations

import os
import threading
import time
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("TRUST_LOCAL_OWNER", "1")

from core.monitor_mode import (
    MonitorModeEngine,
    MonitorSession,
    Observation,
    DEFAULT_INTERVAL_SEC,
    MIN_INTERVAL_SEC,
    MAX_INTERVAL_SEC,
    MAX_OBSERVATIONS,
)


# ── Helpers ─────────────────────────────────────────────────────────────────

def _fake_capture() -> bytes:
    """Return tiny fake PNG bytes."""
    return b"\x89PNG fake screenshot bytes"


def _fake_analyse(png_bytes: bytes, task: str) -> dict:
    """Simple analysis stub."""
    return {
        "summary": f"Screen looks normal for: {task}",
        "needs_attention": False,
        "raw_ocr": "hello world",
    }


def _alert_analyse(png_bytes: bytes, task: str) -> dict:
    """Analysis stub that always flags attention."""
    return {
        "summary": f"BUILD FAILED for: {task}",
        "needs_attention": True,
        "raw_ocr": "error: build failed",
    }


# ── Tests ───────────────────────────────────────────────────────────────────

class TestMonitorSession:
    def test_session_defaults(self):
        s = MonitorSession(task="test build")
        assert s.active is False
        assert s.task == "test build"
        assert s.interval_sec == DEFAULT_INTERVAL_SEC
        assert len(s.observations) == 0

    def test_session_summary(self):
        s = MonitorSession(task="deploy check", active=True)
        summary = s.summary()
        assert summary["task"] == "deploy check"
        assert summary["active"] is True
        assert "elapsed_sec" in summary

    def test_elapsed_calculation(self):
        s = MonitorSession(task="test", started_at=100.0, stopped_at=200.0)
        assert s.elapsed() == 100.0


class TestMonitorModeEngine:
    def test_start_and_stop_lifecycle(self):
        notifications = []
        engine = MonitorModeEngine(
            capture_fn=_fake_capture,
            analyse_fn=_fake_analyse,
            notify_fn=lambda t: notifications.append(t),
        )
        session = engine.start("build progress", interval_sec=MIN_INTERVAL_SEC, max_duration_sec=120)
        assert session.active is True
        assert session.task == "build progress"

        # Let it run for a moment
        time.sleep(0.2)
        status = engine.status()
        assert status["active"] is True

        # Stop
        result = engine.stop()
        assert result is not None
        assert result.active is False
        assert result.stopped_at is not None

    def test_cannot_start_while_active(self):
        engine = MonitorModeEngine(
            capture_fn=_fake_capture,
            analyse_fn=_fake_analyse,
        )
        engine.start("task A", interval_sec=MIN_INTERVAL_SEC)
        with pytest.raises(RuntimeError, match="Already monitoring"):
            engine.start("task B")
        engine.stop()

    def test_empty_task_raises(self):
        engine = MonitorModeEngine(
            capture_fn=_fake_capture,
            analyse_fn=_fake_analyse,
        )
        with pytest.raises(ValueError, match="Describe"):
            engine.start("")

    def test_interval_clamping(self):
        engine = MonitorModeEngine(
            capture_fn=_fake_capture,
            analyse_fn=_fake_analyse,
        )
        session = engine.start("test", interval_sec=1)  # below minimum
        assert session.interval_sec == MIN_INTERVAL_SEC
        engine.stop()

        session = engine.start("test2", interval_sec=99999)  # above maximum
        assert session.interval_sec == MAX_INTERVAL_SEC
        engine.stop()

    def test_adjust_interval(self):
        engine = MonitorModeEngine(
            capture_fn=_fake_capture,
            analyse_fn=_fake_analyse,
        )
        engine.start("test", interval_sec=60)
        result = engine.adjust_interval(120)
        assert result["interval_sec"] == 120
        engine.stop()

    def test_adjust_without_session_raises(self):
        engine = MonitorModeEngine(
            capture_fn=_fake_capture,
            analyse_fn=_fake_analyse,
        )
        with pytest.raises(RuntimeError, match="No active"):
            engine.adjust_interval(60)

    def test_alert_notification(self):
        notifications = []
        engine = MonitorModeEngine(
            capture_fn=_fake_capture,
            analyse_fn=_alert_analyse,
            notify_fn=lambda t: notifications.append(t),
        )
        # Use very short interval for testing
        session = engine.start("build", interval_sec=MIN_INTERVAL_SEC, max_duration_sec=120)

        # Wait for at least one capture cycle
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and not notifications:
            time.sleep(0.1)

        engine.stop()
        assert len(notifications) >= 1
        assert "Monitor Alert" in notifications[0]
        assert session.alerts_raised >= 1

    def test_max_duration_stops_session(self):
        notifications = []
        engine = MonitorModeEngine(
            capture_fn=_fake_capture,
            analyse_fn=_fake_analyse,
            notify_fn=lambda t: notifications.append(t),
        )
        # Very short max duration without clamping
        session = engine.start("test", interval_sec=1, max_duration_sec=1, _clamp=False)

        # Wait for it to self-stop
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and session.active:
            time.sleep(0.1)

        assert session.active is False
        assert session.stopped_at is not None

    def test_history_tracking(self):
        engine = MonitorModeEngine(
            capture_fn=_fake_capture,
            analyse_fn=_fake_analyse,
        )
        engine.start("task1", interval_sec=1, max_duration_sec=1, _clamp=False)
        # Wait for natural stop
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if not engine.status().get("active"):
                break
            time.sleep(0.1)

        history = engine.history()
        assert len(history) >= 1
        assert history[-1]["task"] == "task1"

    def test_capture_failure_graceful(self):
        """Engine handles capture exceptions gracefully."""
        def failing_capture():
            raise OSError("Display not available")

        engine = MonitorModeEngine(
            capture_fn=failing_capture,
            analyse_fn=_fake_analyse,
        )
        session = engine.start("test", interval_sec=MIN_INTERVAL_SEC, max_duration_sec=60)
        time.sleep(0.5)
        engine.stop()
        # Should not crash — just no observations
        assert session.active is False

    def test_status_no_session(self):
        engine = MonitorModeEngine()
        status = engine.status()
        assert status["active"] is False
        assert "No monitoring" in status.get("message", "")


class TestMonitorModeAction:
    def test_action_start_stop(self):
        from actions.monitor_mode_action import monitor_mode
        result = monitor_mode({"action": "start", "task": "build check", "interval_minutes": 1})
        assert result.status == "success"
        assert "Monitor started" in result.summary

        result = monitor_mode({"action": "status"})
        assert result.status == "success"

        result = monitor_mode({"action": "stop"})
        assert result.status == "success"

    def test_action_start_no_task(self):
        from actions.monitor_mode_action import monitor_mode
        result = monitor_mode({"action": "start"})
        assert result.status == "failed"

    def test_action_unknown(self):
        from actions.monitor_mode_action import monitor_mode
        result = monitor_mode({"action": "unknown_action"})
        assert result.status == "failed"
