"""Windows DNS Resolvers & Resolution Latency Sentinel.
Created and developed by Sajan Rai for Zaya.

Inspects active IPv4/IPv6 DNS server configurations across network adapters (Wi-Fi, Ethernet, Tailscale),
benchmarks real-time domain resolution latencies, and audits DNS lookup health.
"""
from __future__ import annotations

import json
import logging
import re
import socket
import subprocess
import time
from typing import Any, Dict, List, Optional

from core.execution_policy import require_owner

logger = logging.getLogger(__name__)

DEFAULT_BENCHMARK_DOMAINS = ["google.com", "cloudflare.com", "github.com"]


def _parse_netsh_dns_output(raw_text: str, ip_version: str = "IPv4") -> Dict[str, Dict[str, Any]]:
    """Parse netsh interface dnsservers output."""
    interfaces: Dict[str, Dict[str, Any]] = {}
    current_iface: Optional[str] = None
    current_servers: List[str] = []
    config_type = "DHCP"

    for line in raw_text.splitlines():
        line_str = line.strip()
        if not line_str:
            continue

        if line_str.startswith("Configuration for interface"):
            if current_iface and current_servers:
                interfaces[current_iface] = {
                    "interface": current_iface,
                    "ip_version": ip_version,
                    "config_type": config_type,
                    "servers": current_servers,
                }
            match = re.search(r'"([^"]+)"', line_str)
            current_iface = match.group(1) if match else "Unknown"
            current_servers = []
            config_type = "DHCP"
            continue

        if "Statically Configured DNS Servers" in line_str:
            config_type = "Static"
            val = line_str.partition(":")[2].strip()
            if val and val != "None":
                current_servers.append(val)
            continue

        if "DNS servers configured through DHCP" in line_str:
            config_type = "DHCP"
            val = line_str.partition(":")[2].strip()
            if val and val != "None":
                current_servers.append(val)
            continue

        if current_iface and line_str and not line_str.startswith("Register with") and not line_str.startswith("Configuration"):
            # Check if line looks like an IP address or continuation server
            clean_val = line_str.strip()
            if clean_val and clean_val != "None" and ("." in clean_val or ":" in clean_val):
                current_servers.append(clean_val)

    if current_iface and current_servers:
        interfaces[current_iface] = {
            "interface": current_iface,
            "ip_version": ip_version,
            "config_type": config_type,
            "servers": current_servers,
        }

    return interfaces


def get_dns_servers() -> Dict[str, Any]:
    """Retrieve active DNS server IPs for IPv4 and IPv6 across all interfaces."""
    v4_interfaces: Dict[str, Any] = {}
    v6_interfaces: Dict[str, Any] = {}

    try:
        p4 = subprocess.run(["netsh", "interface", "ipv4", "show", "dnsservers"], capture_output=True, text=True, timeout=5)
        if p4.returncode == 0:
            v4_interfaces = _parse_netsh_dns_output(p4.stdout, "IPv4")
    except Exception as exc:
        logger.warning("Failed to query IPv4 DNS servers: %s", exc)

    try:
        p6 = subprocess.run(["netsh", "interface", "ipv6", "show", "dnsservers"], capture_output=True, text=True, timeout=5)
        if p6.returncode == 0:
            v6_interfaces = _parse_netsh_dns_output(p6.stdout, "IPv6")
    except Exception as exc:
        logger.warning("Failed to query IPv6 DNS servers: %s", exc)

    # Consolidate primary active DNS servers
    active_servers: List[str] = []
    for iface_data in v4_interfaces.values():
        active_servers.extend(iface_data.get("servers", []))

    return {
        "active_ipv4_servers": list(dict.fromkeys(active_servers)),
        "ipv4_interfaces": v4_interfaces,
        "ipv6_interfaces": v6_interfaces,
    }


def resolve_host(hostname: str) -> Dict[str, Any]:
    """Resolve a specific hostname and measure exact resolution latency in ms."""
    clean_host = hostname.strip().lower()
    t0 = time.perf_counter()
    try:
        results = socket.getaddrinfo(clean_host, None)
        dt_ms = round((time.perf_counter() - t0) * 1000, 2)
        ips = list(dict.fromkeys(r[4][0] for r in results))
        return {
            "host": clean_host,
            "status": "Resolved",
            "latency_ms": dt_ms,
            "ips": ips,
            "ip_count": len(ips),
        }
    except socket.gaierror as err:
        dt_ms = round((time.perf_counter() - t0) * 1000, 2)
        return {
            "host": clean_host,
            "status": "Error",
            "latency_ms": dt_ms,
            "error": str(err),
            "ips": [],
        }


def benchmark_dns_resolution(domains: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """Benchmark DNS resolution latency across high-availability domains."""
    targets = domains or DEFAULT_BENCHMARK_DOMAINS
    benchmarks: List[Dict[str, Any]] = []
    for domain in targets:
        benchmarks.append(resolve_host(domain))
    return benchmarks


def get_dns_health_summary() -> Dict[str, Any]:
    """Compile comprehensive DNS status, active nameservers, and resolution speeds."""
    servers_info = get_dns_servers()
    benchmarks = benchmark_dns_resolution()

    latencies = [b["latency_ms"] for b in benchmarks if b["status"] == "Resolved"]
    avg_latency = round(sum(latencies) / len(latencies), 1) if latencies else 0.0

    if avg_latency == 0.0:
        health_rating = "Offline / Unreachable"
    elif avg_latency < 30.0:
        health_rating = "Excellent (Ultra-fast resolution)"
    elif avg_latency < 80.0:
        health_rating = "Good (Normal resolution)"
    else:
        health_rating = "Degraded (High DNS lookup latency)"

    active_dns = servers_info.get("active_ipv4_servers", [])
    primary_dns = active_dns[0] if active_dns else "System Default"

    return {
        "status": "success",
        "health_rating": health_rating,
        "average_latency_ms": avg_latency,
        "primary_dns_server": primary_dns,
        "all_active_servers": active_dns,
        "benchmarks": benchmarks,
        "adapters": servers_info.get("ipv4_interfaces", {}),
    }


def dns_sentinel(parameters: dict, **_kwargs) -> str:
    """Dispatches DNS server discovery, resolution benchmarking, and domain testing."""
    require_owner()
    action = str(parameters.get("action") or "summary").lower().strip()
    host = str(parameters.get("host") or parameters.get("domain") or "").strip()

    if action in ("summary", "health", "status"):
        summary = get_dns_health_summary()
        summary_text = (
            f"DNS Health: {summary['health_rating']}. "
            f"Primary DNS: {summary['primary_dns_server']}. "
            f"Avg Latency: {summary['average_latency_ms']} ms across benchmarks."
        )
        return json.dumps({"status": "success", "summary": summary_text, "data": summary}, indent=2)

    if action in ("servers", "nameservers", "list_servers"):
        servers = get_dns_servers()
        summary_text = f"Found {len(servers['active_ipv4_servers'])} active DNS servers configured: {', '.join(servers['active_ipv4_servers'])}."
        return json.dumps({"status": "success", "summary": summary_text, "servers": servers}, indent=2)

    if action in ("benchmark", "speed", "test"):
        benchmarks = benchmark_dns_resolution()
        avg = round(sum(b['latency_ms'] for b in benchmarks if b['status'] == 'Resolved') / max(1, len(benchmarks)), 1)
        summary_text = f"DNS benchmark complete across {len(benchmarks)} endpoints (Avg latency: {avg} ms)."
        return json.dumps({"status": "success", "summary": summary_text, "average_latency_ms": avg, "results": benchmarks}, indent=2)

    if action in ("resolve", "lookup"):
        if not host:
            return json.dumps({"status": "error", "message": "Parameter 'host' or 'domain' is required."}, indent=2)
        res = resolve_host(host)
        if res["status"] == "Resolved":
            summary_text = f"Resolved '{host}' in {res['latency_ms']} ms -> {', '.join(res['ips'])}."
        else:
            summary_text = f"Failed to resolve '{host}' ({res.get('error', 'Unknown error')})."
        return json.dumps({"status": "success", "summary": summary_text, "result": res}, indent=2)

    return json.dumps({
        "status": "error",
        "message": f"Unknown action '{action}'. Choose from: summary, servers, benchmark, resolve."
    }, indent=2)


TOOL = {
    "name": "dns_sentinel",
    "description": "Inspect active IPv4/IPv6 DNS nameservers, benchmark DNS resolution speed, and perform instant domain lookups with latency metrics.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["summary", "servers", "benchmark", "resolve"],
                "description": "DNS action to execute (default: 'summary').",
            },
            "host": {
                "type": "STRING",
                "description": "Domain or hostname to resolve when action is 'resolve'.",
            },
        },
    },
    "handler": dns_sentinel,
}
