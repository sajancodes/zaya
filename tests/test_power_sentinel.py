"""Tests for Battery Health & Power Hardware Sentinel."""
import json
import pytest
from unittest.mock import MagicMock, patch

from actions.power_sentinel import (
    power_sentinel,
    _get_live_battery_status,
    _parse_battery_report_xml,
    _generate_battery_health_report,
    _get_power_plans,
    TOOL,
)
from core.execution_policy import set_trust, TRUST_LOCAL_OWNER, TRUST_UNKNOWN

_SAMPLE_XML = """<?xml version="1.0" encoding="utf-8"?>
<BatteryReport xmlns="http://schemas.microsoft.com/battery/2012">
    <SystemInformation>
        <SystemManufacturer>LENOVO</SystemManufacturer>
    </SystemInformation>
    <Batteries>
        <Battery>
            <Manufacturer>Sunwoda</Manufacturer>
            <Chemistry>LiP</Chemistry>
            <DesignCapacity>60000</DesignCapacity>
            <FullChargeCapacity>54000</FullChargeCapacity>
            <CycleCount>150</CycleCount>
        </Battery>
    </Batteries>
</BatteryReport>
"""

_DEGRADED_XML = """<?xml version="1.0" encoding="utf-8"?>
<BatteryReport xmlns="http://schemas.microsoft.com/battery/2012">
    <Batteries>
        <Battery>
            <Manufacturer>Generic</Manufacturer>
            <DesignCapacity>50000</DesignCapacity>
            <FullChargeCapacity>25000</FullChargeCapacity>
            <CycleCount>600</CycleCount>
        </Battery>
    </Batteries>
</BatteryReport>
"""


@pytest.fixture(autouse=True)
def ensure_owner_trust():
    set_trust(TRUST_LOCAL_OWNER)
    yield
    set_trust(TRUST_LOCAL_OWNER)


def test_tool_declaration():
    assert TOOL["name"] == "power_sentinel"
    assert "battery" in TOOL["description"].lower()
    assert callable(TOOL["handler"])


def test_get_live_battery_status_mocked():
    mock_sensor = MagicMock()
    mock_sensor.percent = 85.0
    mock_sensor.power_plugged = True
    mock_sensor.secsleft = -1

    with patch("psutil.sensors_battery", return_value=mock_sensor):
        st = _get_live_battery_status()
        assert st["has_battery"] is True
        assert st["percent"] == 85
        assert st["power_plugged"] is True
        assert "Charging" in st["status_text"]


def test_get_live_battery_status_no_battery():
    with patch("psutil.sensors_battery", return_value=None):
        st = _get_live_battery_status()
        assert st["has_battery"] is False
        assert st["percent"] == 100
        assert "AC Power" in st["status_text"]


def test_parse_battery_report_xml_valid():
    parsed = _parse_battery_report_xml(_SAMPLE_XML)
    assert parsed["has_battery"] is True
    assert parsed["manufacturer"] == "Sunwoda"
    assert parsed["system_manufacturer"] == "LENOVO"
    assert parsed["design_capacity_mwh"] == 60000
    assert parsed["full_charge_capacity_mwh"] == 54000
    assert parsed["cycle_count"] == 150
    assert parsed["health_percent"] == 90.0
    assert parsed["wear_percent"] == 10.0
    assert parsed["condition"] == "Excellent"


def test_parse_battery_report_xml_degraded():
    parsed = _parse_battery_report_xml(_DEGRADED_XML)
    assert parsed["has_battery"] is True
    assert parsed["design_capacity_mwh"] == 50000
    assert parsed["full_charge_capacity_mwh"] == 25000
    assert parsed["health_percent"] == 50.0
    assert parsed["wear_percent"] == 50.0
    assert "High Wear" in parsed["condition"]


def test_parse_battery_report_xml_corrupt():
    parsed = _parse_battery_report_xml("<Invalid><XML>")
    assert parsed["has_battery"] is False


def test_power_sentinel_health():
    mock_report = {
        "has_battery": True,
        "design_capacity_mwh": 60000,
        "full_charge_capacity_mwh": 57000,
        "health_percent": 95.0,
        "wear_percent": 5.0,
        "cycle_count": 80,
        "condition": "Excellent",
        "live": {"percent": 90, "power_plugged": True},
    }
    with patch("actions.power_sentinel._generate_battery_health_report", return_value=mock_report):
        res = json.loads(power_sentinel({"action": "health"}))
        assert res["status"] == "success"
        assert "Battery Health: Excellent" in res["summary"]
        assert "95.0%" in res["summary"]


def test_power_sentinel_health_no_battery():
    with patch("actions.power_sentinel._generate_battery_health_report", return_value={"has_battery": False}):
        res = json.loads(power_sentinel({"action": "health"}))
        assert res["status"] == "success"
        assert "No battery detected" in res["summary"]


def test_power_sentinel_status():
    mock_live = {
        "has_battery": True,
        "percent": 75,
        "power_plugged": False,
        "secs_left": 7200,
        "status_text": "Discharging on Battery",
    }
    with patch("actions.power_sentinel._get_live_battery_status", return_value=mock_live):
        res = json.loads(power_sentinel({"action": "status"}))
        assert res["status"] == "success"
        assert "Battery: 75%" in res["summary"]
        assert "120 mins remaining" in res["summary"]


def test_power_sentinel_plans():
    mock_plans = [
        {"guid": "12345", "name": "Balanced", "active": True},
        {"guid": "67890", "name": "Performance", "active": False},
    ]
    with patch("actions.power_sentinel._get_power_plans", return_value=mock_plans):
        res = json.loads(power_sentinel({"action": "plans"}))
        assert res["status"] == "success"
        assert "Balanced" in res["summary"]
        assert len(res["plans"]) == 2


def test_power_sentinel_unknown_action():
    res = json.loads(power_sentinel({"action": "unknown_action"}))
    assert res["status"] == "error"
    assert "Unknown action" in res["message"]


def test_power_sentinel_requires_owner():
    set_trust(TRUST_UNKNOWN)
    try:
        with pytest.raises(PermissionError):
            power_sentinel({"action": "health"})
    finally:
        set_trust(TRUST_LOCAL_OWNER)
