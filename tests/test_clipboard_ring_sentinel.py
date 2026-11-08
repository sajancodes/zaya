"""Tests for Windows Clipboard History & Ring Sentinel."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch
import pytest

from actions.clipboard_ring_sentinel import (
    clipboard_ring_sentinel,
    get_clipboard_history_status,
    set_clipboard_history,
    toggle_clipboard_history,
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
        clipboard_ring_sentinel({"action": "status"})


def test_get_clipboard_history_status_live():
    res = get_clipboard_history_status()
    assert isinstance(res, dict)
    assert res["status"] in ("success", "unavailable")
    assert "enabled" in res
    assert "cloud_sync" in res
    assert res["hotkey"] == "Win + V"


def test_get_clipboard_history_status_mocked():
    import actions.clipboard_ring_sentinel as crs

    with patch.object(crs, "get_clipboard_history_status", return_value={
        "status": "success",
        "enabled": True,
        "cloud_sync": True,
        "shell_hotkey_used": True,
        "hotkey": "Win + V",
        "state_label": "Enabled",
    }):
        info = crs.get_clipboard_history_status()
        assert info["enabled"] is True
        assert info["cloud_sync"] is True
        assert info["state_label"] == "Enabled"


def test_set_and_toggle_clipboard_history():
    with patch("actions.clipboard_ring_sentinel.set_clipboard_history", return_value={"status": "success", "enabled": True}):
        res_on = set_clipboard_history(True)
        assert res_on["status"] == "success"
        assert res_on["enabled"] is True

    with patch("actions.clipboard_ring_sentinel.get_clipboard_history_status", return_value={"status": "success", "enabled": True}), \
         patch("actions.clipboard_ring_sentinel.set_clipboard_history", return_value={"status": "success", "enabled": False}) as mock_set:
        res_tog = toggle_clipboard_history()
        mock_set.assert_called_once_with(False)
        assert res_tog["status"] == "success"


def test_clipboard_ring_sentinel_actions():
    mock_status = {
        "status": "success",
        "enabled": True,
        "cloud_sync": False,
        "shell_hotkey_used": True,
        "hotkey": "Win + V",
        "state_label": "Enabled",
    }

    with patch("actions.clipboard_ring_sentinel.get_clipboard_history_status", return_value=mock_status), \
         patch("actions.clipboard_ring_sentinel.set_clipboard_history", return_value={"status": "success", "enabled": True}), \
         patch("actions.clipboard_ring_sentinel.toggle_clipboard_history", return_value={"status": "success", "enabled": False}):

        out_stat = json.loads(clipboard_ring_sentinel({"action": "status"}))
        assert out_stat["status"] == "success"
        assert "Enabled" in out_stat["summary"]
        assert "Win + V" in out_stat["summary"]

        out_en = json.loads(clipboard_ring_sentinel({"action": "enable"}))
        assert out_en["status"] == "success"

        out_dis = json.loads(clipboard_ring_sentinel({"action": "disable"}))
        assert out_dis["status"] == "success"

        out_tog = json.loads(clipboard_ring_sentinel({"action": "toggle"}))
        assert out_tog["status"] == "success"

        out_err = json.loads(clipboard_ring_sentinel({"action": "invalid"}))
        assert out_err["status"] == "error"


def test_tool_declaration():
    assert TOOL["name"] == "clipboard_ring_sentinel"
    assert "parameters" in TOOL
    assert callable(TOOL["handler"])


def test_fast_reflex_clipboard_history():
    router = FastReflexRouter()

    # Query
    intent, score = router.match("check clipboard history")
    assert intent == "CLIPBOARD_HISTORY_QUERY"
    assert score >= 0.88

    res = router.execute_intent(intent)
    assert res.matched is True
    assert "Windows Clipboard History is currently" in res.ack

    # Enable
    on_intent, on_score = router.match("enable clipboard history")
    assert on_intent == "CLIPBOARD_HISTORY_ON"
    assert on_score >= 0.88

    with patch("actions.clipboard_ring_sentinel.set_clipboard_history", return_value={"status": "success"}):
        res_on = router.execute_intent(on_intent)
        assert res_on.matched is True
        assert "enabled" in res_on.ack

    # Disable
    off_intent, off_score = router.match("disable clipboard history")
    assert off_intent == "CLIPBOARD_HISTORY_OFF"
    assert off_score >= 0.88

    with patch("actions.clipboard_ring_sentinel.set_clipboard_history", return_value={"status": "success"}):
        res_off = router.execute_intent(off_intent)
        assert res_off.matched is True
        assert "disabled" in res_off.ack
