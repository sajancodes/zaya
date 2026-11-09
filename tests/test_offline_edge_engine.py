"""Tests for Hybrid Offline Edge Engine and Local Intent Classifier.
Created and developed by Sajan Rai for Zaya.
"""
from __future__ import annotations

import os
from unittest.mock import patch, MagicMock

import pytest

os.environ.setdefault("TRUST_LOCAL_OWNER", "1")

from core.offline_edge_engine import OfflineEdgeEngine
from actions.offline_edge_action import offline_edge_action
from core.tool_result import ToolResult


class TestOfflineEdgeEngine:
    def test_volume_intents_matching(self):
        engine = OfflineEdgeEngine()

        m1 = engine.match("mute volume")
        assert m1 is not None
        assert m1.tool_name == "volume_control"
        assert m1.parameters == {"action": "mute"}

        m2 = engine.match("set volume to 65%")
        assert m2 is not None
        assert m2.parameters == {"action": "set", "level": 65}

        m3 = engine.match("please unmute")
        assert m3 is not None
        assert m3.parameters == {"action": "unmute"}

    def test_spatial_layout_intents(self):
        engine = OfflineEdgeEngine()

        m = engine.match("set windows in split mode")
        assert m is not None
        assert m.tool_name == "spatial_layout"
        assert m.parameters["preset"] == "split_code"

        m_quad = engine.match("arrange quad layout")
        assert m_quad is not None
        assert m_quad.parameters["preset"] == "quad"

    def test_screen_capture_and_monitor_intents(self):
        engine = OfflineEdgeEngine()

        m_shot = engine.match("take a screenshot")
        assert m_shot is not None
        assert m_shot.tool_name == "screen_peeler"

        m_mon = engine.match("stop the monitor")
        assert m_mon is not None
        assert m_mon.tool_name == "monitor_mode"
        assert m_mon.parameters["action"] == "stop"

    def test_non_local_queries_pass_through(self):
        engine = OfflineEdgeEngine()

        # Questions requiring cloud LLM reasoning
        assert engine.match("What is quantum computing?") is None
        assert engine.match("Write a python script to parse CSV") is None
        assert engine.match("Tell me a funny story about robots") is None

    def test_execute_locally_speed_and_dispatch(self):
        engine = OfflineEdgeEngine()

        with patch("core.action_loader.execute_tool") as mock_exec:
            mock_exec.return_value = ToolResult("success", "Volume muted.")
            handled, res, latency_ms = engine.execute_locally("mute")

            assert handled is True
            assert res.status == "success"
            assert latency_ms < 50.0  # extremely fast local execution


class TestOfflineEdgeAction:
    def test_action_handled_locally(self):
        with patch("core.action_loader.execute_tool") as mock_exec:
            mock_exec.return_value = ToolResult("success", "Screenshot captured.")
            res = offline_edge_action({"utterance": "capture the screen"})
            assert res.status == "success"
            assert "Offline Edge:" in res.summary
            assert res.data["handled_locally"] is True

    def test_action_unhandled_passes_to_cloud(self):
        res = offline_edge_action({"utterance": "Explain general relativity"})
        assert res.status == "partial"
        assert res.data["handled_locally"] is False
