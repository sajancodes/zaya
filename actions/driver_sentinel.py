"""Hardware Device & System Driver Sentinel.
Created and developed by Sajan Rai for Zaya.

Inspects hardware devices, audits third-party OEM drivers, and detects device
manager problems or driver faults using native Windows pnputil telemetry.
"""
from __future__ import annotations

from collections import Counter
import json
import logging
import subprocess
from typing import Any, Dict, List, Optional

from core.execution_policy import require_owner

logger = logging.getLogger(__name__)


def _parse_pnputil_blocks(raw_text: str) -> List[Dict[str, str]]:
    """Parse colon-delimited key-value blocks from pnputil output."""
    items: List[Dict[str, str]] = []
    current: Dict[str, str] = {}

    for line in raw_text.splitlines():
        line_str = line.strip()
        if not line_str or line_str.startswith("Microsoft PnP Utility"):
            if current:
                items.append(current)
                current = {}
            continue

        if ":" in line_str:
            key, sep, val = line_str.partition(":")
            clean_key = key.strip().lower().replace(" ", "_")
            current[clean_key] = val.strip()

    if current:
        items.append(current)

    return items


def get_problem_devices() -> List[Dict[str, Any]]:
    """Detect devices with hardware errors, driver failures, or Device Manager warnings."""
    cmd = ["pnputil", "/enum-devices", "/problem"]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
        if proc.returncode != 0 or not proc.stdout.strip():
            return []

        # If no devices are found, pnputil outputs "No devices were found on the system."
        if "No devices were found" in proc.stdout:
            return []

        return _parse_pnputil_blocks(proc.stdout)

    except (subprocess.TimeoutExpired, subprocess.SubprocessError, Exception) as exc:
        logger.warning("pnputil problem query failed: %s", exc)
        return []


def get_installed_drivers(limit: int = 100) -> List[Dict[str, Any]]:
    """Audit installed third-party OEM hardware drivers."""
    cmd = ["pnputil", "/enum-drivers"]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
        if proc.returncode != 0 or not proc.stdout.strip():
            return []

        drivers = _parse_pnputil_blocks(proc.stdout)
        return drivers[:max(1, limit)]

    except (subprocess.TimeoutExpired, subprocess.SubprocessError, Exception) as exc:
        logger.warning("pnputil drivers query failed: %s", exc)
        return []


def get_devices_by_class(device_class: str) -> List[Dict[str, Any]]:
    """Retrieve connected devices belonging to a specific hardware class (e.g. Display, Net, MEDIA)."""
    cmd = ["pnputil", "/enum-devices", "/class", device_class.strip()]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
        if proc.returncode != 0 or not proc.stdout.strip():
            return []

        if "No devices were found" in proc.stdout:
            return []

        return _parse_pnputil_blocks(proc.stdout)

    except (subprocess.TimeoutExpired, subprocess.SubprocessError, Exception) as exc:
        logger.warning("pnputil class query failed for %s: %s", device_class, exc)
        return []


def get_hardware_health_summary() -> Dict[str, Any]:
    """Compile top-level hardware devices, problem checks, and driver counts."""
    problems = get_problem_devices()
    drivers = get_installed_drivers(limit=200)

    # Count driver distribution by manufacturer/provider
    provider_counter: Counter[str] = Counter()
    for d in drivers:
        prov = d.get("provider_name") or "Unknown"
        provider_counter[prov] += 1

    display_devices = get_devices_by_class("Display")
    net_devices = get_devices_by_class("Net")

    primary_gpu = display_devices[0].get("device_description", "Unknown GPU") if display_devices else "Standard Display"

    # Filter physical network controllers
    phys_net = [
        d.get("device_description") for d in net_devices
        if d.get("device_description") and not d.get("device_description", "").startswith("WAN Miniport")
    ]

    status_str = "Healthy (All hardware devices functioning normally)" if not problems else f"Attention: {len(problems)} device error(s) detected"

    return {
        "status": "success",
        "hardware_health": status_str,
        "problem_device_count": len(problems),
        "problem_devices": problems,
        "total_oem_drivers": len(drivers),
        "top_driver_providers": dict(provider_counter.most_common(5)),
        "primary_gpu": primary_gpu,
        "physical_network_adapters": phys_net[:4],
    }


def driver_sentinel(parameters: dict, **_kwargs) -> str:
    """Dispatches hardware device inspection and driver auditing actions."""
    require_owner()
    action = str(parameters.get("action") or "summary").lower().strip()
    device_class = str(parameters.get("class") or parameters.get("device_class") or "").strip()
    limit = int(parameters.get("limit") or 50)

    if action in ("summary", "health", "status"):
        data = get_hardware_health_summary()
        prob_note = f" Found {data['problem_device_count']} problem devices." if data['problem_device_count'] else " Zero device errors."
        summary_text = (
            f"Hardware Status: {data['hardware_health']}. "
            f"GPU: {data['primary_gpu']}. "
            f"OEM Drivers: {data['total_oem_drivers']} installed.{prob_note}"
        )
        return json.dumps({"status": "success", "summary": summary_text, "data": data}, indent=2)

    if action in ("problems", "issues", "errors"):
        problems = get_problem_devices()
        summary_text = f"Found {len(problems)} hardware devices reporting errors or warnings."
        return json.dumps({"status": "success", "summary": summary_text, "problems": problems}, indent=2)

    if action in ("drivers", "list_drivers"):
        drivers = get_installed_drivers(limit=limit)
        summary_text = f"Retrieved {len(drivers)} installed third-party OEM drivers."
        return json.dumps({"status": "success", "summary": summary_text, "drivers": drivers}, indent=2)

    if action in ("class", "devices", "by_class"):
        if not device_class:
            return json.dumps({
                "status": "error",
                "message": "Parameter 'class' is required (e.g. Display, Net, MEDIA, Camera, Bluetooth, DiskDrive)."
            }, indent=2)
        devices = get_devices_by_class(device_class)
        summary_text = f"Retrieved {len(devices)} devices in class '{device_class}'."
        return json.dumps({"status": "success", "summary": summary_text, "class": device_class, "devices": devices}, indent=2)

    return json.dumps({
        "status": "error",
        "message": f"Unknown action '{action}'. Choose from: summary, problems, drivers, class."
    }, indent=2)


TOOL = {
    "name": "driver_sentinel",
    "description": "Inspect hardware devices and drivers via pnputil: check for device manager errors/warnings, audit installed OEM drivers, and query device classes (Display, Net, Audio).",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["summary", "problems", "drivers", "class"],
                "description": "Driver action to execute (default: 'summary').",
            },
            "class": {
                "type": "STRING",
                "description": "Device class to inspect when action is 'class' (e.g. Display, Net, MEDIA, Camera, Bluetooth).",
            },
            "limit": {
                "type": "INTEGER",
                "description": "Maximum number of driver records to retrieve (default: 50).",
            },
        },
    },
    "handler": driver_sentinel,
}
