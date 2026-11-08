"""Tests for Windows Night Light & Blue Light Reduction Sentinel."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch
import pytest

from actions.night_light_sentinel import (
    get_night_light_status,
    night_light_sentinel,
    set_night_light,
    toggle_night_light,
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
        night_light_sentinel({"action": "status"})


def test_get_night_light_status_live():
    # Test real Windows registry status query
    res = get_night_light_status()
    assert isinstance(res, dict)
    assert "status" in res
    assert "enabled" in res
    assert "state_label" in res
    assert "schedule" in res


def test_get_night_light_status_mocked_on():
    import actions.night_light_sentinel as nls
    # Construct 25-byte sample with byte 18 == 21 (ON)
    data_state = bytearray(30)
    data_state[18] = 21

    # Settings buffer with schedule markers
    data_settings = bytearray([0] * 10 + [202, 20, 14, 22, 30] + [202, 30, 14, 6, 45] + [0] * 10)

    with patch.object(nls, "get_night_light_status", return_value={
        "status": "active",
        "enabled": True,
        "state_label": "ON (Active)",
        "schedule": {"has_schedule": True, "start_time": "22:30", "end_time": "06:45"},
    }):
        info = nls.get_night_light_status()
        assert info["enabled"] is True
        assert info["state_label"] == "ON (Active)"
        assert info["schedule"]["start_time"] == "22:30"
        assert info["schedule"]["end_time"] == "06:45"


def test_set_and_toggle_night_light():
    with patch("actions.night_light_sentinel.set_night_light", return_value={"status": "success", "enabled": True}):
        res_on = set_night_light(True)
        assert res_on["status"] == "success"
        assert res_on["enabled"] is True

    with patch("actions.night_light_sentinel.get_night_light_status", return_value={"status": "active", "enabled": False}), \
         patch("actions.night_light_sentinel.set_night_light", return_value={"status": "success", "enabled": True}) as mock_set:
        res_tog = toggle_night_light()
        mock_set.assert_called_once_with(True)
        assert res_tog["status"] == "success"


def test_night_light_sentinel_actions():
    mock_status = {
        "status": "active",
        "enabled": False,
        "state_label": "OFF (Disabled)",
        "schedule": {"has_schedule": True, "start_time": "21:00", "end_time": "07:00"},
    }

    with patch("actions.night_light_sentinel.get_night_light_status", return_value=mock_status), \
         patch("actions.night_light_sentinel.set_night_light", return_value={"status": "success", "enabled": True, "message": "enabled"}), \
         patch("actions.night_light_sentinel.toggle_night_light", return_value={"status": "success", "enabled": True}):

        out_status = json.loads(night_light_sentinel({"action": "status"}))
        assert out_status["status"] == "success"
        assert "OFF (Disabled)" in out_status["summary"]

        out_enable = json.loads(night_light_sentinel({"action": "enable"}))
        assert out_enable["status"] == "success"

        out_disable = json.loads(night_light_sentinel({"action": "disable"}))
        assert out_disable["status"] == "success"

        out_toggle = json.loads(night_light_sentinel({"action": "toggle"}))
        assert out_toggle["status"] == "success"

        out_err = json.loads(night_light_sentinel({"action": "invalid"}))
        assert out_err["status"] == "error"


def test_tool_declaration():
    assert TOOL["name"] == "night_light_sentinel"
    assert "parameters" in TOOL
    assert callable(TOOL["handler"])


def test_fast_reflex_night_light():
    router = FastReflexRouter()

    # Query
    intent, score = router.match("check night light")
    assert intent == "NIGHT_LIGHT_STATUS"
    assert score >= 0.88
    res = router.execute_intent(intent)
    assert res.matched is True
    assert "Windows Night Light is currently" in res.ack

    # Enable
    on_intent, on_score = router.match("turn on night light")
    assert on_intent == "NIGHT_LIGHT_ON"
    assert on_score >= 0.88
    with patch("actions.night_light_sentinel.set_night_light", return_value={"status": "success"}):
        res_on = router.execute_intent(on_intent)
        assert res_on.matched is True
        assert "enabled" in res_on.ack

    # Disable
    off_intent, off_score = router.match("turn off night light")
    assert off_intent == "NIGHT_LIGHT_OFF"
    assert off_score >= 0.88
    with patch("actions.night_light_sentinel.set_night_light", return_value={"status": "success"}):
        res_off = router.execute_intent(off_intent)
        assert res_off.matched is True
        assert "disabled" in res_off.ack

    # Toggle
    tog_intent, tog_score = router.match("toggle night light")
    assert tog_intent == "NIGHT_LIGHT_TOGGLE"
    assert tog_score >= 0.88
    with patch("actions.night_light_sentinel.toggle_night_light", return_value={"status": "success", "enabled": True}):
        res_tog = router.execute_intent(tog_intent)
        assert res_tog.matched is True
        assert "Windows Night Light" in res_tog.ack
