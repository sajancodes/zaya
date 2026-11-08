"""Tests for Windows Background Service Sentinel."""
import json
import pytest
from unittest.mock import MagicMock, patch

from actions.service_sentinel import (
    service_sentinel,
    _get_services_summary,
    _search_services,
    _get_service_detail,
    TOOL,
)
from core.execution_policy import set_trust, TRUST_LOCAL_OWNER, TRUST_UNKNOWN


@pytest.fixture(autouse=True)
def ensure_owner_trust():
    set_trust(TRUST_LOCAL_OWNER)
    yield
    set_trust(TRUST_LOCAL_OWNER)


def test_tool_declaration():
    assert TOOL["name"] == "service_sentinel"
    assert "service" in TOOL["description"].lower()
    assert callable(TOOL["handler"])


def test_get_services_summary_mocked():
    s1 = MagicMock()
    s1.name.return_value = "Audiosrv"
    s1.status.return_value = "running"
    s1.as_dict.return_value = {"name": "Audiosrv", "status": "running", "start_type": "automatic", "pid": 1234}

    s2 = MagicMock()
    s2.name.return_value = "wuauserv"
    s2.status.return_value = "stopped"
    s2.as_dict.return_value = {"name": "wuauserv", "status": "stopped", "start_type": "manual", "pid": None}

    with patch("psutil.win_service_iter", return_value=[s1, s2]):
        data = _get_services_summary()
        assert data["total"] == 2
        assert data["running_count"] == 1
        assert data["stopped_count"] == 1
        assert len(data["key_subsystems"]) >= 1


def test_search_services_mocked():
    s1 = MagicMock()
    s1.name.return_value = "Docker"
    s1.display_name.return_value = "Docker Desktop Service"
    s1.description.return_value = "Runs docker containers"
    s1.status.return_value = "running"
    s1.start_type.return_value = "automatic"
    s1.pid.return_value = 5678

    with patch("psutil.win_service_iter", return_value=[s1]):
        matches = _search_services("docker")
        assert len(matches) == 1
        assert matches[0]["name"] == "Docker"
        assert matches[0]["status"] == "running"


def test_get_service_detail_mocked():
    mock_service = MagicMock()
    mock_service.as_dict.return_value = {
        "name": "WSLService",
        "display_name": "Windows Subsystem for Linux",
        "status": "running",
        "start_type": "automatic",
        "pid": 9999,
        "username": "LocalSystem",
    }
    with patch("psutil.win_service_get", return_value=mock_service):
        detail = _get_service_detail("WSLService")
        assert detail is not None
        assert detail["name"] == "WSLService"
        assert detail["status"] == "running"


def test_service_sentinel_summary():
    mock_summary = {
        "total": 100,
        "running_count": 40,
        "stopped_count": 60,
        "key_subsystems": [{"label": "Windows Audio", "status": "running"}],
    }
    with patch("actions.service_sentinel._get_services_summary", return_value=mock_summary):
        res = json.loads(service_sentinel({"action": "summary"}))
        assert res["status"] == "success"
        assert "40 running" in res["summary"]
        assert "Windows Audio" in res["summary"]


def test_service_sentinel_search():
    mock_matches = [{"name": "Audiosrv", "status": "running"}]
    with patch("actions.service_sentinel._search_services", return_value=mock_matches):
        res = json.loads(service_sentinel({"action": "search", "keyword": "audio"}))
        assert res["status"] == "success"
        assert "Found 1 service(s)" in res["summary"]
        assert len(res["matches"]) == 1


def test_service_sentinel_search_missing_param():
    res = json.loads(service_sentinel({"action": "search"}))
    assert res["status"] == "error"
    assert "Missing required parameter 'keyword'" in res["message"]


def test_service_sentinel_get():
    mock_detail = {
        "name": "Spooler",
        "display_name": "Print Spooler",
        "status": "running",
        "pid": 4321,
        "start_type": "automatic",
        "username": "LocalSystem",
    }
    with patch("actions.service_sentinel._get_service_detail", return_value=mock_detail):
        res = json.loads(service_sentinel({"action": "get", "name": "Spooler"}))
        assert res["status"] == "success"
        assert "Print Spooler" in res["summary"]
        assert "running" in res["summary"]


def test_service_sentinel_get_missing_param():
    res = json.loads(service_sentinel({"action": "get"}))
    assert res["status"] == "error"
    assert "Missing required parameter 'name'" in res["message"]


def test_service_sentinel_unknown_action():
    res = json.loads(service_sentinel({"action": "unknown"}))
    assert res["status"] == "error"
    assert "Unknown action" in res["message"]


def test_service_sentinel_requires_owner():
    set_trust(TRUST_UNKNOWN)
    try:
        with pytest.raises(PermissionError):
            service_sentinel({"action": "summary"})
    finally:
        set_trust(TRUST_LOCAL_OWNER)


def test_service_sentinel_live():
    res = json.loads(service_sentinel({"action": "summary"}))
    assert res["status"] == "success"
    assert res["data"]["total"] > 0
    assert res["data"]["running_count"] > 0
