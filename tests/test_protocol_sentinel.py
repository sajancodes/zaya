"""Tests for Windows URI Protocol & Deep-Link Sentinel."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch
import pytest

from actions.protocol_sentinel import (
    _extract_executable_path,
    get_protocol_details,
    get_protocol_summary,
    get_registered_protocols,
    protocol_sentinel,
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
        protocol_sentinel({"action": "summary"})


def test_extract_executable_path():
    quoted = '"C:\\Program Files\\Discord\\Discord.exe" --url -- "%1"'
    assert _extract_executable_path(quoted) == "C:\\Program Files\\Discord\\Discord.exe"

    unquoted = "C:\\Riot Games\\RiotClientServices.exe --launch-game"
    assert _extract_executable_path(unquoted) == "C:\\Riot Games\\RiotClientServices.exe"

    empty = ""
    assert _extract_executable_path(empty) is None

    no_exe = "something_else_entirely"
    assert _extract_executable_path(no_exe) is None


def test_get_registered_protocols_mocked():
    import actions.protocol_sentinel as ps
    mock_protocols = [
        {"scheme": "spotify", "source": "HKCU", "command": '"C:\\Users\\User\\Spotify.exe" %1', "executable": "C:\\Users\\User\\Spotify.exe", "executable_exists": False},
        {"scheme": "discord", "source": "HKCU", "command": '"C:\\Users\\User\\Discord.exe" %1', "executable": "C:\\Users\\User\\Discord.exe", "executable_exists": False},
        {"scheme": "antigravity", "source": "HKCU", "command": '"C:\\Users\\User\\Antigravity.exe" %1', "executable": "C:\\Users\\User\\Antigravity.exe", "executable_exists": False},
    ]

    with patch.object(ps, "get_registered_protocols", return_value=mock_protocols):
        res = ps.get_registered_protocols()
        assert len(res) == 3
        schemes = [p["scheme"] for p in res]
        assert "spotify" in schemes
        assert "discord" in schemes


def test_get_registered_protocols_live():
    # Test real Windows registry scan
    res = get_registered_protocols()
    assert isinstance(res, list)
    assert len(res) > 0
    # Every protocol item should contain scheme, source, command
    sample = res[0]
    assert "scheme" in sample
    assert "source" in sample
    assert "command" in sample


def test_get_protocol_details():
    mock_protocols = [
        {"scheme": "spotify", "source": "HKCU", "command": '"C:\\Spotify.exe" %1', "executable": "C:\\Spotify.exe", "executable_exists": True},
    ]

    with patch("actions.protocol_sentinel.get_registered_protocols", return_value=mock_protocols):
        found = get_protocol_details("spotify")
        assert found["status"] == "registered"
        assert found["scheme"] == "spotify"
        assert found["executable"] == "C:\\Spotify.exe"

        not_found = get_protocol_details("nonexistent_scheme_xyz")
        assert not_found["status"] == "not_registered"


def test_get_protocol_summary():
    mock_protocols = [
        {"scheme": "antigravity", "executable": "C:\\Antigravity.exe"},
        {"scheme": "discord", "executable": "C:\\Discord.exe"},
        {"scheme": "discord-rpc-1", "executable": "C:\\Discord.exe"},
        {"scheme": "vscode", "executable": "C:\\Code.exe"},
        {"scheme": "customproto", "executable": None},
    ]

    with patch("actions.protocol_sentinel.get_registered_protocols", return_value=mock_protocols):
        summary = get_protocol_summary()
        assert summary["status"] == "success"
        assert summary["total_protocols_registered"] == 5
        # discord-rpc-1 should be deduplicated under discord
        sample_str = " ".join(summary["popular_apps_sample"])
        assert "antigravity" in sample_str
        assert "discord" in sample_str
        assert "vscode" in sample_str


def test_protocol_sentinel_actions():
    mock_summary = {
        "status": "success",
        "total_protocols_registered": 150,
        "popular_apps_detected_count": 5,
        "popular_apps_sample": ["spotify", "discord", "vscode"],
    }
    mock_details = {
        "status": "registered",
        "scheme": "spotify",
        "source": "HKCU",
        "command": '"C:\\Spotify.exe" %1',
        "executable": "C:\\Spotify.exe",
        "executable_exists": True,
    }
    mock_list = [
        {"scheme": "spotify", "command": "cmd"},
        {"scheme": "discord", "command": "cmd"},
    ]

    with patch("actions.protocol_sentinel.get_protocol_summary", return_value=mock_summary), \
         patch("actions.protocol_sentinel.get_protocol_details", return_value=mock_details), \
         patch("actions.protocol_sentinel.get_registered_protocols", return_value=mock_list):

        out_summary = json.loads(protocol_sentinel({"action": "summary"}))
        assert out_summary["status"] == "success"
        assert "150 total found" in out_summary["summary"]

        out_lookup = json.loads(protocol_sentinel({"action": "lookup", "scheme": "spotify"}))
        assert out_lookup["status"] == "success"
        assert "registered" in out_lookup["summary"]

        out_lookup_err = json.loads(protocol_sentinel({"action": "lookup"}))
        assert out_lookup_err["status"] == "error"

        out_list = json.loads(protocol_sentinel({"action": "list"}))
        assert out_list["status"] == "success"
        assert out_list["data"]["count"] == 2

        out_unknown = json.loads(protocol_sentinel({"action": "invalid"}))
        assert out_unknown["status"] == "error"


def test_tool_declaration():
    assert TOOL["name"] == "protocol_sentinel"
    assert "parameters" in TOOL
    assert callable(TOOL["handler"])


def test_fast_reflex_protocol_query():
    router = FastReflexRouter()
    intent, score = router.match("check protocol handlers")
    assert intent == "PROTOCOL_HANDLER_QUERY"
    assert score >= 0.88

    res = router.execute_intent(intent)
    assert res.matched is True
    assert "registered URL protocols" in res.ack
