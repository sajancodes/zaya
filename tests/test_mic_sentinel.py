"""Tests for Windows Microphone & Audio Capture Sentinel."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch
import pytest

from actions.mic_sentinel import (
    get_microphone_status,
    list_recording_devices,
    mic_sentinel,
    set_microphone_mute,
    set_microphone_volume,
    toggle_microphone_mute,
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
        mic_sentinel({"action": "status"})


def test_get_microphone_status_success():
    mock_mic = MagicMock()
    mock_mic.FriendlyName = "Realtek High Definition Audio"
    mock_mic.id = "{0.0.1.00000000}.{mock-id}"
    mock_vol = MagicMock()
    mock_vol.GetMute.return_value = 0
    mock_vol.GetMasterVolumeLevelScalar.return_value = 0.75
    mock_mic.EndpointVolume = mock_vol

    with patch("actions.mic_sentinel._get_default_mic_device", return_value=mock_mic):
        status = get_microphone_status()

    assert status["device"] == "Realtek High Definition Audio"
    assert status["muted"] is False
    assert status["volume_percent"] == 75
    assert status["status"] == "active"


def test_get_microphone_status_none():
    with patch("actions.mic_sentinel._get_default_mic_device", return_value=None):
        status = get_microphone_status()

    assert status["device"] == "None detected"
    assert status["status"] == "unavailable"


def test_list_recording_devices():
    dev1 = MagicMock()
    dev1.id = "{0.0.1.00000000}.{mic-1}"
    dev1.FriendlyName = "Microphone Array"
    dev1.state = "AudioDeviceState.Active"

    dev2 = MagicMock()
    dev2.id = "{0.0.0.00000000}.{spk-1}"
    dev2.FriendlyName = "Headphones"
    dev2.state = "AudioDeviceState.Active"

    dev3 = MagicMock()
    dev3.id = "{0.0.1.00000000}.{mic-2}"
    dev3.FriendlyName = "USB Gaming Headset Mic"
    dev3.state = "Active"

    with patch("pycaw.pycaw.AudioUtilities.GetAllDevices", return_value=[dev1, dev2, dev3]):
        devices = list_recording_devices()

    # Only dev1 and dev3 should match capture endpoint IDs
    names = [d["name"] for d in devices]
    assert "Microphone Array" in names
    assert "USB Gaming Headset Mic" in names
    assert "Headphones" not in names


def test_set_microphone_mute():
    mock_mic = MagicMock()
    mock_mic.FriendlyName = "Microphone Array"
    mock_vol = MagicMock()
    mock_vol.GetMute.return_value = 1
    mock_mic.EndpointVolume = mock_vol

    with patch("actions.mic_sentinel._get_default_mic_device", return_value=mock_mic):
        res = set_microphone_mute(True)

    mock_vol.SetMute.assert_called_once_with(1, None)
    assert res["status"] == "success"
    assert res["muted"] is True
    assert "muted" in res["message"]


def test_set_microphone_mute_missing_device():
    with patch("actions.mic_sentinel._get_default_mic_device", return_value=None):
        res = set_microphone_mute(True)

    assert res["status"] == "error"


def test_toggle_microphone_mute():
    mock_mic = MagicMock()
    mock_mic.FriendlyName = "Microphone Array"
    mock_vol = MagicMock()
    mock_vol.GetMute.side_effect = [0, 1]  # starts unmuted, then muted
    mock_mic.EndpointVolume = mock_vol

    with patch("actions.mic_sentinel._get_default_mic_device", return_value=mock_mic):
        res = toggle_microphone_mute()

    mock_vol.SetMute.assert_called_once_with(1, None)
    assert res["status"] == "success"


def test_set_microphone_volume():
    mock_mic = MagicMock()
    mock_mic.FriendlyName = "Microphone Array"
    mock_vol = MagicMock()
    mock_vol.GetMasterVolumeLevelScalar.return_value = 0.50
    mock_mic.EndpointVolume = mock_vol

    with patch("actions.mic_sentinel._get_default_mic_device", return_value=mock_mic):
        res = set_microphone_volume(50)

    mock_vol.SetMasterVolumeLevelScalar.assert_called_once_with(0.5, None)
    assert res["status"] == "success"
    assert res["volume_percent"] == 50


def test_mic_sentinel_actions():
    mock_mic = MagicMock()
    mock_mic.FriendlyName = "Microphone Array"
    mock_mic.id = "{0.0.1.00000000}.{mock-id}"
    mock_vol = MagicMock()
    mock_vol.GetMute.return_value = 0
    mock_vol.GetMasterVolumeLevelScalar.return_value = 0.80
    mock_mic.EndpointVolume = mock_vol

    with patch("actions.mic_sentinel._get_default_mic_device", return_value=mock_mic):
        out = json.loads(mic_sentinel({"action": "status"}))
        assert out["status"] == "success"
        assert "Microphone Array" in out["summary"]

        out_mute = json.loads(mic_sentinel({"action": "mute"}))
        assert out_mute["status"] == "success"

        out_unmute = json.loads(mic_sentinel({"action": "unmute"}))
        assert out_unmute["status"] == "success"

        out_vol = json.loads(mic_sentinel({"action": "set_volume", "volume": 70}))
        assert out_vol["status"] == "success"

        out_vol_err = json.loads(mic_sentinel({"action": "set_volume"}))
        assert out_vol_err["status"] == "error"

        out_err = json.loads(mic_sentinel({"action": "unknown"}))
        assert out_err["status"] == "error"


def test_tool_declaration():
    assert TOOL["name"] == "mic_sentinel"
    assert "parameters" in TOOL
    assert callable(TOOL["handler"])


def test_fast_reflex_mic_status():
    router = FastReflexRouter()
    intent, score = router.match("check microphone")
    assert intent == "MIC_STATUS_QUERY"
    assert score >= 0.88

    res = router.execute_intent(intent)
    assert res.matched is True
    assert "Microphone is" in res.ack


def test_fast_reflex_mic_mute_and_unmute():
    router = FastReflexRouter()
    mute_intent, m_score = router.match("mute my mic")
    assert mute_intent == "MIC_MUTE"
    assert m_score >= 0.88

    with patch("actions.mic_sentinel.set_microphone_mute", return_value={"status": "success"}):
        res = router.execute_intent(mute_intent)
        assert res.matched is True
        assert "Microphone muted" in res.ack

    unmute_intent, u_score = router.match("unmute my mic")
    assert unmute_intent == "MIC_UNMUTE"
    assert u_score >= 0.88

    with patch("actions.mic_sentinel.set_microphone_mute", return_value={"status": "success"}):
        res_u = router.execute_intent(unmute_intent)
        assert res_u.matched is True
        assert "Microphone unmuted" in res_u.ack
