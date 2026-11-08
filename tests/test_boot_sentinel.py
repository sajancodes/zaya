"""Tests for System Uptime, Boot Diagnostics & Power State Sentinel."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch
import pytest

from actions.boot_sentinel import (
    boot_sentinel,
    get_system_uptime,
    get_last_shutdown_info,
    get_wake_armed_devices,
    get_available_sleep_states,
    get_boot_summary,
    TOOL,
)
from core.execution_policy import set_trust, TRUST_LOCAL_OWNER, TRUST_UNKNOWN
from core.fast_reflex import FastReflexRouter

_MOCK_EVENT_1074 = """
<Event xmlns="http://schemas.microsoft.com/win/2004/08/events/event">
    <System>
        <Provider Name="User32"/>
        <EventID>1074</EventID>
        <TimeCreated SystemTime="2026-11-07T13:19:41.2372655Z"/>
    </System>
    <EventData>
        <Data Name="param1">C:\\WINDOWS\\system32\\winlogon.exe</Data>
        <Data Name="param2">PARROT</Data>
        <Data Name="param3">Power button pressed</Data>
        <Data Name="param5">power off</Data>
        <Data Name="param7">NT AUTHORITY\\SYSTEM</Data>
    </EventData>
</Event>
"""

_MOCK_POWERCFG_A = """
The following sleep states are available on this system:
    Standby (S0 Low Power Idle) Network Connected

The following sleep states are not available on this system:
    Standby (S3)
"""

_MOCK_WAKE_ARMED = """
Realtek PCIe GbE Family Controller
HID-compliant mouse (002)
"""


@pytest.fixture(autouse=True)
def _owner_trust():
    set_trust(TRUST_LOCAL_OWNER)
    yield
    set_trust(TRUST_LOCAL_OWNER)


def test_owner_security_gate():
    set_trust(TRUST_UNKNOWN)
    with pytest.raises(PermissionError):
        boot_sentinel({"action": "summary"})


def test_tool_declaration():
    assert TOOL["name"] == "boot_sentinel"
    assert "parameters" in TOOL
    assert callable(TOOL["handler"])


@patch("time.time")
@patch("psutil.boot_time")
def test_get_system_uptime(mock_boot, mock_time):
    mock_boot.return_value = 100000.0
    mock_time.return_value = 100000.0 + 90060  # 1 day, 1 hour, 1 minute
    uptime = get_system_uptime()
    assert uptime["days"] == 1
    assert uptime["hours"] == 1
    assert uptime["minutes"] == 1
    assert "1 day" in uptime["uptime_formatted"]


@patch("subprocess.run")
def test_get_last_shutdown_info(mock_run):
    mock_run.return_value = MagicMock(returncode=0, stdout=_MOCK_EVENT_1074)
    shut = get_last_shutdown_info()
    assert shut is not None
    assert shut["shutdown_action"] == "power off"
    assert shut["initiator_user"] == "NT AUTHORITY\\SYSTEM"
    assert shut["reason"] == "Power button pressed"


@patch("subprocess.run")
def test_get_wake_armed_devices(mock_run):
    mock_run.return_value = MagicMock(returncode=0, stdout=_MOCK_WAKE_ARMED)
    devices = get_wake_armed_devices()
    assert len(devices) == 2
    assert "Realtek PCIe GbE Family Controller" in devices
    assert "HID-compliant mouse (002)" in devices


@patch("subprocess.run")
def test_get_available_sleep_states(mock_run):
    mock_run.return_value = MagicMock(returncode=0, stdout=_MOCK_POWERCFG_A)
    states = get_available_sleep_states()
    assert len(states) == 1
    assert "Standby (S0 Low Power Idle) Network Connected" in states[0]


@patch("actions.boot_sentinel.get_available_sleep_states")
@patch("actions.boot_sentinel.get_wake_armed_devices")
@patch("actions.boot_sentinel.get_last_shutdown_info")
@patch("actions.boot_sentinel.get_system_uptime")
def test_get_boot_summary(mock_upt, mock_shut, mock_wake, mock_sleep):
    mock_upt.return_value = {"uptime_formatted": "4 hours, 10 minutes", "uptime_seconds": 15000}
    mock_shut.return_value = {"initiator_user": "Sajan", "shutdown_action": "restart"}
    mock_wake.return_value = ["Mouse"]
    mock_sleep.return_value = ["Modern Standby"]

    summary = get_boot_summary()
    assert summary["status"] == "success"
    assert summary["uptime"]["uptime_seconds"] == 15000
    assert summary["last_shutdown"]["initiator_user"] == "Sajan"


def test_boot_sentinel_actions():
    res_raw = boot_sentinel({"action": "summary"})
    res = json.loads(res_raw)
    assert res["status"] == "success"
    assert "summary" in res
    assert "data" in res

    upt_raw = boot_sentinel({"action": "uptime"})
    upt = json.loads(upt_raw)
    assert upt["status"] == "success"
    assert "uptime" in upt

    err_raw = boot_sentinel({"action": "invalid"})
    err = json.loads(err_raw)
    assert err["status"] == "error"


def test_fast_reflex_system_uptime():
    router = FastReflexRouter()
    intent, score = router.match("how long has my pc been on")
    assert intent == "SYSTEM_UPTIME_QUERY"
    assert score >= 0.88

    res = router.execute_intent("SYSTEM_UPTIME_QUERY")
    assert res.matched is True
    assert "System has been running for" in res.ack
