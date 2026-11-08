"""Tests for Installed Software & Application Package Sentinel."""
import json
import pytest
from unittest.mock import MagicMock, patch

from actions.software_sentinel import (
    software_sentinel,
    _audit_installed_software,
    TOOL,
)
from core.execution_policy import set_trust, TRUST_LOCAL_OWNER, TRUST_UNKNOWN


@pytest.fixture(autouse=True)
def ensure_owner_trust():
    set_trust(TRUST_LOCAL_OWNER)
    yield
    set_trust(TRUST_LOCAL_OWNER)


def test_tool_declaration():
    assert TOOL["name"] == "software_sentinel"
    assert "software" in TOOL["description"].lower()
    assert callable(TOOL["handler"])


def test_audit_installed_software_mocked():
    mock_apps = [
        {"name": "VS Code", "version": "1.90.0", "publisher": "Microsoft", "install_date": "20240101", "install_location": "C:\\", "registry_source": "HKCU"},
        {"name": "Chrome", "version": "120.0", "publisher": "Google", "install_date": "20240101", "install_location": "C:\\", "registry_source": "HKLM"},
    ]
    with patch("actions.software_sentinel._audit_installed_software", return_value=mock_apps):
        res = json.loads(software_sentinel({"action": "summary"}))
        assert res["status"] == "success"
        assert res["total_count"] == 2
        assert "VS Code" in res["summary"]


def test_software_sentinel_search_found():
    mock_apps = [
        {"name": "Visual Studio Code", "version": "1.90.0", "publisher": "Microsoft", "install_date": "20240101", "install_location": "C:\\", "registry_source": "HKCU"},
        {"name": "Spotify", "version": "1.2", "publisher": "Spotify AB", "install_date": "20240101", "install_location": "C:\\", "registry_source": "HKCU"},
    ]
    with patch("actions.software_sentinel._audit_installed_software", return_value=mock_apps):
        res = json.loads(software_sentinel({"action": "search", "keyword": "visual"}))
        assert res["status"] == "success"
        assert res["matches_count"] == 1
        assert "Visual Studio Code" in res["summary"]


def test_software_sentinel_search_not_found():
    mock_apps = [{"name": "App1", "publisher": "Pub1", "version": "1.0"}]
    with patch("actions.software_sentinel._audit_installed_software", return_value=mock_apps):
        res = json.loads(software_sentinel({"action": "search", "keyword": "nonexistent"}))
        assert res["status"] == "success"
        assert res["matches_count"] == 0
        assert "No installed application found" in res["summary"]


def test_software_sentinel_search_missing_param():
    res = json.loads(software_sentinel({"action": "search"}))
    assert res["status"] == "error"
    assert "Missing required parameter 'keyword'" in res["message"]


def test_software_sentinel_check_installed():
    mock_apps = [{"name": "Android Studio", "version": "2024.1", "publisher": "Google"}]
    with patch("actions.software_sentinel._audit_installed_software", return_value=mock_apps):
        res = json.loads(software_sentinel({"action": "check", "name": "android studio"}))
        assert res["status"] == "success"
        assert res["installed"] is True
        assert "Android Studio" in res["summary"]


def test_software_sentinel_check_not_installed():
    mock_apps = [{"name": "App1", "version": "1.0", "publisher": "Pub1"}]
    with patch("actions.software_sentinel._audit_installed_software", return_value=mock_apps):
        res = json.loads(software_sentinel({"action": "check", "name": "Maya"}))
        assert res["status"] == "success"
        assert res["installed"] is False
        assert "No installed application matching 'maya'" in res["summary"]


def test_software_sentinel_check_missing_param():
    res = json.loads(software_sentinel({"action": "check"}))
    assert res["status"] == "error"
    assert "Missing required parameter 'name'" in res["message"]


def test_software_sentinel_unknown_action():
    res = json.loads(software_sentinel({"action": "unknown"}))
    assert res["status"] == "error"
    assert "Unknown action" in res["message"]


def test_software_sentinel_requires_owner():
    set_trust(TRUST_UNKNOWN)
    try:
        with pytest.raises(PermissionError):
            software_sentinel({"action": "summary"})
    finally:
        set_trust(TRUST_LOCAL_OWNER)


def test_software_sentinel_live():
    res = json.loads(software_sentinel({"action": "summary"}))
    assert res["status"] == "success"
    assert res["total_count"] > 0
