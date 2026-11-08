"""Tests for Wi-Fi Signal, Radio & Wireless Quality Sentinel."""
import json
import pytest
from unittest.mock import MagicMock, patch

from actions.wifi_sentinel import (
    wifi_sentinel,
    _parse_interface_output,
    _get_wifi_interface_telemetry,
    _get_saved_profiles,
    _scan_nearby_networks,
    TOOL,
)
from core.execution_policy import set_trust, TRUST_LOCAL_OWNER, TRUST_UNKNOWN

_SAMPLE_NETSH_INTERFACE = """
There is 1 interface on the system: 

    Name                   : Wi-Fi
    Description            : Intel(R) Wi-Fi 6 AX200 160MHz
    State                  : connected
    SSID                   : Office_5G
    Radio type             : 802.11ax
    Authentication         : WPA2-Personal
    Cipher                 : CCMP
    Band                   : 5 GHz
    Channel                : 36
    Receive rate (Mbps)    : 1200
    Transmit rate (Mbps)   : 1200
    Signal                 : 92% 
    Rssi                   : -48
"""

_SAMPLE_DISCONNECTED = """
There is 1 interface on the system: 

    Name                   : Wi-Fi
    Description            : Wi-Fi Adapter
    State                  : disconnected
"""


@pytest.fixture(autouse=True)
def ensure_owner_trust():
    set_trust(TRUST_LOCAL_OWNER)
    yield
    set_trust(TRUST_LOCAL_OWNER)


def test_tool_declaration():
    assert TOOL["name"] == "wifi_sentinel"
    assert "wi-fi" in TOOL["description"].lower()
    assert callable(TOOL["handler"])


def test_parse_interface_output_connected():
    data = _parse_interface_output(_SAMPLE_NETSH_INTERFACE)
    assert data["connected"] is True
    assert data["ssid"] == "Office_5G"
    assert data["band"] == "5 GHz"
    assert data["channel"] == 36
    assert data["radio_type"] == "802.11ax"
    assert data["signal_percent"] == 92
    assert data["signal_rating"] == "Excellent"
    assert data["rx_rate_mbps"] == 1200.0
    assert data["rssi_dbm"] == -48


def test_parse_interface_output_disconnected():
    data = _parse_interface_output(_SAMPLE_DISCONNECTED)
    assert data["connected"] is False
    assert data["signal_rating"] == "Disconnected"


def test_get_saved_profiles_mocked():
    mock_out = """
Profiles on interface Wi-Fi:
User profiles
-------------
    All User Profile     : Home_Network
    All User Profile     : Work_Guest
"""
    mock_proc = MagicMock(returncode=0, stdout=mock_out)
    with patch("subprocess.run", return_value=mock_proc):
        profiles = _get_saved_profiles()
        assert len(profiles) == 2
        assert "Home_Network" in profiles
        assert "Work_Guest" in profiles


def test_scan_nearby_networks_mocked():
    mock_out = """
Interface name : Wi-Fi 
SSID 1 : HomeNet
    Network type            : Infrastructure
    Authentication          : WPA2-Personal
    Encryption              : CCMP 
SSID 2 : GuestNet
    Network type            : Infrastructure
    Authentication          : Open
    Encryption              : None
"""
    mock_proc = MagicMock(returncode=0, stdout=mock_out)
    with patch("subprocess.run", return_value=mock_proc):
        nets = _scan_nearby_networks()
        assert len(nets) == 2
        assert nets[0]["ssid"] == "HomeNet"
        assert nets[1]["ssid"] == "GuestNet"


def test_wifi_sentinel_status_connected():
    mock_telemetry = {
        "connected": True,
        "ssid": "FastWifi",
        "band": "5 GHz",
        "radio_type": "802.11ax",
        "channel": 48,
        "signal_rating": "Excellent",
        "signal_percent": 90,
        "rssi_dbm": -50,
        "rx_rate_mbps": 866.0,
        "adapter": "Intel AX200",
    }
    with patch("actions.wifi_sentinel._get_wifi_interface_telemetry", return_value=mock_telemetry):
        res = json.loads(wifi_sentinel({"action": "status"}))
        assert res["status"] == "success"
        assert "FastWifi" in res["summary"]
        assert "Excellent (90%" in res["summary"]


def test_wifi_sentinel_status_disconnected():
    mock_telemetry = {"connected": False}
    with patch("actions.wifi_sentinel._get_wifi_interface_telemetry", return_value=mock_telemetry):
        res = json.loads(wifi_sentinel({"action": "status"}))
        assert res["status"] == "success"
        assert "disconnected" in res["summary"]


def test_wifi_sentinel_profiles():
    with patch("actions.wifi_sentinel._get_saved_profiles", return_value=["Network1", "Network2"]):
        res = json.loads(wifi_sentinel({"action": "profiles"}))
        assert res["status"] == "success"
        assert "Found 2 saved Wi-Fi profile(s)" in res["summary"]
        assert "Network1" in res["profiles"]


def test_wifi_sentinel_scan():
    mock_nets = [{"ssid": "NeighborWifi"}]
    with patch("actions.wifi_sentinel._scan_nearby_networks", return_value=mock_nets):
        res = json.loads(wifi_sentinel({"action": "scan"}))
        assert res["status"] == "success"
        assert "NeighborWifi" in res["summary"]


def test_wifi_sentinel_unknown_action():
    res = json.loads(wifi_sentinel({"action": "invalid"}))
    assert res["status"] == "error"
    assert "Unknown action" in res["message"]


def test_wifi_sentinel_requires_owner():
    set_trust(TRUST_UNKNOWN)
    try:
        with pytest.raises(PermissionError):
            wifi_sentinel({"action": "status"})
    finally:
        set_trust(TRUST_LOCAL_OWNER)


def test_wifi_sentinel_live():
    res = json.loads(wifi_sentinel({"action": "status"}))
    assert res["status"] == "success"
    assert "data" in res
