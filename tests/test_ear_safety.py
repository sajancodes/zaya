"""Tests for System Audio Volume Limiter & Ear-Safety Sentinel."""
import json
import pytest
from unittest.mock import MagicMock, patch

from actions.ear_safety import (
    ear_safety,
    _load_safety_config,
    _save_safety_config,
    TOOL,
)
from core.execution_policy import set_trust, TRUST_LOCAL_OWNER, TRUST_UNKNOWN


@pytest.fixture(autouse=True)
def clean_ear_safety_state(tmp_path, monkeypatch):
    test_cfg = tmp_path / "ear_safety.json"
    monkeypatch.setattr("actions.ear_safety._CONFIG_PATH", test_cfg)
    set_trust(TRUST_LOCAL_OWNER)
    yield
    set_trust(TRUST_LOCAL_OWNER)


def test_tool_declaration():
    assert TOOL["name"] == "ear_safety"
    assert "ear" in TOOL["description"].lower()
    assert callable(TOOL["handler"])


def test_load_and_save_config():
    cfg = {"enabled": True, "max_volume_percent": 65, "whisper_mode": False}
    _save_safety_config(cfg)
    loaded = _load_safety_config()
    assert loaded["max_volume_percent"] == 65
    assert loaded["enabled"] is True


def test_ear_safety_status():
    with patch("actions.ear_safety._get_master_volume", return_value=60):
        res = json.loads(ear_safety({"action": "status"}))
        assert res["status"] == "success"
        assert "Ear Safety Guard" in res["summary"]
        assert "60%" in res["summary"]


def test_ear_safety_set_ceiling_clamped():
    with patch("actions.ear_safety._get_master_volume", return_value=90):
        with patch("actions.ear_safety._set_master_volume", return_value=True) as mock_set:
            res = json.loads(ear_safety({"action": "set_ceiling", "percent": 70}))
            assert res["status"] == "success"
            assert res["clamped"] is True
            assert res["max_volume_percent"] == 70
            mock_set.assert_called_once_with(70)


def test_ear_safety_set_ceiling_unclamped():
    with patch("actions.ear_safety._get_master_volume", return_value=40):
        with patch("actions.ear_safety._set_master_volume", return_value=True) as mock_set:
            res = json.loads(ear_safety({"action": "set_ceiling", "percent": 75}))
            assert res["status"] == "success"
            assert res["clamped"] is False
            mock_set.assert_not_called()


def test_ear_safety_whisper_mode():
    with patch("actions.ear_safety._set_master_volume", return_value=True) as mock_set:
        res = json.loads(ear_safety({"action": "whisper"}))
        assert res["status"] == "success"
        assert "Whisper Mode activated" in res["summary"]
        assert res["ceiling"] == 25
        mock_set.assert_called_once_with(15)


def test_ear_safety_normal_mode():
    with patch("actions.ear_safety._set_master_volume", return_value=True) as mock_set:
        res = json.loads(ear_safety({"action": "normal"}))
        assert res["status"] == "success"
        assert "Normal audio mode restored" in res["summary"]
        mock_set.assert_called_once_with(50)


def test_ear_safety_enable_disable():
    res_off = json.loads(ear_safety({"action": "disable"}))
    assert res_off["status"] == "success"
    assert res_off["enabled"] is False

    res_on = json.loads(ear_safety({"action": "enable"}))
    assert res_on["status"] == "success"
    assert res_on["enabled"] is True


def test_ear_safety_unknown_action():
    res = json.loads(ear_safety({"action": "invalid"}))
    assert res["status"] == "error"
    assert "Unknown action" in res["message"]


def test_ear_safety_requires_owner():
    set_trust(TRUST_UNKNOWN)
    try:
        with pytest.raises(PermissionError):
            ear_safety({"action": "status"})
    finally:
        set_trust(TRUST_LOCAL_OWNER)
