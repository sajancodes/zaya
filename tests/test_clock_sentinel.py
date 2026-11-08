"""Tests for Windows Timezone, NTP Clock & Time Synchronization Sentinel."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch
import pytest

from actions.clock_sentinel import (
    clock_sentinel,
    get_clock_summary,
    get_ntp_server_config,
    get_system_timezone_info,
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
        clock_sentinel({"action": "summary"})


def test_get_system_timezone_info_live():
    res = get_system_timezone_info()
    assert isinstance(res, dict)
    assert res["status"] in ("success", "fallback")
    assert "timezone_name" in res
    assert "utc_offset" in res
    assert "local_time" in res
    assert "utc_time" in res
    assert res["utc_offset"].startswith("UTC")


def test_get_system_timezone_info_mocked():
    import actions.clock_sentinel as cs

    with patch.object(cs, "get_system_timezone_info", return_value={
        "status": "success",
        "timezone_name": "Eastern Standard Time",
        "standard_name": "Eastern Standard Time",
        "utc_offset": "UTC-05:00",
        "bias_minutes": -300,
        "daylight_disabled": False,
        "local_time": "2026-11-08 12:00:00",
        "utc_time": "2026-11-08 17:00:00",
    }):
        info = cs.get_system_timezone_info()
        assert info["timezone_name"] == "Eastern Standard Time"
        assert info["utc_offset"] == "UTC-05:00"
        assert info["bias_minutes"] == -300


def test_get_ntp_server_config():
    ntp = get_ntp_server_config()
    assert isinstance(ntp, dict)
    assert "primary_ntp_server" in ntp
    assert "sync_type" in ntp
    assert "configured_servers" in ntp
    assert len(ntp["configured_servers"]) > 0


def test_get_clock_summary():
    summary = get_clock_summary()
    assert summary["status"] == "success"
    assert "timezone" in summary
    assert "ntp" in summary


def test_clock_sentinel_actions():
    mock_summary = {
        "status": "success",
        "timezone": {
            "timezone_name": "Nepal Standard Time",
            "utc_offset": "UTC+05:45",
            "local_time": "2026-11-08 17:00:00",
            "utc_time": "2026-11-08 11:15:00",
        },
        "ntp": {
            "primary_ntp_server": "time.windows.com",
            "sync_type": "NTP",
            "configured_servers": ["time.windows.com"],
        },
    }

    with patch("actions.clock_sentinel.get_clock_summary", return_value=mock_summary), \
         patch("actions.clock_sentinel.get_system_timezone_info", return_value=mock_summary["timezone"]), \
         patch("actions.clock_sentinel.get_ntp_server_config", return_value=mock_summary["ntp"]):

        out_sum = json.loads(clock_sentinel({"action": "summary"}))
        assert out_sum["status"] == "success"
        assert "Nepal Standard Time" in out_sum["summary"]
        assert "UTC+05:45" in out_sum["summary"]

        out_tz = json.loads(clock_sentinel({"action": "timezone"}))
        assert out_tz["status"] == "success"
        assert "System Timezone:" in out_tz["summary"]

        out_ntp = json.loads(clock_sentinel({"action": "ntp"}))
        assert out_ntp["status"] == "success"
        assert "Primary NTP Server:" in out_ntp["summary"]

        out_err = json.loads(clock_sentinel({"action": "invalid"}))
        assert out_err["status"] == "error"


def test_tool_declaration():
    assert TOOL["name"] == "clock_sentinel"
    assert "parameters" in TOOL
    assert callable(TOOL["handler"])


def test_fast_reflex_timezone():
    router = FastReflexRouter()

    intent, score = router.match("what is my timezone")
    assert intent == "TIMEZONE_QUERY"
    assert score >= 0.88

    res = router.execute_intent(intent)
    assert res.matched is True
    assert "System timezone is" in res.ack
    assert "UTC" in res.ack
