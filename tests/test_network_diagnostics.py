"""Unit tests for Network Diagnostics & Connectivity Engine.
Created and developed by Sajan Rai for Zaya.
"""
from __future__ import annotations

import json
import time
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


def test_dns_timeout_and_tcp_handshake_classification():
    # 1. Test DNS timeout handling
    with patch("actions.network_diagnostics.socket.gethostbyname", side_effect=lambda d: time.sleep(0.5) or "1.2.3.4"):
        dns_res = _benchmark_dns(timeout=0.05)
        for d, res in dns_res.items():
            assert "timeout" in res["status"]
            assert res["ip"] is None

    # 2. Test TCP handshake classification when ICMP fails
    with patch("subprocess.run", side_effect=Exception("ICMP blocked")), \
         patch("actions.network_diagnostics._check_tcp_latency", return_value=18.5):
        ping_res = _run_icmp_ping("1.1.1.1")
        assert ping_res["reachable"] is True
        assert ping_res["method"] == "TCP_handshake"
        assert ping_res["packet_loss_pct"] is None

        with with_trust(TRUST_LOCAL_OWNER):
            raw = network_diagnostics({"action": "ping", "target": "1.1.1.1"})
            res = json.loads(raw)
            assert "TCP handshake to 1.1.1.1: 18.5ms" in res["summary"]
            assert "packet loss not applicable" in res["summary"]


def test_genuine_dns_deadlines_and_hanging_workers():
    # 1. Normal resolution
    def fast_resolver(domain):
        return "93.184.216.34"

    with patch("actions.network_diagnostics.socket.gethostbyname", side_effect=fast_resolver):
        t0 = time.perf_counter()
        res_normal = _benchmark_dns(timeout=0.5)
        elapsed_normal = time.perf_counter() - t0
        assert elapsed_normal < 0.3
        for d, r in res_normal.items():
            assert r["ip"] == "93.184.216.34"
            assert r["status"] == "ok"
            assert r["latency_ms"] is not None

    # 2. One DNS request hangs (2.0s hang), others succeed fast
    def one_hang_resolver(domain):
        if "google" in domain:
            time.sleep(2.0)
            return "8.8.8.8"
        return "1.1.1.1"

    with patch("actions.network_diagnostics.socket.gethostbyname", side_effect=one_hang_resolver):
        t0 = time.perf_counter()
        res_one_hang = _benchmark_dns(timeout=0.08)
        elapsed_one_hang = time.perf_counter() - t0
        # Strictly bounded: must finish within ~0.25s, NEVER waiting 2.0s!
        assert elapsed_one_hang < 0.25
        assert "timeout" in res_one_hang["google.com"]["status"]
        assert res_one_hang["google.com"]["ip"] is None
        # Other domains that finished before deadline are preserved
        assert res_one_hang["cloudflare.com"]["ip"] == "1.1.1.1"
        assert res_one_hang["cloudflare.com"]["status"] == "ok"

    # 3. Multiple DNS requests hang
    def multi_hang_resolver(domain):
        if "google" in domain or "microsoft" in domain:
            time.sleep(2.0)
            return "8.8.8.8"
        return "1.1.1.1"

    with patch("actions.network_diagnostics.socket.gethostbyname", side_effect=multi_hang_resolver):
        t0 = time.perf_counter()
        res_multi_hang = _benchmark_dns(timeout=0.08)
        elapsed_multi_hang = time.perf_counter() - t0
        assert elapsed_multi_hang < 0.25
        assert "timeout" in res_multi_hang["google.com"]["status"]
        assert "timeout" in res_multi_hang["microsoft.com"]["status"]
        assert res_multi_hang["cloudflare.com"]["ip"] == "1.1.1.1"

    # 4. One domain fails while others succeed
    def one_fail_resolver(domain):
        if "github" in domain:
            raise RuntimeError("NXDOMAIN: domain not found")
        return "1.1.1.1"

    with patch("actions.network_diagnostics.socket.gethostbyname", side_effect=one_fail_resolver):
        res_fail = _benchmark_dns(timeout=0.5)
        assert "failed" in res_fail["github.com"]["status"]
        assert res_fail["github.com"]["ip"] is None
        assert res_fail["cloudflare.com"]["ip"] == "1.1.1.1"
        assert res_fail["cloudflare.com"]["status"] == "ok"

    # 5. All DNS requests fail
    with patch("actions.network_diagnostics.socket.gethostbyname", side_effect=RuntimeError("DNS offline")):
        res_all_fail = _benchmark_dns(timeout=0.5)
        for d, r in res_all_fail.items():
            assert "failed" in r["status"]
            assert r["ip"] is None

    # 6 & 7. Overall deadline enforced and subsequent operation is not delayed
    t_start = time.perf_counter()
    with patch("actions.network_diagnostics.socket.gethostbyname", side_effect=lambda _: time.sleep(3.0)):
        _benchmark_dns(timeout=0.06)
    elapsed_hang = time.perf_counter() - t_start
    assert elapsed_hang < 0.20

    # Subsequent operation executes immediately without block
    t_sub = time.perf_counter()
    sub_res = _get_local_ip()
    assert (time.perf_counter() - t_sub) < 0.05
    assert isinstance(sub_res, str)


