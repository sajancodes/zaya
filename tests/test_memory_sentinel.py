"""Tests for System Memory Leak & Process RAM Footprint Sentinel."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch
import pytest

from actions.memory_sentinel import (
    memory_sentinel,
    get_virtual_memory_stats,
    get_top_memory_consumers,
    assess_memory_pressure,
    TOOL,
)
from core.execution_policy import set_trust, TRUST_LOCAL_OWNER, TRUST_UNKNOWN
from core.fast_reflex import FastReflexRouter


@pytest.fixture(autouse=True)
def _owner_trust():
    set_trust(TRUST_LOCAL_OWNER)
    yield
    set_trust(TRUST_LOCAL_OWNER)


def test_owner_security_gate():
    set_trust(TRUST_UNKNOWN)
    with pytest.raises(PermissionError):
        memory_sentinel({"action": "summary"})


def test_tool_declaration():
    assert TOOL["name"] == "memory_sentinel"
    assert "parameters" in TOOL
    assert callable(TOOL["handler"])


@patch("psutil.swap_memory")
@patch("psutil.virtual_memory")
def test_get_virtual_memory_stats(mock_vm, mock_swap):
    mock_vm.return_value = MagicMock(
        total=16 * (1024**3),
        used=8 * (1024**3),
        available=8 * (1024**3),
        percent=50.0,
    )
    mock_swap.return_value = MagicMock(
        total=4 * (1024**3),
        used=1 * (1024**3),
        free=3 * (1024**3),
        percent=25.0,
    )

    stats = get_virtual_memory_stats()
    assert stats["ram_total_gb"] == 16.0
    assert stats["ram_used_gb"] == 8.0
    assert stats["ram_percent"] == 50.0
    assert stats["swap_percent"] == 25.0


@patch("psutil.virtual_memory")
@patch("psutil.process_iter")
def test_get_top_memory_consumers_grouped(mock_piter, mock_vm):
    mock_vm.return_value = MagicMock(total=16 * (1024**3))

    p1 = MagicMock(info={"name": "msedge.exe", "pid": 101, "memory_info": MagicMock(rss=500 * (1024**2))})
    p2 = MagicMock(info={"name": "msedge.exe", "pid": 102, "memory_info": MagicMock(rss=300 * (1024**2))})
    p3 = MagicMock(info={"name": "python.exe", "pid": 201, "memory_info": MagicMock(rss=400 * (1024**2))})
    mock_piter.return_value = [p1, p2, p3]

    top = get_top_memory_consumers(limit=5, group_by_name=True)
    assert len(top) == 2
    # msedge should be first with aggregated 800 MB and count 2
    assert top[0]["application"] == "msedge.exe"
    assert top[0]["process_count"] == 2
    assert top[0]["memory_mb"] == 800.0

    assert top[1]["application"] == "python.exe"
    assert top[1]["process_count"] == 1
    assert top[1]["memory_mb"] == 400.0


@patch("psutil.virtual_memory")
@patch("psutil.process_iter")
def test_get_top_memory_consumers_individual(mock_piter, mock_vm):
    mock_vm.return_value = MagicMock(total=16 * (1024**3))

    p1 = MagicMock(info={"name": "msedge.exe", "pid": 101, "memory_info": MagicMock(rss=500 * (1024**2))})
    p2 = MagicMock(info={"name": "msedge.exe", "pid": 102, "memory_info": MagicMock(rss=300 * (1024**2))})
    mock_piter.return_value = [p1, p2]

    top = get_top_memory_consumers(limit=5, group_by_name=False)
    assert len(top) == 2
    assert top[0]["pid"] == 101
    assert top[1]["pid"] == 102


@patch("actions.memory_sentinel.get_top_memory_consumers")
@patch("actions.memory_sentinel.get_virtual_memory_stats")
def test_assess_memory_pressure_healthy(mock_stats, mock_top):
    mock_stats.return_value = {
        "ram_percent": 50.0,
        "ram_available_gb": 8.0,
        "swap_percent": 20.0,
    }
    mock_top.return_value = [{"application": "msedge.exe", "memory_mb": 500.0}]

    pressure = assess_memory_pressure()
    assert pressure["status_code"] == "healthy"
    assert "Healthy" in pressure["pressure_level"]


@patch("actions.memory_sentinel.get_top_memory_consumers")
@patch("actions.memory_sentinel.get_virtual_memory_stats")
def test_assess_memory_pressure_critical(mock_stats, mock_top):
    mock_stats.return_value = {
        "ram_percent": 92.0,
        "ram_available_gb": 0.8,
        "swap_percent": 85.0,
    }
    mock_top.return_value = [{"application": "heavy_app.exe", "memory_mb": 4000.0}]

    pressure = assess_memory_pressure()
    assert pressure["status_code"] == "critical"
    assert "Critical" in pressure["pressure_level"]


def test_memory_sentinel_actions():
    res_raw = memory_sentinel({"action": "summary"})
    res = json.loads(res_raw)
    assert res["status"] == "success"
    assert "data" in res

    stats_raw = memory_sentinel({"action": "stats"})
    stats = json.loads(stats_raw)
    assert stats["status"] == "success"
    assert "stats" in stats

    err_raw = memory_sentinel({"action": "invalid"})
    err = json.loads(err_raw)
    assert err["status"] == "error"


def test_fast_reflex_memory_analysis():
    router = FastReflexRouter()
    intent, score = router.match("memory breakdown")
    assert intent == "MEMORY_ANALYSIS_QUERY"
    assert score >= 0.88

    res = router.execute_intent("MEMORY_ANALYSIS_QUERY")
    assert res.matched is True
    assert "RAM Status:" in res.ack
