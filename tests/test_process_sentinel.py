"""Unit tests for Process Resource Sentinel & Unresponsive Window Detector.
Created and developed by Sajan Rai for Zaya.
"""
from __future__ import annotations

import json
import os
from unittest.mock import MagicMock, patch
import pytest

from actions.process_sentinel import (
    TOOL,
    _CRITICAL_SYSTEM_PROCESSES,
    _detect_hung_windows,
    _find_anomalies,
    _get_top_cpu,
    _get_top_memory,
    _terminate_process_safe,
    process_sentinel,
)
from core.execution_policy import TRUST_EXTERNAL_MESSAGE, TRUST_LOCAL_OWNER, with_trust
from core.fast_reflex import FastReflexRouter
from core.tools.routing import ToolRouter


def test_process_sentinel_requires_owner():
    with with_trust(TRUST_EXTERNAL_MESSAGE):
        with pytest.raises(PermissionError):
            process_sentinel({"action": "summary"})


def test_process_sentinel_top_cpu():
    with with_trust(TRUST_LOCAL_OWNER):
        res_raw = process_sentinel({"action": "top_cpu", "limit": 3})
        res = json.loads(res_raw)
        assert res["status"] == "success"
        assert "Top CPU consumers:" in res["summary"]
        assert isinstance(res["data"], list)
        if res["data"]:
            assert "name" in res["data"][0]
            assert "cpu_percent" in res["data"][0]


def test_process_sentinel_top_memory():
    with with_trust(TRUST_LOCAL_OWNER):
        res_raw = process_sentinel({"action": "top_memory", "limit": 3})
        res = json.loads(res_raw)
        assert res["status"] == "success"
        assert "Top Memory consumers:" in res["summary"]
        assert isinstance(res["data"], list)
        if res["data"]:
            assert "name" in res["data"][0]
            assert "memory_mb" in res["data"][0]


def test_process_sentinel_not_responding():
    with with_trust(TRUST_LOCAL_OWNER):
        res_raw = process_sentinel({"action": "not_responding"})
        res = json.loads(res_raw)
        assert res["status"] == "success"
        assert "unresponsive" in res["summary"] or "No frozen" in res["summary"]


def test_process_sentinel_anomalies():
    with patch("actions.process_sentinel._find_anomalies") as mock_anom:
        # 1. No anomalies
        mock_anom.return_value = []
        with with_trust(TRUST_LOCAL_OWNER):
            res_raw = process_sentinel({
                "action": "anomalies",
                "cpu_threshold": 80.0,
                "memory_mb_threshold": 4096.0,
            })
            res = json.loads(res_raw)
            assert res["status"] == "success"
            assert "No resource anomalies detected" in res["summary"]

        # 2. Anomalies detected
        mock_anom.return_value = [{
            "pid": 9999,
            "name": "rogue_miner.exe",
            "cpu_percent": 98.5,
            "memory_mb": 4500.0,
            "threads": 64,
            "reasons": ["High CPU: 98.5% >= 80.0%"],
        }]
        with with_trust(TRUST_LOCAL_OWNER):
            res_raw = process_sentinel({
                "action": "anomalies",
                "cpu_threshold": 80.0,
            })
            res = json.loads(res_raw)
            assert res["status"] == "success"
            assert "Detected 1 resource anomaly/hogs" in res["summary"]
            assert "rogue_miner.exe" in res["summary"]


def test_process_sentinel_summary():
    with with_trust(TRUST_LOCAL_OWNER):
        res_raw = process_sentinel({"action": "summary"})
        res = json.loads(res_raw)
        assert res["status"] == "success"
        assert "Process Sentinel:" in res["summary"]
        assert "top_cpu" in res["data"]
        assert "top_memory" in res["data"]


def test_process_sentinel_safe_termination_blocks_critical():
    with with_trust(TRUST_LOCAL_OWNER):
        # Attempt to kill critical system process by name
        res_raw = process_sentinel({"action": "kill_safe", "name": "csrss.exe"})
        res = json.loads(res_raw)
        assert res["status"] == "error"
        assert "protected system process" in res["message"]


def test_process_sentinel_safe_termination_blocks_self():
    with with_trust(TRUST_LOCAL_OWNER):
        # Attempt to kill Zaya's own PID
        res_raw = process_sentinel({"action": "kill_safe", "pid": os.getpid()})
        res = json.loads(res_raw)
        assert res["status"] == "error"
        assert "Cannot terminate current Zaya process" in res["message"]


def test_process_sentinel_safe_termination_nonexistent_pid():
    with with_trust(TRUST_LOCAL_OWNER):
        res_raw = process_sentinel({"action": "kill_safe", "pid": 9999999})
        res = json.loads(res_raw)
        assert res["status"] == "error"
        assert "not found" in res["message"]


def test_tool_declaration_schema():
    assert TOOL["name"] == "process_sentinel"
    assert "top_cpu" in TOOL["parameters"]["properties"]["action"]["enum"]
    assert "not_responding" in TOOL["parameters"]["properties"]["action"]["enum"]
    assert callable(TOOL["handler"])


def test_fast_reflex_process_sentinel():
    router = FastReflexRouter()
    
    intent, score = router.match("what's using the most cpu")
    assert intent == "TOP_CPU_QUERY"
    assert score >= 0.88

    intent, score = router.match("any frozen apps")
    assert intent == "NOT_RESPONDING_QUERY"
    assert score >= 0.88

    res_cpu = router.execute_intent("TOP_CPU_QUERY")
    assert res_cpu.matched is True
    assert "Top CPU process is" in res_cpu.ack

    res_hung = router.execute_intent("NOT_RESPONDING_QUERY")
    assert res_hung.matched is True
    assert "No frozen or unresponsive" in res_hung.ack or "Detected" in res_hung.ack


def test_tool_router_maps_process_sentinel():
    router = ToolRouter()
    declarations = [
        {"name": "process_sentinel", "description": "inspect process hogs and hung windows"},
        {"name": "web_search", "description": "search web"},
    ]
    routed = router.route("find hung frozen apps and kill process hogs", declarations)
    names = [d["name"] for d in routed.declarations]
    assert "process_sentinel" in names
