"""Network Diagnostics & Connectivity Telemetry Engine.
Created and developed by Sajan Rai for Zaya.

Provides real-time latency ping testing, TCP socket latency fallback,
DNS resolution benchmarks, network adapter statistics, and public IP lookup.
All queries are designed with strict timeouts for zero-hang assistant responses.
"""
from __future__ import annotations

import json
import re
import socket
import subprocess
import time
import urllib.request
from typing import Any, Dict, List, Optional

import psutil

from core.execution_policy import require_owner


def _check_tcp_latency(host: str, port: int = 53, timeout: float = 1.2) -> Optional[float]:
    """Measure TCP handshake time in milliseconds with a strict timeout."""
    start = time.perf_counter()
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect((host, port))
        latency = (time.perf_counter() - start) * 1000.0
        return round(latency, 1)
    except Exception:
        return None
    finally:
        sock.close()


def _run_icmp_ping(target: str, count: int = 2, timeout_ms: int = 800) -> Dict[str, Any]:
    """Run Windows ping command, returning round-trip time and packet loss."""
    # Sanitize target to prevent command injection
    clean_target = re.sub(r"[^\w\.-]", "", target)
    if not clean_target:
        clean_target = "1.1.1.1"

    cmd = ["ping", "-n", str(count), "-w", str(timeout_ms), clean_target]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=3.0)
        output = proc.stdout
        
        # Parse packet loss: e.g. "Lost = 0 (0% loss)"
        loss_match = re.search(r"\((\d+)%\s+loss\)", output, re.IGNORECASE)
        loss_pct = int(loss_match.group(1)) if loss_match else 100

        # Parse round-trip times: e.g. "Minimum = 14ms, Maximum = 16ms, Average = 15ms"
        times_match = re.search(r"Minimum\s*=\s*(\d+)ms,\s*Maximum\s*=\s*(\d+)ms,\s*Average\s*=\s*(\d+)ms", output, re.IGNORECASE)
        if times_match:
            return {
                "target": clean_target,
                "reachable": True,
                "min_ms": int(times_match.group(1)),
                "max_ms": int(times_match.group(2)),
                "avg_ms": int(times_match.group(3)),
                "packet_loss_pct": loss_pct,
                "method": "ICMP",
            }
    except Exception:
        pass

    # If ICMP fails (firewall/blocked), fallback to TCP socket latency on port 443 / 80 / 53
    tcp_ms = _check_tcp_latency(clean_target, 443) or _check_tcp_latency(clean_target, 80) or _check_tcp_latency(clean_target, 53)
    if tcp_ms is not None:
        return {
            "target": clean_target,
            "reachable": True,
            "min_ms": tcp_ms,
            "max_ms": tcp_ms,
            "avg_ms": tcp_ms,
            "packet_loss_pct": 0,
            "method": "TCP_handshake",
        }

    return {
        "target": clean_target,
        "reachable": False,
        "min_ms": None,
        "max_ms": None,
        "avg_ms": None,
        "packet_loss_pct": 100,
        "method": "failed",
    }


def _get_local_ip() -> str:
    """Retrieve primary local IPv4 address."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Does not send actual traffic, just resolves local routing interface
        s.connect(("1.1.1.1", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


def _get_active_interfaces() -> List[Dict[str, Any]]:
    """List network adapters with link status, duplex, speed, and IO counters."""
    stats = psutil.net_if_stats()
    counters = psutil.net_io_counters(pernic=True)
    interfaces = []
    
    for iface_name, stat in stats.items():
        if stat.isup:
            cnt = counters.get(iface_name)
            mb_sent = round(cnt.bytes_sent / (1024 * 1024), 2) if cnt else 0.0
            mb_recv = round(cnt.bytes_recv / (1024 * 1024), 2) if cnt else 0.0
            interfaces.append({
                "interface": iface_name,
                "speed_mbps": stat.speed,
                "duplex": str(stat.duplex).replace("NicDuplex.", ""),
                "is_up": stat.isup,
                "mb_sent": mb_sent,
                "mb_recv": mb_recv,
            })
    return interfaces


def _benchmark_dns() -> Dict[str, Any]:
    """Measure DNS resolution speed for core domains."""
    test_domains = ["google.com", "cloudflare.com", "github.com", "microsoft.com"]
    results = {}
    for domain in test_domains:
        start = time.perf_counter()
        try:
            ip = socket.gethostbyname(domain)
            elapsed_ms = round((time.perf_counter() - start) * 1000.0, 1)
            results[domain] = {"ip": ip, "latency_ms": elapsed_ms, "status": "ok"}
        except Exception as e:
            results[domain] = {"ip": None, "latency_ms": None, "status": f"failed: {e}"}
    return results


def _get_public_ip_info() -> Dict[str, Any]:
    """Fetch public IP and ISP details with strict 2-second timeout."""
    try:
        req = urllib.request.Request(
            "http://ip-api.com/json/?fields=status,message,country,city,regionName,isp,org,as,query",
            headers={"User-Agent": "Zaya-Diagnostics/1.0"}
        )
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("status") == "success":
                return {
                    "online": True,
                    "public_ip": data.get("query"),
                    "isp": data.get("isp"),
                    "org": data.get("org"),
                    "location": f"{data.get('city')}, {data.get('regionName')}, {data.get('country')}",
                    "asn": data.get("as"),
                }
    except Exception:
        pass

    # Fast fallback for just IP
    try:
        req = urllib.request.Request(
            "https://api.ipify.org?format=json",
            headers={"User-Agent": "Zaya-Diagnostics/1.0"}
        )
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return {
                "online": True,
                "public_ip": data.get("ip"),
                "isp": "Unknown",
                "location": "Unknown",
            }
    except Exception:
        pass

    return {
        "online": False,
        "public_ip": None,
        "message": "Public IP service unreachable.",
    }


def network_diagnostics(parameters: dict, **_kwargs) -> str:
    """Dispatches network diagnostic tasks."""
    require_owner()
    action = str(parameters.get("action") or "status").lower().strip()
    target = str(parameters.get("target") or "1.1.1.1").strip()

    # 1. Ping Latency Check
    if action in ("ping", "latency"):
        res = _run_icmp_ping(target)
        if res.get("reachable"):
            summary = (
                f"Ping to {res['target']}: avg {res['avg_ms']}ms "
                f"(min {res['min_ms']}ms / max {res['max_ms']}ms), "
                f"packet loss {res['packet_loss_pct']}% via {res['method']}."
            )
        else:
            summary = f"Ping to {res['target']} failed: host unreachable (100% loss)."
        return json.dumps({"status": "success", "summary": summary, "data": res}, indent=2)

    # 2. General Connectivity Status
    if action in ("status", "connectivity"):
        is_online = _check_tcp_latency("1.1.1.1", 53, timeout=1.0) is not None
        local_ip = _get_local_ip()
        interfaces = _get_active_interfaces()
        hostname = socket.gethostname()
        
        status_text = "Online and connected" if is_online else "Offline / No Internet access"
        summary = (
            f"Network status: {status_text}. Local IP: {local_ip} on host '{hostname}'. "
            f"{len(interfaces)} active interface(s)."
        )
        return json.dumps({
            "status": "success",
            "summary": summary,
            "data": {
                "online": is_online,
                "local_ip": local_ip,
                "hostname": hostname,
                "interfaces": interfaces,
            }
        }, indent=2)

    # 3. DNS Benchmark
    if action == "dns":
        dns_res = _benchmark_dns()
        resolved = sum(1 for v in dns_res.values() if v.get("status") == "ok")
        summary = f"DNS resolution benchmark: {resolved}/{len(dns_res)} domains resolved successfully."
        return json.dumps({"status": "success", "summary": summary, "data": dns_res}, indent=2)

    # 4. Public IP & ISP
    if action in ("public_ip", "ip", "isp"):
        pub = _get_public_ip_info()
        if pub.get("online"):
            summary = f"Public IP: {pub.get('public_ip')}, ISP: {pub.get('isp')}, Location: {pub.get('location')}."
        else:
            summary = "Unable to determine public IP (network may be offline)."
        return json.dumps({"status": "success", "summary": summary, "data": pub}, indent=2)

    # 5. Interfaces List
    if action in ("interfaces", "adapters"):
        ifaces = _get_active_interfaces()
        summary = f"Found {len(ifaces)} active network interface(s)."
        return json.dumps({"status": "success", "summary": summary, "data": ifaces}, indent=2)

    # 6. Full Comprehensive Diagnostic
    if action == "full":
        is_online = _check_tcp_latency("1.1.1.1", 53, timeout=1.0) is not None
        ping_res = _run_icmp_ping("1.1.1.1")
        dns_res = _benchmark_dns()
        pub_info = _get_public_ip_info()
        local_ip = _get_local_ip()
        interfaces = _get_active_interfaces()

        summary = (
            f"Network: {'Online' if is_online else 'Offline'}. Local IP: {local_ip}. "
            f"Public IP: {pub_info.get('public_ip', 'Unknown')}. "
            f"Avg Ping: {ping_res.get('avg_ms')}ms. Active interfaces: {len(interfaces)}."
        )
        return json.dumps({
            "status": "success",
            "summary": summary,
            "data": {
                "online": is_online,
                "local_ip": local_ip,
                "public_info": pub_info,
                "ping": ping_res,
                "dns": dns_res,
                "interfaces": interfaces,
            }
        }, indent=2)

    return json.dumps({
        "status": "error",
        "message": f"Unknown action '{action}'. Choose from: status, ping, dns, public_ip, interfaces, full."
    }, indent=2)


TOOL = {
    "name": "network_diagnostics",
    "description": "Run non-destructive network connectivity, ping latency tests, DNS resolution benchmarks, active network adapters inspection, and public IP lookup.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["status", "ping", "dns", "public_ip", "interfaces", "full"],
                "description": "The diagnostic action to perform (default: 'status').",
            },
            "target": {
                "type": "STRING",
                "description": "Target IP address or domain to ping (default: '1.1.1.1').",
            },
        },
    },
    "handler": network_diagnostics,
}
