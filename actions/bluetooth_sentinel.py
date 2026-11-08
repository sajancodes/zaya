"""Windows Bluetooth & Wireless Peripheral Sentinel.
Created and developed by Sajan Rai for Zaya.

Inspects Bluetooth radio status, discovers paired and active wireless peripherals
(headphones, earbuds, phones, mice, keyboards, controllers), and monitors connection states.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
from typing import Any, Dict, List, Optional

from core.execution_policy import require_owner

_IGNORED_SERVICE_PATTERNS = (
    r"avrcp transport",
    r"service discovery service",
    r"phonebook access",
    r"personal area network",
    r"headset audio gateway",
    r"object push service",
    r"rfcomm protocol",
    r"microsoft bluetooth enumerator",
    r"microsoft bluetooth le enumerator",
)


def _classify_device_type(name: str) -> str:
    """Classify device into user-friendly category based on name heuristics."""
    low = name.lower()
    if any(k in low for k in ("airpods", "buds", "earbuds", "headphones", "headset", "audio", "speaker")):
        return "audio"
    if any(k in low for k in ("phone", "iphone", "galaxy", "vivo", "pixel", "redmi", "xiaomi", "oppo")):
        return "phone"
    if any(k in low for k in ("mouse", "trackpad", "pointer")):
        return "mouse"
    if any(k in low for k in ("keyboard", "keypad")):
        return "keyboard"
    if any(k in low for k in ("xbox", "controller", "dualsense", "gamepad", "joystick")):
        return "gamepad"
    return "peripheral"


def _get_bluetooth_telemetry() -> Dict[str, Any]:
    """Query Bluetooth hardware and paired peripherals via PowerShell PnP."""
    if os.name != "nt":
        return {
            "adapter_present": False,
            "adapter_name": "Non-Windows OS",
            "devices": [],
            "connected_count": 0,
        }

    script = "Get-PnpDevice -Class Bluetooth | Select-Object FriendlyName, Status, Present"
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True,
            text=True,
            timeout=4.0,
        )
    except Exception as e:
        return {
            "adapter_present": False,
            "adapter_name": f"Query error: {e}",
            "devices": [],
            "connected_count": 0,
        }

    lines = proc.stdout.splitlines()
    adapter_name = "Unknown Bluetooth Adapter"
    adapter_present = False
    raw_devices = []

    for line in lines:
        line = line.strip()
        if not line or line.startswith("FriendlyName") or line.startswith("----"):
            continue
        parts = re.split(r"\s{2,}", line)
        if len(parts) >= 2:
            name = parts[0].strip()
            status = parts[1].strip() if len(parts) >= 2 else "Unknown"
            present = (parts[2].strip() == "True") if len(parts) >= 3 else False

            # Check if this line is the adapter itself
            if "adapter" in name.lower() or "radio" in name.lower():
                adapter_name = name
                adapter_present = (status == "OK" or present)
                continue

            # Skip low-level Windows driver services and enumerators
            if any(re.search(pat, name, re.IGNORECASE) for pat in _IGNORED_SERVICE_PATTERNS):
                continue

            raw_devices.append({
                "name": name,
                "status": status,
                "connected": present,
                "type": _classify_device_type(name),
            })

    # Deduplicate devices by name
    seen_names = set()
    unique_devices = []
    for d in raw_devices:
        clean_name = d["name"]
        if clean_name not in seen_names:
            seen_names.add(clean_name)
            unique_devices.append(d)

    connected_count = sum(1 for d in unique_devices if d["connected"])

    return {
        "adapter_present": adapter_present,
        "adapter_name": adapter_name,
        "devices": unique_devices,
        "connected_count": connected_count,
        "paired_count": len(unique_devices),
    }


def bluetooth_sentinel(parameters: dict, **_kwargs) -> str:
    """Dispatches Bluetooth hardware and peripheral discovery."""
    require_owner()
    action = str(parameters.get("action") or "summary").lower().strip()
    data = _get_bluetooth_telemetry()

    # 1. Radio / Adapter Status
    if action in ("status", "radio"):
        if data["adapter_present"]:
            summary = f"Bluetooth radio is ON and active ({data['adapter_name']})."
        else:
            summary = f"Bluetooth radio is OFF or adapter '{data['adapter_name']}' is disconnected."
        return json.dumps({"status": "success", "summary": summary, "data": data}, indent=2)

    # 2. All Paired Devices
    if action in ("devices", "list", "paired"):
        devs = data["devices"]
        if devs:
            summary = f"Found {len(devs)} paired Bluetooth device(s): " + ", ".join(f"{d['name']} ({'connected' if d['connected'] else 'disconnected'})" for d in devs)
        else:
            summary = "No paired Bluetooth devices detected."
        return json.dumps({"status": "success", "summary": summary, "data": devs}, indent=2)

    # 3. Only Connected Peripherals
    if action in ("connected", "active"):
        connected = [d for d in data["devices"] if d["connected"]]
        if connected:
            summary = f"Currently connected ({len(connected)}): " + ", ".join(f"{d['name']} [{d['type']}]" for d in connected)
        else:
            summary = "No Bluetooth peripherals are currently connected."
        return json.dumps({"status": "success", "summary": summary, "data": connected}, indent=2)

    # 4. Overall Bluetooth Health Summary
    if action == "summary":
        radio_str = "Active" if data["adapter_present"] else "Inactive"
        summary = (
            f"Bluetooth Sentinel: Radio is {radio_str} ({data['adapter_name']}). "
            f"{data['paired_count']} paired device(s), {data['connected_count']} currently connected."
        )
        return json.dumps({"status": "success", "summary": summary, "data": data}, indent=2)

    return json.dumps({
        "status": "error",
        "message": f"Unknown action '{action}'. Choose from: summary, status, devices, connected."
    }, indent=2)


TOOL = {
    "name": "bluetooth_sentinel",
    "description": "Inspect Bluetooth adapter status, discover paired wireless peripherals (headphones, phones, mice, gamepads), and check real-time connection states.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["summary", "status", "devices", "connected"],
                "description": "Bluetooth operation to perform (default: 'summary').",
            },
        },
    },
    "handler": bluetooth_sentinel,
}
