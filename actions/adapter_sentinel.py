"""Windows Network Adapter & Local IP Configuration Sentinel.
Created and developed by Sajan Rai for Zaya.

Inspects physical and virtual network adapters (Wi-Fi, Ethernet, VPN, Tailscale),
audits local IPv4/IPv6 addresses, MAC addresses, link speeds, and default router gateways.
"""
from __future__ import annotations

import json
import logging
import subprocess
from typing import Any, Dict, List, Optional
import psutil

from core.execution_policy import require_owner

logger = logging.getLogger(__name__)


def get_default_gateway() -> Optional[Dict[str, str]]:
    """Retrieve default router gateway and primary network interface via Windows route table."""
    try:
        proc = subprocess.run(
            ["route", "print", "0.0.0.0"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if proc.returncode != 0 or not proc.stdout.strip():
            return None

        lowest_metric_gw = None
        lowest_metric = 999999

        for line in proc.stdout.splitlines():
            line_str = line.strip()
            if line_str.startswith("0.0.0.0"):
                parts = line_str.split()
                if len(parts) >= 5 and parts[0] == "0.0.0.0":
                    gateway = parts[2]
                    interface_ip = parts[3]
                    try:
                        metric = int(parts[4])
                    except ValueError:
                        metric = 100

                    if metric < lowest_metric:
                        lowest_metric = metric
                        lowest_metric_gw = {
                            "gateway_ip": gateway,
                            "interface_ip": interface_ip,
                            "metric": metric,
                        }

        return lowest_metric_gw

    except (subprocess.TimeoutExpired, subprocess.SubprocessError, Exception) as exc:
        logger.warning("Failed to query default gateway: %s", exc)
        return None


def get_network_adapters(active_only: bool = True) -> List[Dict[str, Any]]:
    """Retrieve hardware and virtual network interface details."""
    stats = psutil.net_if_stats()
    addrs = psutil.net_if_addrs()

    adapters: List[Dict[str, Any]] = []

    for iface_name, st in stats.items():
        if active_only and not st.isup:
            continue
        if iface_name.startswith("Loopback"):
            continue

        iface_addrs = addrs.get(iface_name, [])

        ipv4_addr = None
        netmask = None
        ipv6_addrs = []
        mac_addr = None

        for a in iface_addrs:
            fam_name = getattr(a.family, "name", "")
            fam_val = getattr(a.family, "value", 0)

            if fam_name == "AF_INET":
                ipv4_addr = a.address
                netmask = a.netmask
            elif fam_name == "AF_INET6":
                ipv6_addrs.append(a.address)
            elif fam_name in ("AF_LINK", "AF_PACKET") or fam_val == -1:
                mac_addr = a.address

        adapters.append({
            "interface_name": iface_name,
            "is_connected": st.isup,
            "speed_mbps": st.speed,
            "mtu": st.mtu,
            "ipv4": ipv4_addr,
            "netmask": netmask,
            "ipv6": ipv6_addrs,
            "mac_address": mac_addr,
        })

    return adapters


def get_network_ip_summary() -> Dict[str, Any]:
    """Compile top-level network IP configuration, gateway, and primary adapter metrics."""
    adapters = get_network_adapters(active_only=True)
    gw_info = get_default_gateway()

    primary_ip = gw_info.get("interface_ip") if gw_info else None
    gateway_ip = gw_info.get("gateway_ip") if gw_info else None

    # Locate primary active interface
    primary_adapter = None
    vpn_adapters = []

    for a in adapters:
        if a["ipv4"] == primary_ip:
            primary_adapter = a
        if "tailscale" in a["interface_name"].lower() or "vpn" in a["interface_name"].lower():
            vpn_adapters.append(a)

    if not primary_adapter and adapters:
        primary_adapter = adapters[0]
        primary_ip = primary_adapter.get("ipv4")

    return {
        "status": "success",
        "primary_ip": primary_ip or "127.0.0.1",
        "default_gateway": gateway_ip or "Unknown",
        "primary_adapter_name": primary_adapter.get("interface_name") if primary_adapter else "Unknown",
        "mac_address": primary_adapter.get("mac_address") if primary_adapter else "Unknown",
        "link_speed_mbps": primary_adapter.get("speed_mbps") if primary_adapter else 0,
        "vpn_adapters": vpn_adapters,
        "all_active_adapters": adapters,
    }


def adapter_sentinel(parameters: dict, **_kwargs) -> str:
    """Dispatches network adapter inspection and IP address queries."""
    require_owner()
    action = str(parameters.get("action") or "summary").lower().strip()
    all_adapters = bool(parameters.get("all", False))

    if action in ("summary", "ip", "local_ip", "status"):
        summary = get_network_ip_summary()
        mac_str = f" (MAC: {summary['mac_address']})" if summary['mac_address'] != "Unknown" else ""
        speed_str = f" @ {summary['link_speed_mbps']} Mbps" if summary['link_speed_mbps'] else ""
        vpn_str = f", VPN: {summary['vpn_adapters'][0]['interface_name']} ({summary['vpn_adapters'][0]['ipv4']})" if summary['vpn_adapters'] else ""
        summary_text = (
            f"Local IP: {summary['primary_ip']} on '{summary['primary_adapter_name']}'{speed_str}{mac_str}. "
            f"Router Gateway: {summary['default_gateway']}{vpn_str}."
        )
        return json.dumps({"status": "success", "summary": summary_text, "data": summary}, indent=2)

    if action in ("gateway", "router"):
        gw = get_default_gateway()
        if not gw:
            return json.dumps({"status": "error", "message": "Default gateway could not be resolved."}, indent=2)
        summary_text = f"Default Router Gateway: {gw['gateway_ip']} (via local interface {gw['interface_ip']}, metric {gw['metric']})."
        return json.dumps({"status": "success", "summary": summary_text, "gateway": gw}, indent=2)

    if action in ("adapters", "list", "interfaces"):
        adapters = get_network_adapters(active_only=not all_adapters)
        summary_text = f"Retrieved {len(adapters)} network adapters."
        return json.dumps({"status": "success", "summary": summary_text, "adapters": adapters}, indent=2)

    if action in ("mac", "mac_address"):
        summary = get_network_ip_summary()
        summary_text = f"Primary MAC Address: {summary['mac_address']} (Adapter: {summary['primary_adapter_name']})."
        return json.dumps({"status": "success", "summary": summary_text, "mac_address": summary['mac_address'], "adapter": summary['primary_adapter_name']}, indent=2)

    return json.dumps({
        "status": "error",
        "message": f"Unknown action '{action}'. Choose from: summary, gateway, adapters, mac."
    }, indent=2)


TOOL = {
    "name": "adapter_sentinel",
    "description": "Inspect network adapters (Wi-Fi, Ethernet, Tailscale/VPN), retrieve local IPv4/IPv6 addresses, MAC addresses, link speeds, and default router gateway.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["summary", "gateway", "adapters", "mac"],
                "description": "Network adapter action to execute (default: 'summary').",
            },
            "all": {
                "type": "BOOLEAN",
                "description": "Whether to list inactive/disconnected adapters as well (default: false).",
            },
        },
    },
    "handler": adapter_sentinel,
}
