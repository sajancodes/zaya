"""Wi-Fi Signal, Radio & Wireless Quality Sentinel.
Created and developed by Sajan Rai for Zaya.

Inspects physical Wi-Fi radio metrics, signal quality percentage, RSSI dBm,
link speed (Mbps), frequency band (2.4/5/6 GHz), Wi-Fi standards (802.11ax/ac),
nearby networks, and saved network profiles via Windows netsh wlan.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from typing import Any, Dict, List, Optional

from core.execution_policy import require_owner


def _parse_interface_output(output: str) -> Dict[str, Any]:
    """Parse output of 'netsh wlan show interfaces' into structured telemetry."""
    data: Dict[str, Any] = {
        "connected": False,
        "interface_name": "Wi-Fi",
        "adapter": "Unknown",
        "ssid": None,
        "bssid": None,
        "state": "disconnected",
        "signal_percent": 0,
        "rssi_dbm": None,
        "radio_type": "Unknown",
        "band": "Unknown",
        "channel": None,
        "auth": "Unknown",
        "cipher": "Unknown",
        "rx_rate_mbps": 0.0,
        "tx_rate_mbps": 0.0,
        "signal_rating": "Disconnected",
    }

    for line in output.splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        key, val = [p.strip() for p in line.split(":", 1)]
        low_k = key.lower()

        if low_k == "name":
            data["interface_name"] = val
        elif low_k == "description":
            data["adapter"] = val
        elif low_k == "state":
            data["state"] = val.lower()
            data["connected"] = val.lower() == "connected"
        elif low_k == "ssid":
            data["ssid"] = val
        elif low_k in ("ap bssid", "bssid"):
            data["bssid"] = val
        elif low_k == "radio type":
            data["radio_type"] = val
        elif low_k == "band":
            data["band"] = val
        elif low_k == "channel":
            try:
                data["channel"] = int(val)
            except ValueError:
                data["channel"] = val
        elif low_k == "authentication":
            data["auth"] = val
        elif low_k == "cipher":
            data["cipher"] = val
        elif "receive rate" in low_k:
            try:
                data["rx_rate_mbps"] = float(val)
            except ValueError:
                pass
        elif "transmit rate" in low_k:
            try:
                data["tx_rate_mbps"] = float(val)
            except ValueError:
                pass
        elif low_k == "signal":
            m = re.search(r"(\d+)%", val)
            if m:
                data["signal_percent"] = int(m.group(1))
        elif low_k == "rssi":
            try:
                data["rssi_dbm"] = int(val)
            except ValueError:
                pass

    if data["connected"]:
        sig = data["signal_percent"]
        if sig >= 80:
            data["signal_rating"] = "Excellent"
        elif sig >= 60:
            data["signal_rating"] = "Good"
        elif sig >= 40:
            data["signal_rating"] = "Fair"
        else:
            data["signal_rating"] = "Weak"

    return data


def _get_wifi_interface_telemetry() -> Dict[str, Any]:
    """Query live wireless adapter status via netsh wlan show interfaces."""
    if os.name != "nt":
        return {
            "connected": False,
            "message": "Wi-Fi sentinel is only supported on Windows.",
            "signal_rating": "Unsupported",
        }

    try:
        proc = subprocess.run(
            ["netsh", "wlan", "show", "interfaces"],
            capture_output=True,
            text=True,
            timeout=3.0,
        )
        if proc.returncode == 0:
            return _parse_interface_output(proc.stdout)
    except Exception as e:
        return {"connected": False, "error": str(e), "signal_rating": "Error"}

    return {"connected": False, "signal_rating": "Disconnected"}


def _get_saved_profiles() -> List[str]:
    """List saved Wi-Fi connection profile names."""
    if os.name != "nt":
        return []

    profiles = []
    try:
        proc = subprocess.run(
            ["netsh", "wlan", "show", "profiles"],
            capture_output=True,
            text=True,
            timeout=3.0,
        )
        if proc.returncode == 0:
            for line in proc.stdout.splitlines():
                if ":" in line and "Profile" in line:
                    _, name = line.split(":", 1)
                    p_name = name.strip()
                    if p_name and p_name != "<None>":
                        profiles.append(p_name)
    except Exception:
        pass
    return profiles


def _scan_nearby_networks() -> List[Dict[str, Any]]:
    """Scan visible nearby Wi-Fi SSIDs."""
    if os.name != "nt":
        return []

    networks = []
    try:
        proc = subprocess.run(
            ["netsh", "wlan", "show", "networks"],
            capture_output=True,
            text=True,
            timeout=4.0,
        )
        if proc.returncode == 0:
            current: Dict[str, Any] = {}
            for line in proc.stdout.splitlines():
                line = line.strip()
                if line.startswith("SSID "):
                    if current.get("ssid"):
                        networks.append(current)
                    _, ssid = line.split(":", 1)
                    current = {"ssid": ssid.strip()}
                elif ":" in line and current:
                    k, v = [p.strip() for p in line.split(":", 1)]
                    if "Network type" in k:
                        current["type"] = v
                    elif "Authentication" in k:
                        current["auth"] = v
                    elif "Encryption" in k:
                        current["encryption"] = v
            if current.get("ssid"):
                networks.append(current)
    except Exception:
        pass
    return networks


def wifi_sentinel(parameters: dict, **_kwargs) -> str:
    """Dispatches Wi-Fi Signal, Wireless Radio and Network Quality actions."""
    require_owner()
    action = str(parameters.get("action") or "status").lower().strip()

    # 1. Active Wi-Fi Connection & Signal Telemetry
    if action in ("status", "summary", "signal"):
        data = _get_wifi_interface_telemetry()
        if not data.get("connected"):
            summary = "Wi-Fi is disconnected or no active wireless network is joined."
            return json.dumps({"status": "success", "summary": summary, "data": data}, indent=2)

        rssi_str = f", {data['rssi_dbm']} dBm" if data.get("rssi_dbm") else ""
        summary = (
            f"Wi-Fi Status: Connected to '{data['ssid']}' on {data['band']} ({data['radio_type']}, Ch {data['channel']}). "
            f"Signal: {data['signal_rating']} ({data['signal_percent']}%{rssi_str}). "
            f"Link Speed: {data['rx_rate_mbps']} Mbps. Adapter: {data['adapter']}."
        )
        return json.dumps({"status": "success", "summary": summary, "data": data}, indent=2)

    # 2. Saved Wi-Fi Profiles
    if action in ("profiles", "saved"):
        profiles = _get_saved_profiles()
        summary = f"Found {len(profiles)} saved Wi-Fi profile(s): " + ", ".join(profiles)
        return json.dumps({"status": "success", "summary": summary, "profiles": profiles}, indent=2)

    # 3. Scan Visible Networks
    if action in ("scan", "networks", "nearby"):
        networks = _scan_nearby_networks()
        ssids = [n["ssid"] for n in networks]
        summary = f"Discovered {len(networks)} visible wireless network(s): " + ", ".join(ssids)
        return json.dumps({"status": "success", "summary": summary, "networks": networks}, indent=2)

    return json.dumps({
        "status": "error",
        "message": f"Unknown action '{action}'. Choose from: status, profiles, scan."
    }, indent=2)


TOOL = {
    "name": "wifi_sentinel",
    "description": "Inspect live Wi-Fi signal quality percentage, RSSI dBm, radio standard (802.11ax/ac), 2.4/5GHz band, link speed (Mbps), nearby networks, and saved profiles.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["status", "profiles", "scan"],
                "description": "Wireless network action to execute (default: 'status').",
            },
        },
    },
    "handler": wifi_sentinel,
}
