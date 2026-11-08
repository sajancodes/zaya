"""Tests for Focus Mode, DND & Notification Center Sentinel."""
import json
import pytest
from unittest.mock import MagicMock, patch

from actions.focus_mode import (
    focus_mode,
    _get_windows_quiet_hours_state,
    _set_windows_quiet_hours_state,
    _get_active_session,
    _save_active_session,
    _list_app_notification_rules,
    _toggle_app_notification,
    TOOL,
)


@pytest.fixture(autouse=True)
def clean_focus_state(tmp_path, monkeypatch):
    """Isolate DB and active session file in tmp directory for tests."""
    db_file = tmp_path / "focus_sessions.db"
    json_file = tmp_path / "active_focus.json"
    monkeypatch.setattr("actions.focus_mode._DB_PATH", db_file)
    monkeypatch.setattr("actions.focus_mode._ACTIVE_SESSION_FILE", json_file)
    # Ensure owner permission passes
    monkeypatch.setattr("actions.focus_mode.require_owner", lambda: None)


def test_tool_declaration():
    assert TOOL["name"] == "focus_mode"
    assert "Focus Mode" in TOOL["description"]
    assert callable(TOOL["handler"])


def test_focus_mode_status_inactive():
    res = json.loads(focus_mode({"action": "status"}))
    assert res["status"] == "success"
    assert res["active"] is False
    assert "INACTIVE" in res["summary"]


def test_focus_mode_start_and_status_active():
    with patch("actions.focus_mode._set_windows_quiet_hours_state", return_value=True):
        res_start = json.loads(focus_mode({
            "action": "start",
            "duration_minutes": 30,
            "goal": "Build Focus Controller",
        }))
        assert res_start["status"] == "success"
        assert res_start["session"]["target_minutes"] == 30
        assert res_start["session"]["goal"] == "Build Focus Controller"
        assert "Focus Mode activated" in res_start["summary"]

        # Check status shows active
        res_status = json.loads(focus_mode({"action": "status"}))
        assert res_status["status"] == "success"
        assert res_status["active"] is True
        assert res_status["session"]["goal"] == "Build Focus Controller"


def test_focus_mode_extend():
    with patch("actions.focus_mode._set_windows_quiet_hours_state", return_value=True):
        focus_mode({"action": "start", "duration_minutes": 25, "goal": "Writing docs"})
        res_extend = json.loads(focus_mode({"action": "extend", "minutes": 15}))
        assert res_extend["status"] == "success"
        assert res_extend["session"]["target_minutes"] == 40
        assert "extended by 15 minutes" in res_extend["summary"]


def test_focus_mode_extend_when_inactive():
    res = json.loads(focus_mode({"action": "extend", "minutes": 10}))
    assert res["status"] == "error"
    assert "no focus session is currently active" in res["message"]


def test_focus_mode_stop():
    with patch("actions.focus_mode._set_windows_quiet_hours_state", return_value=True):
        focus_mode({"action": "start", "duration_minutes": 25, "goal": "Math study"})
        res_stop = json.loads(focus_mode({"action": "stop"}))
        assert res_stop["status"] == "success"
        assert res_stop["goal"] == "Math study"
        assert "completed" in res_stop["summary"].lower()

        # Check status is now inactive
        res_status = json.loads(focus_mode({"action": "status"}))
        assert res_status["active"] is False


def test_focus_mode_stop_when_already_inactive():
    res = json.loads(focus_mode({"action": "stop"}))
    assert res["status"] == "success"
    assert res["active"] is False


def test_focus_mode_history():
    with patch("actions.focus_mode._set_windows_quiet_hours_state", return_value=True):
        focus_mode({"action": "start", "duration_minutes": 10, "goal": "Sprint 1"})
        focus_mode({"action": "stop"})

        res_hist = json.loads(focus_mode({"action": "history"}))
        assert res_hist["status"] == "success"
        assert res_hist["today_sessions"] >= 1
        assert len(res_hist["recent_sessions"]) >= 1
        assert res_hist["recent_sessions"][0]["goal"] == "Sprint 1"


def test_focus_mode_dnd_toggle():
    with patch("actions.focus_mode._set_windows_quiet_hours_state", return_value=True):
        res = json.loads(focus_mode({"action": "dnd_toggle", "enabled": True}))
        assert res["status"] == "success"
        assert "ENABLED" in res["summary"]

        res2 = json.loads(focus_mode({"action": "dnd_toggle", "enabled": False}))
        assert res2["status"] == "success"
        assert "DISABLED" in res2["summary"]


def test_focus_mode_apps_and_toggle():
    with patch("actions.focus_mode._list_app_notification_rules", return_value=[{"app_id": "Brave", "enabled": True}]):
        res = json.loads(focus_mode({"action": "apps"}))
        assert res["status"] == "success"
        assert len(res["apps"]) == 1
        assert res["apps"][0]["app_id"] == "Brave"

    with patch("actions.focus_mode._toggle_app_notification", return_value=True):
        res_toggle = json.loads(focus_mode({"action": "app_toggle", "app_id": "Brave", "enabled": False}))
        assert res_toggle["status"] == "success"
        assert "disabled" in res_toggle["summary"]


def test_focus_mode_unknown_action():
    res = json.loads(focus_mode({"action": "invalid_operation"}))
    assert res["status"] == "error"
    assert "Unknown action" in res["message"]
