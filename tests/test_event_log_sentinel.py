"""Tests for Windows Event Log & System Crash Sentinel."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch
import pytest

from actions.event_log_sentinel import (
    event_log_sentinel,
    get_system_errors,
    get_application_crashes,
    get_unexpected_shutdowns,
    get_event_log_summary,
    _run_wevtutil_query,
    TOOL,
)
from core.execution_policy import set_trust, TRUST_LOCAL_OWNER, TRUST_UNKNOWN
from core.fast_reflex import FastReflexRouter

_MOCK_SYSTEM_XML = """
<Event xmlns="http://schemas.microsoft.com/win/2004/08/events/event">
    <System>
        <Provider Name="Microsoft-Windows-Kernel-Power"/>
        <EventID>41</EventID>
        <Level>1</Level>
        <TimeCreated SystemTime="2026-11-08T10:00:00.0000000Z"/>
        <EventRecordID>1001</EventRecordID>
        <Channel>System</Channel>
    </System>
    <EventData>
        <Data Name="BugcheckCode">0</Data>
        <Data Name="PowerButtonTimestamp">0</Data>
        <Data Name="SleepInProgress">0</Data>
    </EventData>
</Event>
<Event xmlns="http://schemas.microsoft.com/win/2004/08/events/event">
    <System>
        <Provider Name="Disk"/>
        <EventID>11</EventID>
        <Level>2</Level>
        <TimeCreated SystemTime="2026-11-08T09:30:00.0000000Z"/>
        <EventRecordID>1000</EventRecordID>
        <Channel>System</Channel>
    </System>
    <EventData>
        <Data Name="DeviceName">Harddisk0/DR0</Data>
    </EventData>
</Event>
"""

_MOCK_APP_XML = """
<Event xmlns="http://schemas.microsoft.com/win/2004/08/events/event">
    <System>
        <Provider Name="Application Error"/>
        <EventID>1000</EventID>
        <Level>2</Level>
        <TimeCreated SystemTime="2026-11-08T08:15:00.0000000Z"/>
        <EventRecordID>2001</EventRecordID>
        <Channel>Application</Channel>
    </System>
    <EventData>
        <Data Name="AppName">notepad.exe</Data>
        <Data Name="AppVersion">11.0.0.1</Data>
        <Data Name="ModuleName">ntdll.dll</Data>
        <Data Name="ExceptionCode">c0000005</Data>
        <Data Name="FaultingOffset">0000000000051234</Data>
        <Data Name="AppPath">C:\\Windows\\notepad.exe</Data>
    </EventData>
</Event>
"""


@pytest.fixture(autouse=True)
def _owner_trust():
    set_trust(TRUST_LOCAL_OWNER)
    yield
    set_trust(TRUST_LOCAL_OWNER)


def test_owner_security_gate():
    set_trust(TRUST_UNKNOWN)
    with pytest.raises(PermissionError):
        event_log_sentinel({"action": "summary"})


def test_tool_declaration():
    assert TOOL["name"] == "event_log_sentinel"
    assert "parameters" in TOOL
    assert callable(TOOL["handler"])


@patch("subprocess.run")
def test_run_wevtutil_query_parsing(mock_run):
    mock_run.return_value = MagicMock(returncode=0, stdout=_MOCK_SYSTEM_XML)
    events = _run_wevtutil_query("System", "*[System[(Level=1)]]", limit=5)
    assert len(events) == 2
    assert events[0]["event_id"] == "41"
    assert events[0]["level"] == "Critical"
    assert events[0]["provider"] == "Microsoft-Windows-Kernel-Power"
    assert events[0]["data"]["BugcheckCode"] == "0"
    assert events[1]["event_id"] == "11"
    assert events[1]["level"] == "Error"


@patch("subprocess.run")
def test_run_wevtutil_query_error(mock_run):
    mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="Error")
    events = _run_wevtutil_query("System", "*", limit=5)
    assert events == []


@patch("actions.event_log_sentinel._run_wevtutil_query")
def test_get_application_crashes(mock_query):
    mock_query.return_value = [
        {
            "event_id": "1000",
            "timestamp": "2026-11-08T08:15:00.0000000Z",
            "data": {
                "AppName": "notepad.exe",
                "AppVersion": "11.0.0.1",
                "ModuleName": "ntdll.dll",
                "ExceptionCode": "c0000005",
                "FaultingOffset": "0000000000051234",
                "AppPath": "C:\\Windows\\notepad.exe",
            },
        }
    ]
    crashes = get_application_crashes(limit=5)
    assert len(crashes) == 1
    assert crashes[0]["app_name"] == "notepad.exe"
    assert crashes[0]["fault_module"] == "ntdll.dll"
    assert crashes[0]["exception_code"] == "c0000005"


@patch("actions.event_log_sentinel._run_wevtutil_query")
def test_get_unexpected_shutdowns(mock_query):
    mock_query.return_value = [
        {
            "event_id": "41",
            "provider": "Microsoft-Windows-Kernel-Power",
            "timestamp": "2026-11-08T10:00:00.0000000Z",
            "data": {
                "BugcheckCode": "0",
                "PowerButtonTimestamp": "0",
                "SleepInProgress": "0",
            },
        }
    ]
    shutdowns = get_unexpected_shutdowns(limit=5)
    assert len(shutdowns) == 1
    assert shutdowns[0]["event_id"] == "41"
    assert shutdowns[0]["bugcheck_code"] == "0"


@patch("actions.event_log_sentinel.get_unexpected_shutdowns")
@patch("actions.event_log_sentinel.get_application_crashes")
@patch("actions.event_log_sentinel.get_system_errors")
def test_event_log_summary_healthy(mock_sys, mock_app, mock_shut):
    mock_sys.return_value = []
    mock_app.return_value = []
    mock_shut.return_value = []

    summary = get_event_log_summary()
    assert summary["health_status"] == "Healthy (Zero critical errors or crashes logged)"
    assert summary["recent_system_errors_count"] == 0


@patch("actions.event_log_sentinel.get_unexpected_shutdowns")
@patch("actions.event_log_sentinel.get_application_crashes")
@patch("actions.event_log_sentinel.get_system_errors")
def test_event_log_summary_shutdown(mock_sys, mock_app, mock_shut):
    mock_sys.return_value = [{"event_id": "11"}]
    mock_app.return_value = []
    mock_shut.return_value = [{"event_id": "41"}]

    summary = get_event_log_summary()
    assert "Attention Required" in summary["health_status"]


def test_event_log_sentinel_actions():
    # Test summary action
    res_raw = event_log_sentinel({"action": "summary"})
    res = json.loads(res_raw)
    assert res["status"] == "success"
    assert "summary" in res
    assert "data" in res

    # Test unknown action
    err_raw = event_log_sentinel({"action": "invalid_action"})
    err = json.loads(err_raw)
    assert err["status"] == "error"


def test_fast_reflex_event_log():
    router = FastReflexRouter()
    intent, score = router.match("check system errors")
    assert intent == "EVENT_LOG_QUERY"
    assert score >= 0.88

    res = router.execute_intent("EVENT_LOG_QUERY")
    assert res.matched is True
    assert "Event Log Status" in res.ack
