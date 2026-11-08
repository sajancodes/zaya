"""Unit tests for Windows Audio Endpoint & App Volume Manager.
Created and developed by Sajan Rai for Zaya.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch
import pytest

from actions.audio_switcher import (
    TOOL,
    _control_app_audio,
    _get_default_speakers,
    _list_active_devices,
    _list_app_sessions,
    audio_switcher,
)
from core.execution_policy import TRUST_EXTERNAL_MESSAGE, TRUST_LOCAL_OWNER, with_trust
from core.fast_reflex import FastReflexRouter
from core.tools.routing import ToolRouter


def test_audio_switcher_requires_owner():
    with with_trust(TRUST_EXTERNAL_MESSAGE):
        with pytest.raises(PermissionError):
            audio_switcher({"action": "summary"})


def test_audio_switcher_devices():
    with with_trust(TRUST_LOCAL_OWNER):
        res_raw = audio_switcher({"action": "devices"})
        res = json.loads(res_raw)
        assert res["status"] == "success"
        assert "Active Audio Endpoints:" in res["summary"]
        assert isinstance(res["data"], list)


def test_audio_switcher_app_sessions():
    with with_trust(TRUST_LOCAL_OWNER):
        res_raw = audio_switcher({"action": "app_sessions"})
        res = json.loads(res_raw)
        assert res["status"] == "success"
        assert isinstance(res["data"], list)


def test_audio_switcher_control_app_volume():
    mock_control = {
        "status": "success",
        "app_name": "spotify",
        "matched": [{"process": "Spotify.exe", "pid": 4321, "volume_percent": 65, "muted": False}],
    }
    with patch("actions.audio_switcher._control_app_audio", return_value=mock_control):
        with with_trust(TRUST_LOCAL_OWNER):
            res_raw = audio_switcher({"action": "set_app_volume", "app": "spotify", "volume": 65})
            res = json.loads(res_raw)
            assert res["status"] == "success"
            assert "Set spotify volume to 65%" in res["summary"]


def test_audio_switcher_mute_and_unmute():
    mock_mute = {
        "status": "success",
        "app_name": "brave",
        "matched": [{"process": "brave.exe", "pid": 8888, "volume_percent": 100, "muted": True}],
    }
    with patch("actions.audio_switcher._control_app_audio", return_value=mock_mute):
        with with_trust(TRUST_LOCAL_OWNER):
            res_raw = audio_switcher({"action": "mute_app", "app": "brave"})
            res = json.loads(res_raw)
            assert res["status"] == "success"
            assert "Muted brave" in res["summary"]


def test_audio_switcher_summary():
    with with_trust(TRUST_LOCAL_OWNER):
        res_raw = audio_switcher({"action": "summary"})
        res = json.loads(res_raw)
        assert res["status"] == "success"
        assert "Audio Summary:" in res["summary"]
        assert "default_speakers" in res["data"]
        assert "devices" in res["data"]


def test_tool_declaration_schema():
    assert TOOL["name"] == "audio_switcher"
    assert "devices" in TOOL["parameters"]["properties"]["action"]["enum"]
    assert "set_app_volume" in TOOL["parameters"]["properties"]["action"]["enum"]
    assert callable(TOOL["handler"])


def test_fast_reflex_audio():
    router = FastReflexRouter()
    
    intent, score = router.match("what audio device am i using")
    assert intent == "ACTIVE_AUDIO_DEVICE_QUERY"
    assert score >= 0.88

    intent, score = router.match("what apps are playing audio")
    assert intent == "APP_AUDIO_QUERY"
    assert score >= 0.88

    res_dev = router.execute_intent("ACTIVE_AUDIO_DEVICE_QUERY")
    assert res_dev.matched is True
    assert "outputting through" in res_dev.ack or "unavailable" in res_dev.ack

    res_app = router.execute_intent("APP_AUDIO_QUERY")
    assert res_app.matched is True
    assert "active audio app" in res_app.ack or "No apps" in res_app.ack


def test_tool_router_maps_audio_switcher():
    router = ToolRouter()
    declarations = [
        {"name": "audio_switcher", "description": "switch audio endpoints and control app volumes"},
        {"name": "web_search", "description": "search web"},
    ]
    routed = router.route("mute spotify app and switch headphones", declarations)
    names = [d["name"] for d in routed.declarations]
    assert "audio_switcher" in names
