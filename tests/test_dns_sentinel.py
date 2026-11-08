"""Tests for Windows DNS Resolvers & Resolution Latency Sentinel."""
from __future__ import annotations

import json
import socket
from unittest.mock import MagicMock, patch
import pytest

from actions.dns_sentinel import (
    dns_sentinel,
    _parse_netsh_dns_output,
    get_dns_servers,
    resolve_host,
    benchmark_dns_resolution,
    get_dns_health_summary,
    TOOL,
)
from core.execution_policy import set_trust, TRUST_LOCAL_OWNER, TRUST_UNKNOWN
from core.fast_reflex import FastReflexRouter

_MOCK_NETSH_IPV4_DNS = """
Configuration for interface "Wi-Fi"
    DNS servers configured through DHCP:  1.1.1.1
                                          1.0.0.1
    Register with which suffix:           Primary only

Configuration for interface "Ethernet"
    DNS servers configured through DHCP:  None
    Register with which suffix:           Primary only
"""


@pytest.fixture(autouse=True)
def _owner_trust():
    set_trust(TRUST_LOCAL_OWNER)
    yield
    set_trust(TRUST_LOCAL_OWNER)


def test_owner_security_gate():
    set_trust(TRUST_UNKNOWN)
    with pytest.raises(PermissionError):
        dns_sentinel({"action": "summary"})


def test_tool_declaration():
    assert TOOL["name"] == "dns_sentinel"
    assert "parameters" in TOOL
    assert callable(TOOL["handler"])


def test_parse_netsh_dns_output():
    parsed = _parse_netsh_dns_output(_MOCK_NETSH_IPV4_DNS, "IPv4")
    assert "Wi-Fi" in parsed
    assert parsed["Wi-Fi"]["config_type"] == "DHCP"
    assert parsed["Wi-Fi"]["servers"] == ["1.1.1.1", "1.0.0.1"]
    assert "Ethernet" not in parsed  # "None" servers excluded


@patch("subprocess.run")
def test_get_dns_servers(mock_run):
    mock_run.return_value = MagicMock(returncode=0, stdout=_MOCK_NETSH_IPV4_DNS)
    servers = get_dns_servers()
    assert "1.1.1.1" in servers["active_ipv4_servers"]
    assert "1.0.0.1" in servers["active_ipv4_servers"]


@patch("socket.getaddrinfo")
def test_resolve_host_success(mock_addr):
    mock_addr.return_value = [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 80)),
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 80)),
    ]
    res = resolve_host("example.com")
    assert res["status"] == "Resolved"
    assert res["ips"] == ["93.184.216.34"]
    assert res["ip_count"] == 1
    assert "latency_ms" in res


@patch("socket.getaddrinfo")
def test_resolve_host_error(mock_addr):
    mock_addr.side_effect = socket.gaierror(-2, "Name or service not known")
    res = resolve_host("invalid.nonexistent.domain")
    assert res["status"] == "Error"
    assert res["ips"] == []
    assert "error" in res


@patch("actions.dns_sentinel.resolve_host")
def test_benchmark_dns_resolution(mock_res):
    mock_res.side_effect = lambda d: {
        "host": d,
        "status": "Resolved",
        "latency_ms": 15.0,
        "ips": ["1.1.1.1"],
    }
    benchmarks = benchmark_dns_resolution(["test1.com", "test2.com"])
    assert len(benchmarks) == 2
    assert benchmarks[0]["host"] == "test1.com"


@patch("actions.dns_sentinel.benchmark_dns_resolution")
@patch("actions.dns_sentinel.get_dns_servers")
def test_get_dns_health_summary(mock_srv, mock_bench):
    mock_srv.return_value = {
        "active_ipv4_servers": ["8.8.8.8"],
        "ipv4_interfaces": {"Wi-Fi": {}},
    }
    mock_bench.return_value = [
        {"host": "google.com", "status": "Resolved", "latency_ms": 10.0},
        {"host": "cloudflare.com", "status": "Resolved", "latency_ms": 12.0},
    ]

    summary = get_dns_health_summary()
    assert summary["status"] == "success"
    assert "Excellent" in summary["health_rating"]
    assert summary["average_latency_ms"] == 11.0
    assert summary["primary_dns_server"] == "8.8.8.8"


def test_dns_sentinel_actions():
    res_raw = dns_sentinel({"action": "summary"})
    res = json.loads(res_raw)
    assert res["status"] == "success"
    assert "data" in res

    srv_raw = dns_sentinel({"action": "servers"})
    srv = json.loads(srv_raw)
    assert srv["status"] == "success"
    assert "servers" in srv

    err_raw = dns_sentinel({"action": "invalid"})
    err = json.loads(err_raw)
    assert err["status"] == "error"


def test_fast_reflex_dns_health():
    router = FastReflexRouter()
    intent, score = router.match("dns status")
    assert intent == "DNS_HEALTH_QUERY"
    assert score >= 0.88

    res = router.execute_intent("DNS_HEALTH_QUERY")
    assert res.matched is True
    assert "DNS Health:" in res.ack
