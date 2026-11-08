"""Tests for Hardware Thermal, GPU Sensor & CPU Frequency Sentinel."""
import json
import pytest
from unittest.mock import MagicMock, patch

from actions.thermal_sentinel import (
    thermal_sentinel,
    _query_nvidia_smi,
    _query_cpu_telemetry,
    TOOL,
)
from core.execution_policy import set_trust, TRUST_LOCAL_OWNER, TRUST_UNKNOWN


@pytest.fixture(autouse=True)
def ensure_owner_trust():
    set_trust(TRUST_LOCAL_OWNER)
    yield
    set_trust(TRUST_LOCAL_OWNER)


def test_tool_declaration():
    assert TOOL["name"] == "thermal_sentinel"
    assert "thermal" in TOOL["description"].lower()
    assert callable(TOOL["handler"])


def test_query_nvidia_smi_mocked_success():
    mock_out = "NVIDIA GeForce RTX 4070, 48, 15, 20, 8192, 6144, 2048, 45.5\n"
    mock_proc = MagicMock(returncode=0, stdout=mock_out)

    with patch("shutil.which", return_value="nvidia-smi"):
        with patch("subprocess.run", return_value=mock_proc):
            gpu = _query_nvidia_smi()
            assert gpu["available"] is True
            assert gpu["name"] == "NVIDIA GeForce RTX 4070"
            assert gpu["temperature_c"] == 48
            assert gpu["condition"] == "Cool"
            assert gpu["power_draw_w"] == 45.5
            assert gpu["vram_total_mb"] == 8192


def test_query_nvidia_smi_mocked_hot():
    mock_out = "NVIDIA GeForce RTX 3080, 85, 99, 90, 10240, 1024, 9216, 280.0\n"
    mock_proc = MagicMock(returncode=0, stdout=mock_out)

    with patch("shutil.which", return_value="nvidia-smi"):
        with patch("subprocess.run", return_value=mock_proc):
            gpu = _query_nvidia_smi()
            assert gpu["available"] is True
            assert gpu["temperature_c"] == 85
            assert "Throttling" in gpu["condition"]


def test_query_nvidia_smi_unavailable():
    with patch("shutil.which", return_value=None):
        gpu = _query_nvidia_smi()
        assert gpu["available"] is False
        assert "not found" in gpu["message"]


def test_query_cpu_telemetry_mocked():
    mock_freq = MagicMock(current=3600.0, max=4200.0, min=800.0)
    with patch("psutil.cpu_freq", return_value=mock_freq):
        with patch("psutil.cpu_percent", return_value=[20.0, 30.0, 10.0, 40.0]):
            with patch("psutil.cpu_count", return_value=4):
                cpu = _query_cpu_telemetry()
                assert cpu["current_frequency_mhz"] == 3600
                assert cpu["average_load_percent"] == 25.0
                assert len(cpu["per_core_load_percent"]) == 4


def test_thermal_sentinel_summary():
    mock_gpu = {
        "available": True,
        "name": "RTX 4050",
        "temperature_c": 42,
        "condition": "Cool",
        "power_draw_w": 12.0,
        "vram_used_mb": 1500,
        "vram_total_mb": 6000,
        "gpu_utilization_percent": 5,
    }
    mock_cpu = {
        "current_frequency_mhz": 3200,
        "logical_cores": 8,
        "average_load_percent": 15.0,
    }
    with patch("actions.thermal_sentinel._query_nvidia_smi", return_value=mock_gpu):
        with patch("actions.thermal_sentinel._query_cpu_telemetry", return_value=mock_cpu):
            res = json.loads(thermal_sentinel({"action": "summary"}))
            assert res["status"] == "success"
            assert "42°C" in res["summary"]
            assert "3.2 GHz" in res["summary"]


def test_thermal_sentinel_gpu():
    mock_gpu = {
        "available": True,
        "name": "RTX 4050",
        "temperature_c": 40,
        "condition": "Cool",
        "power_draw_w": 10.0,
        "vram_used_mb": 1000,
        "vram_total_mb": 6000,
    }
    with patch("actions.thermal_sentinel._query_nvidia_smi", return_value=mock_gpu):
        res = json.loads(thermal_sentinel({"action": "gpu"}))
        assert res["status"] == "success"
        assert "RTX 4050" in res["summary"]


def test_thermal_sentinel_cpu():
    mock_cpu = {
        "physical_cores": 4,
        "logical_cores": 8,
        "current_frequency_mhz": 3000,
        "average_load_percent": 20.0,
    }
    with patch("actions.thermal_sentinel._query_cpu_telemetry", return_value=mock_cpu):
        res = json.loads(thermal_sentinel({"action": "cpu"}))
        assert res["status"] == "success"
        assert "4 physical cores" in res["summary"]
        assert "3.0 GHz" in res["summary"]


def test_thermal_sentinel_unknown_action():
    res = json.loads(thermal_sentinel({"action": "unknown"}))
    assert res["status"] == "error"
    assert "Unknown action" in res["message"]


def test_thermal_sentinel_requires_owner():
    set_trust(TRUST_UNKNOWN)
    try:
        with pytest.raises(PermissionError):
            thermal_sentinel({"action": "summary"})
    finally:
        set_trust(TRUST_LOCAL_OWNER)


def test_thermal_sentinel_live():
    res = json.loads(thermal_sentinel({"action": "summary"}))
    assert res["status"] == "success"
    assert "cpu" in res
    assert res["cpu"]["logical_cores"] >= 1
