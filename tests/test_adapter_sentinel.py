"""Tests for Windows Network Adapter & Local IP Sentinel."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch
import pytest

from actions.adapter_sentinel import (
    adapter_sentinel,
    get_default_gateway,
    get_network_adapters,
    get_network_ip_summary,
    TOOL,
)
from core.execution_policy import set_trust, TRUST_LOCAL_OWNER, TRUST_UNKNOWN
from core.fast_reflex import FastReflexRouter

_MOCK_ROUTE_PRINT = """
===========================================================================
Interface List
===========================================================================
IPv4 Route Table
===========================================================================
Active Routes:
Network Destination        Netmask          Gateway       Interface  Metric
          0.0.0.0          0.0.0.0     192.168.1.1    192.168.1.50      25
        127.0.0.0        255.0.0.0         On-link         127.0.0.1     331
===========================================================================
"""


@pytest.fixture(autouse=True)
def _owner_trust():
    set_trust(TRUST_LOCAL_OWNER)
    yield
    set_trust(TRUST_LOCAL_OWNER)


def test_owner_security_gate():
    set_trust(TRUST_UNKNOWN)
    with pytest.raises(PermissionError):
        adapter_sentinel({"action": "summary"})


def test_tool_declaration():
    assert TOOL["name"] == "adapter_sentinel"
    assert "parameters" in TOOL
    assert callable(TOOL["handler"])


@patch("subprocess.run")
def test_get_default_gateway(mock_run):
    mock_run.return_value = MagicMock(returncode=0, stdout=_MOCK_ROUTE_PRINT)
    gw = get_default_gateway()
    assert gw is not None
    assert gw["gateway_ip"] == "192.168.1.1"
    assert gw["interface_ip"] == "192.168.1.50"
    assert gw["metric"] == 25


@patch("psutil.net_if_addrs")
@patch("psutil.net_if_stats")
def test_get_network_adapters(mock_stats, mock_addrs):
    mock_stats.return_value = {
        "Wi-Fi": MagicMock(isup=True, speed=866, mtu=1500),
        "Ethernet": MagicMock(isup=False, speed=0, mtu=1500),
    }

    fam_v4 = MagicMock()
    fam_v4.name = "AF_INET"
    fam_v4.value = 2

    fam_mac = MagicMock()
    fam_mac.name = "AF_LINK"
    fam_mac.value = -1

    mock_addr_v4 = MagicMock(family=fam_v4, address="192.168.1.50", netmask="255.255.255.0")
    mock_addr_mac = MagicMock(family=fam_mac, address="AA-BB-CC-DD-EE-FF")

    mock_addrs.return_value = {
        "Wi-Fi": [mock_addr_v4, mock_addr_mac],
        "Ethernet": [],
    }

    adapters = get_network_adapters(active_only=True)
    assert len(adapters) == 1
    assert adapters[0]["interface_name"] == "Wi-Fi"
    assert adapters[0]["ipv4"] == "192.168.1.50"
    assert adapters[0]["mac_address"] == "AA-BB-CC-DD-EE-FF"
    assert adapters[0]["speed_mbps"] == 866


@patch("actions.adapter_sentinel.get_default_gateway")
@patch("actions.adapter_sentinel.get_network_adapters")
def test_get_network_ip_summary(mock_adap, mock_gw):
    mock_gw.return_value = {
        "gateway_ip": "192.168.1.1",
        "interface_ip": "192.168.1.50",
    }
    mock_adap.return_value = [
        {
            "interface_name": "Wi-Fi",
            "ipv4": "192.168.1.50",
            "mac_address": "AA-BB-CC-DD-EE-FF",
            "speed_mbps": 866,
        },
        {
            "interface_name": "Tailscale",
            "ipv4": "100.1.2.3",
            "mac_address": None,
            "speed_mbps": 1000,
        },
    ]

    summary = get_network_ip_summary()
    assert summary["status"] == "success"
    assert summary["primary_ip"] == "192.168.1.50"
    assert summary["default_gateway"] == "192.168.1.1"
    assert summary["primary_adapter_name"] == "Wi-Fi"
    assert summary["mac_address"] == "AA-BB-CC-DD-EE-FF"
    assert len(summary["vpn_adapters"]) == 1


def test_adapter_sentinel_actions():
    res_raw = adapter_sentinel({"action": "summary"})
    res = json.loads(res_raw)
    assert res["status"] == "success"
    assert "data" in res

    mac_raw = adapter_sentinel({"action": "mac"})
    mac = json.loads(mac_raw)
    assert mac["status"] == "success"
    assert "mac_address" in mac

    err_raw = adapter_sentinel({"action": "invalid"})
    err = json.loads(err_raw)
    assert err["status"] == "error"


def test_fast_reflex_local_ip():
    router = FastReflexRouter()
    intent, score = router.match("what is my local ip")
    assert intent == "LOCAL_IP_QUERY"
    assert score >= 0.88

    res = router.execute_intent("LOCAL_IP_QUERY")
    assert res.matched is True
    assert "Your local IP is" in res.ack
