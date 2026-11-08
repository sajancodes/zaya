"""Tests for Windows Startup Programs & Auto-Run Sentinel."""
import json
import pytest
from unittest.mock import MagicMock, patch

from actions.startup_sentinel import (
    startup_sentinel,
    _extract_target_path,
    _audit_registry_startup,
    _audit_folder_startup,
    _get_all_startup_entries,
    TOOL,
)
from core.execution_policy import set_trust, TRUST_LOCAL_OWNER, TRUST_UNKNOWN


@pytest.fixture(autouse=True)
def ensure_owner_trust():
    set_trust(TRUST_LOCAL_OWNER)
    yield
    set_trust(TRUST_LOCAL_OWNER)


def test_tool_declaration():
    assert TOOL["name"] == "startup_sentinel"
    assert "startup" in TOOL["description"].lower()
    assert callable(TOOL["handler"])


def test_extract_target_path_quoted():
    cmd = r'"C:\Program Files\App\app.exe" --minimized -v'
    res = _extract_target_path(cmd)
    assert res == r"C:\Program Files\App\app.exe"


def test_extract_target_path_unquoted():
    cmd = r"powershell.exe -ExecutionPolicy Bypass"
    res = _extract_target_path(cmd)
    assert res == "powershell.exe"


def test_audit_registry_startup_mocked():
    mock_reg = [
        {
            "name": "TestApp",
            "command": "C:\\test.exe",
            "target_path": "C:\\test.exe",
            "exists_on_disk": True,
            "source": "HKCU\\Run",
        }
    ]
    with patch("actions.startup_sentinel._audit_registry_startup", return_value=mock_reg):
        with patch("actions.startup_sentinel._audit_folder_startup", return_value=[]):
            data = _get_all_startup_entries()
            assert data["total_count"] == 1
            assert data["valid_count"] == 1
            assert data["dead_count"] == 0
            assert data["entries"][0]["name"] == "TestApp"


def test_get_all_startup_entries_with_dead():
    mock_entries = [
        {
            "name": "GhostApp",
            "command": "C:\\nonexistent\\app.exe",
            "target_path": "C:\\nonexistent\\app.exe",
            "exists_on_disk": False,
            "source": "HKCU\\Run",
        }
    ]
    with patch("actions.startup_sentinel._audit_registry_startup", return_value=mock_entries):
        with patch("actions.startup_sentinel._audit_folder_startup", return_value=[]):
            data = _get_all_startup_entries()
            assert data["total_count"] == 1
            assert data["dead_count"] == 1
            assert len(data["dead_entries"]) == 1
            assert data["dead_entries"][0]["name"] == "GhostApp"


def test_startup_sentinel_summary():
    mock_data = {
        "total_count": 5,
        "valid_count": 5,
        "dead_count": 0,
        "entries": [{"name": f"App{i}"} for i in range(5)],
        "dead_entries": [],
    }
    with patch("actions.startup_sentinel._get_all_startup_entries", return_value=mock_data):
        res = json.loads(startup_sentinel({"action": "summary"}))
        assert res["status"] == "success"
        assert "5 auto-run entries" in res["summary"]
        assert "all targets valid" in res["summary"]


def test_startup_sentinel_dead():
    mock_data = {
        "total_count": 2,
        "valid_count": 1,
        "dead_count": 1,
        "entries": [],
        "dead_entries": [{"name": "GhostEntry", "source": "HKCU\\Run"}],
    }
    with patch("actions.startup_sentinel._get_all_startup_entries", return_value=mock_data):
        res = json.loads(startup_sentinel({"action": "dead"}))
        assert res["status"] == "success"
        assert res["dead_count"] == 1
        assert "GhostEntry" in res["summary"]


def test_startup_sentinel_search():
    mock_data = {
        "total_count": 2,
        "valid_count": 2,
        "dead_count": 0,
        "entries": [
            {"name": "Spotify", "command": "C:\\spotify.exe"},
            {"name": "Discord", "command": "C:\\discord.exe"},
        ],
        "dead_entries": [],
    }
    with patch("actions.startup_sentinel._get_all_startup_entries", return_value=mock_data):
        res = json.loads(startup_sentinel({"action": "search", "keyword": "spot"}))
        assert res["status"] == "success"
        assert len(res["matches"]) == 1
        assert res["matches"][0]["name"] == "Spotify"


def test_startup_sentinel_search_missing_param():
    res = json.loads(startup_sentinel({"action": "search"}))
    assert res["status"] == "error"
    assert "Missing required parameter 'keyword'" in res["message"]


def test_startup_sentinel_unknown_action():
    res = json.loads(startup_sentinel({"action": "unknown"}))
    assert res["status"] == "error"
    assert "Unknown action" in res["message"]


def test_startup_sentinel_requires_owner():
    set_trust(TRUST_UNKNOWN)
    try:
        with pytest.raises(PermissionError):
            startup_sentinel({"action": "summary"})
    finally:
        set_trust(TRUST_LOCAL_OWNER)


def test_startup_sentinel_live():
    res = json.loads(startup_sentinel({"action": "summary"}))
    assert res["status"] == "success"
    assert res["data"]["total_count"] > 0
