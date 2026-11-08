from unittest.mock import patch, MagicMock
from actions.system_diagnostics import system_diagnostics, TOOL


def test_tool_declaration():
    assert TOOL["name"] == "system_diagnostics"
    assert "battery" in TOOL["parameters"]["properties"]["action"]["enum"]
    assert "hardware" in TOOL["parameters"]["properties"]["action"]["enum"]


def test_system_diagnostics_battery():
    fake_status = {
        "cpu_percent": 15.0,
        "ram_percent": 40.0,
        "ram_used_gb": 6.0,
        "ram_total_gb": 16.0,
        "uptime": "1h 30m",
        "battery": {
            "percent": 88,
            "power_plugged": True,
            "secs_left": None,
        }
    }
    with patch("core.execution_policy.require_owner"), \
         patch("services.system_monitor.get_system_status", return_value=fake_status):
        res = system_diagnostics({"action": "battery"})
        assert res.status == "success"
        assert "88%" in res.summary
        assert "charging" in res.summary


def test_system_diagnostics_hardware():
    fake_status = {
        "cpu_percent": 22.5,
        "ram_percent": 55.0,
        "ram_used_gb": 8.8,
        "ram_total_gb": 16.0,
        "uptime": "3h 45m",
        "battery": None
    }
    with patch("core.execution_policy.require_owner"), \
         patch("services.system_monitor.get_system_status", return_value=fake_status):
        res = system_diagnostics({"action": "hardware"})
        assert res.status == "success"
        assert "CPU 22.5%" in res.summary
        assert "RAM 55.0%" in res.summary
        assert "3h 45m" in res.summary
