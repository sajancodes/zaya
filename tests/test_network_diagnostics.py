"""Unit tests for Network Diagnostics & Connectivity Engine.
Created and developed by Sajan Rai for Zaya.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch
import pytest

from actions.network_diagnostics import (
    TOOL,
    _benchmark_dns,
    _check_tcp_latency,
    _get_active_interfaces,
    _get_local_ip,
    _get_public_ip_info,
    _run_icmp_ping,
    network_diagnostics,
)
from core.execution_policy import TRUST_EXTERNAL_MESSAGE, TRUST_LOCAL_OWNER, with_trust
from core.fast_reflex import FastReflexRouter
from core.tools.routing import ToolRouter


def test_network_diagnostics_requires_owner():
    with with_trust(TRUST_EXTERNAL_MESSAGE):
        with pytest.raises(PermissionError):
            network_diagnostics({"action": "status"})


def test_network_diagnostics_status():
    with with_trust(TRUST_LOCAL_OWNER):
        res_raw = network_diagnostics({"action": "status"})
        res = json.loads(res_raw)
        assert res["status"] == "success"
        assert "Network status:" in res["summary"]
        assert "local_ip" in res["data"]
        assert "hostname" in res["data"]
        assert isinstance(res["data"]["interfaces"], list)


def test_network_diagnostics_ping_mocked():
    with patch("actions.network_diagnostics._run_icmp_ping") as mock_ping:
        mock_ping.return_value = {
            "target": "1.1.1.1",
            "reachable": True,
            "min_ms": 12,
            "max_ms": 15,
            "avg_ms": 13,
            "packet_loss_pct": 0,
            "method": "ICMP",
        }
        with with_trust(TRUST_LOCAL_OWNER):
            res_raw = network_diagnostics({"action": "ping", "target": "1.1.1.1"})
            res = json.loads(res_raw)
            assert res["status"] == "success"
            assert "Ping to 1.1.1.1: avg 13ms" in res["summary"]
            assert res["data"]["avg_ms"] == 13


def test_network_diagnostics_ping_unreachable():
    with patch("actions.network_diagnostics._run_icmp_ping") as mock_ping:
        mock_ping.return_value = {
            "target": "192.0.2.1",
            "reachable": False,
            "min_ms": None,
            "max_ms": None,
            "avg_ms": None,
            "packet_loss_pct": 100,
            "method": "failed",
        }
        with with_trust(TRUST_LOCAL_OWNER):
            res_raw = network_diagnostics({"action": "ping", "target": "192.0.2.1"})
            res = json.loads(res_raw)
            assert res["status"] == "success"
            assert "failed: host unreachable" in res["summary"]


def test_network_diagnostics_dns():
    with patch("actions.network_diagnostics._benchmark_dns") as mock_dns:
        mock_dns.return_value = {
            "google.com": {"ip": "142.250.190.46", "latency_ms": 8.5, "status": "ok"},
            "cloudflare.com": {"ip": "104.16.132.229", "latency_ms": 6.2, "status": "ok"},
        }
        with with_trust(TRUST_LOCAL_OWNER):
            res_raw = network_diagnostics({"action": "dns"})
            res = json.loads(res_raw)
            assert res["status"] == "success"
            assert "2/2 domains resolved" in res["summary"]


def test_network_diagnostics_public_ip():
    with patch("actions.network_diagnostics._get_public_ip_info") as mock_pub:
        mock_pub.return_value = {
            "online": True,
            "public_ip": "203.0.113.195",
            "isp": "Test ISP",
            "location": "Kathmandu, Bagmati, Nepal",
        }
        with with_trust(TRUST_LOCAL_OWNER):
            res_raw = network_diagnostics({"action": "public_ip"})
            res = json.loads(res_raw)
            assert res["status"] == "success"
            assert "203.0.113.195" in res["summary"]
            assert "Test ISP" in res["summary"]


def test_network_diagnostics_interfaces():
    with with_trust(TRUST_LOCAL_OWNER):
        res_raw = network_diagnostics({"action": "interfaces"})
        res = json.loads(res_raw)
        assert res["status"] == "success"
        assert isinstance(res["data"], list)


def test_network_diagnostics_full():
    with with_trust(TRUST_LOCAL_OWNER):
        res_raw = network_diagnostics({"action": "full"})
        res = json.loads(res_raw)
        assert res["status"] == "success"
        assert "online" in res["data"]
        assert "ping" in res["data"]
        assert "dns" in res["data"]
        assert "interfaces" in res["data"]


def test_network_diagnostics_invalid_action():
    with with_trust(TRUST_LOCAL_OWNER):
        res_raw = network_diagnostics({"action": "invalid_xyz"})
        res = json.loads(res_raw)
        assert res["status"] == "error"
        assert "Unknown action" in res["message"]


def test_tool_declaration_schema():
    assert TOOL["name"] == "network_diagnostics"
    assert "status" in TOOL["parameters"]["properties"]["action"]["enum"]
    assert "ping" in TOOL["parameters"]["properties"]["action"]["enum"]
    assert callable(TOOL["handler"])


def test_fast_reflex_network_intents():
    router = FastReflexRouter()
    
    intent, score = router.match("ping")
    assert intent == "NETWORK_PING_QUERY"
    assert score >= 0.88

    intent, score = router.match("check internet")
    assert intent == "NETWORK_STATUS_QUERY"
    assert score >= 0.88

    intent, score = router.match("internet status")
    assert intent == "NETWORK_STATUS_QUERY"
    assert score >= 0.88

    # Fast reflex execution test
    res_ping = router.execute_intent("NETWORK_PING_QUERY")
    assert res_ping.matched is True
    assert "milliseconds" in res_ping.ack or "unreachable" in res_ping.ack

    res_status = router.execute_intent("NETWORK_STATUS_QUERY")
    assert res_status.matched is True
    assert "Internet is" in res_status.ack or "offline" in res_status.ack


def test_tool_router_maps_network_query():
    router = ToolRouter()
    declarations = [
        {"name": "network_diagnostics", "description": "ping and network status"},
        {"name": "web_search", "description": "search web"},
        {"name": "media_controller", "description": "media playback"},
    ]
    routed = router.route("check network latency and ping", declarations)
    names = [d["name"] for d in routed.declarations]
    assert "network_diagnostics" in names
