"""Tests for Display, Monitor & GPU Telemetry Sentinel."""
import json
import pytest
from unittest.mock import MagicMock, patch

from actions.display_sentinel import (
    display_sentinel,
    _get_display_adapters,
    _get_display_metrics,
    TOOL,
)
from core.execution_policy import set_trust, TRUST_LOCAL_OWNER, TRUST_UNKNOWN


@pytest.fixture(autouse=True)
def ensure_owner_trust():
    set_trust(TRUST_LOCAL_OWNER)
    yield
    set_trust(TRUST_LOCAL_OWNER)


def test_tool_declaration():
    assert TOOL["name"] == "display_sentinel"
    assert "resolution" in TOOL["description"].lower()
    assert callable(TOOL["handler"])


def test_get_display_metrics_mocked():
    mock_metrics = {
        "monitor_count": 2,
        "physical_width": 2560,
        "physical_height": 1440,
        "refresh_rate_hz": 165,
        "bits_per_pixel": 32,
        "logical_width": 2560,
        "logical_height": 1440,
        "dpi_scale_percent": 100,
        "virtual_desktop": {"x": 0, "y": 0, "width": 5120, "height": 1440},
        "orientation": "Landscape",
        "primary_gpu": "NVIDIA GeForce RTX 4080",
        "adapters": [{"adapter": "NVIDIA GeForce RTX 4080", "device": "\\\\.\\DISPLAY1", "primary": True, "attached": True}],
    }

    with patch("actions.display_sentinel._get_display_metrics", return_value=mock_metrics):
        res = json.loads(display_sentinel({"action": "summary"}))
        assert res["status"] == "success"
        assert "2560x1440" in res["summary"]
        assert "165Hz" in res["summary"]
        assert "RTX 4080" in res["summary"]


def test_display_sentinel_adapters():
    mock_adapters = [
        {"adapter": "NVIDIA GeForce RTX 4050", "device": "\\\\.\\DISPLAY1", "primary": True, "attached": True},
        {"adapter": "Intel Iris Xe", "device": "\\\\.\\DISPLAY2", "primary": False, "attached": False},
    ]
    with patch("actions.display_sentinel._get_display_adapters", return_value=mock_adapters):
        res = json.loads(display_sentinel({"action": "adapters"}))
        assert res["status"] == "success"
        assert "NVIDIA GeForce RTX 4050" in res["summary"]


def test_display_sentinel_geometry():
    mock_metrics = {
        "monitor_count": 1,
        "physical_width": 1920,
        "physical_height": 1080,
        "refresh_rate_hz": 144,
        "bits_per_pixel": 32,
        "logical_width": 1536,
        "logical_height": 864,
        "dpi_scale_percent": 125,
        "virtual_desktop": {"x": 0, "y": 0, "width": 1536, "height": 864},
        "orientation": "Landscape",
        "primary_gpu": "RTX 4050",
    }
    with patch("actions.display_sentinel._get_display_metrics", return_value=mock_metrics):
        res = json.loads(display_sentinel({"action": "geometry"}))
        assert res["status"] == "success"
        assert "1536x864" in res["summary"]
        assert res["virtual_desktop"]["width"] == 1536


def test_display_sentinel_unknown_action():
    res = json.loads(display_sentinel({"action": "invalid_mode"}))
    assert res["status"] == "error"
    assert "Unknown action" in res["message"]


def test_display_sentinel_requires_owner():
    set_trust(TRUST_UNKNOWN)
    try:
        with pytest.raises(PermissionError):
            display_sentinel({"action": "summary"})
    finally:
        set_trust(TRUST_LOCAL_OWNER)


def test_display_sentinel_live():
    res = json.loads(display_sentinel({"action": "summary"}))
    assert res["status"] == "success"
    assert "data" in res
    assert res["data"]["monitor_count"] >= 1
    assert res["data"]["physical_width"] > 0
    assert res["data"]["physical_height"] > 0
