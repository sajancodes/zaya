"""Tests for Continuous Screen Monitor using Gemini Robotics ER-2 Streaming Model.
Created and developed by Sajan Rai for Zaya.
"""
from __future__ import annotations

import json
import time
from unittest.mock import MagicMock, patch
import pytest

from core.robotics_monitor import (
    ROBOTICS_MODEL,
    RoboticsObservation,
    RoboticsScreenMonitorEngine,
    _compute_frame_delta,
    get_robotics_screen_monitor,
)
from actions.robotics_monitor_action import handle_robotics_screen_monitor


class TestRoboticsScreenMonitor:
    def test_model_id_default(self):
        monitor = RoboticsScreenMonitorEngine()
        assert monitor.model_id == "models/gemini-robotics-er-2-streaming-preview"
        assert monitor.interval_sec >= 1.0

    def test_compute_frame_delta(self):
        # Identical frames have 0.0 delta
        frame_a = b"\x89PNG\r\n\x1a\n" + b"\x00" * 200
        assert _compute_frame_delta(frame_a, frame_a) == 0.0

        # Completely different frames have high delta
        frame_b = b"\x89PNG\r\n\x1a\n" + b"\xff" * 200
        delta = _compute_frame_delta(frame_a, frame_b)
        assert delta > 0.50

        # Empty / None frame
        assert _compute_frame_delta(None, frame_a) == 1.0

    def test_analyze_frame_with_mock_gemini(self):
        monitor = RoboticsScreenMonitorEngine()

        mock_payload = {
            "active_app": "Visual Studio Code",
            "summary": "Building Zaya test suite in terminal.",
            "state_transition": "Compilation failed with 1 syntax error on line 45.",
            "needs_attention": True,
            "attention_reason": "SyntaxError in core/example.py",
            "actionable_elements": [
                {"label": "Run Build Again", "bounding_box_normalized": [200, 300, 240, 420]}
            ],
            "action_suggestion": "Fix line 45 and restart build.",
        }

        mock_resp = MagicMock()
        mock_resp.text = json.dumps(mock_payload)

        with patch("core.gemini.call", return_value=mock_resp):
            fake_png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 50
            obs = monitor.analyze_frame(fake_png, task="Monitor build")

            assert obs.active_app == "Visual Studio Code"
            assert obs.needs_attention is True
            assert "SyntaxError" in obs.attention_reason
            assert len(obs.actionable_elements) == 1
            assert obs.model_used == ROBOTICS_MODEL

    def test_analyze_frame_fallback_ocr(self):
        monitor = RoboticsScreenMonitorEngine()

        # Simulate gemini.call failing or returning None
        with patch("core.gemini.call", return_value=None), \
             patch("actions.screen_peeler._ocr_via_powershell", return_value="CRITICAL ERROR: memory access violation"):
            fake_png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 50
            obs = monitor.analyze_frame(fake_png, task="Watch for crash")

            assert obs.needs_attention is True
            assert "error" in obs.attention_reason.lower()
            assert obs.model_used == "heuristic-ocr-fallback"

    def test_monitor_background_loop(self):
        alerts = []
        frames = [
            b"\x89PNG\r\n\x1a\n" + b"\x11" * 100,
            b"\x89PNG\r\n\x1a\n" + b"\x99" * 100,  # Delta change
        ]
        frame_idx = 0

        def fake_capture():
            nonlocal frame_idx
            if frame_idx < len(frames):
                f = frames[frame_idx]
                frame_idx += 1
                return f
            return frames[-1]

        def fake_notify(msg):
            alerts.append(msg)

        monitor = RoboticsScreenMonitorEngine(
            interval_sec=0.02,
            capture_fn=fake_capture,
            notify_fn=fake_notify,
        )

        mock_payload = {
            "active_app": "Terminal",
            "summary": "Task failed",
            "state_transition": "Exited with code 1",
            "needs_attention": True,
            "attention_reason": "Build failure",
            "actionable_elements": [],
            "action_suggestion": "Check error log",
        }
        mock_resp = MagicMock()
        mock_resp.text = json.dumps(mock_payload)

        with patch("core.execution_policy.require_owner"), \
             patch("core.gemini.call", return_value=mock_resp):

            start_res = monitor.start(task_objective="Test build monitor", interval_sec=0.02, max_duration_sec=2)
            assert start_res["status"] == "started"

            # Wait briefly for background thread to record at least 1 observation
            for _ in range(20):
                if monitor.status()["total_observations"] >= 1:
                    break
                time.sleep(0.05)

            st = monitor.status()
            assert st["active"] is True
            assert st["total_observations"] >= 1

            stop_res = monitor.stop()
            assert stop_res["status"] == "stopped"
            assert monitor.status()["active"] is False


class TestRoboticsMonitorAction:
    def test_action_status_and_observe_now(self):
        with patch("core.execution_policy.require_owner"):
            # Status
            res = handle_robotics_screen_monitor(action="status")
            data = json.loads(res)
            assert data["status"] == "success"
            assert "monitor_status" in data
            assert data["monitor_status"]["model"] == "models/gemini-robotics-er-2-streaming-preview"

            # Set interval
            res2 = handle_robotics_screen_monitor(action="set_interval", interval_sec=5.0)
            data2 = json.loads(res2)
            assert data2["status"] == "success"
            assert data2["interval_sec"] == 5.0

            # Observe now with simulated capture
            fake_png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 200
            with patch("actions.screen_peeler.capture_screen_region", return_value=fake_png), \
                 patch("core.gemini.call") as mock_call:
                mock_resp = MagicMock()
                mock_resp.text = json.dumps({
                    "active_app": "Browser",
                    "summary": "Viewing dashboard",
                    "state_transition": "Page loaded",
                    "needs_attention": False,
                })
                mock_call.return_value = mock_resp

                res3 = handle_robotics_screen_monitor(action="observe_now", task="Inspect page")
                data3 = json.loads(res3)
                assert data3["status"] == "success"
                assert "observation" in data3
                assert data3["observation"]["active_app"] == "Browser"
