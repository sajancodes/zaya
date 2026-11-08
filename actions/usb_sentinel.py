"""Windows USB & Removable Device Sentinel.
Created and developed by Sajan Rai for Zaya.

Inspects, monitors, and audits connected USB peripherals, external flash drives,
human interface devices (HID), and host controllers using native pnputil and Win32 telemetry.
"""
from __future__ import annotations

import ctypes
import json
import logging
import subprocess
from typing import Any, Dict, List, Optional
import psutil

from core.execution_policy import require_owner

logger = logging.getLogger(__name__)

# Win32 GetDriveType constants
DRIVE_REMOVABLE = 2
DRIVE_FIXED = 3


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


def _categorize_usb_device(class_name: str, description: str) -> str:
    """Categorize USB device based on class name and description."""
    c = class_name.lower()
    d = description.lower()

    if "hub" in d or "host controller" in d or "root_hub" in d:
        return "Host Controller / Hub"
    if "hid" in c or "keyboard" in d or "mouse" in d or "input" in d or "touchpad" in d:
        return "Input / Peripheral"
    if "camera" in c or "camera" in d or "webcam" in d:
        return "Camera / Imaging"
    if "media" in c or "audio" in d or "sound" in d or "headset" in d:
        return "Audio / Media"
    if "disk" in c or "storage" in d or "mass storage" in d:
        return "Storage"
    if "bluetooth" in c or "bluetooth" in d:
        return "Wireless / Bluetooth"

    return "General USB Device"


def get_connected_usb_devices(include_internal_hubs: bool = False) -> List[Dict[str, Any]]:
    """Retrieve all currently connected USB devices, peripherals, and storage adapters."""
    cmd = ["pnputil", "/enum-devices", "/connected"]
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

        all_devices = _parse_pnputil_blocks(proc.stdout)
        usb_devices: List[Dict[str, Any]] = []

        for dev in all_devices:
            instance_id = dev.get("instance_id", "")
            class_name = dev.get("class_name", "")
            desc = dev.get("device_description", "Unknown Device")

            # Check if device is connected via USB
            is_usb = (
                instance_id.startswith("USB\\")
                or instance_id.startswith("USBSTOR\\")
                or class_name.lower() == "usb"
                or "usb" in desc.lower()
            )

            if not is_usb:
                continue

            category = _categorize_usb_device(class_name, desc)
            if not include_internal_hubs and category == "Host Controller / Hub":
                continue

            usb_devices.append({
                "device_description": desc,
                "category": category,
                "class_name": class_name,
                "manufacturer": dev.get("manufacturer_name", "Unknown"),
                "status": dev.get("status", "Started"),
                "driver_name": dev.get("driver_name", ""),
                "instance_id": instance_id,
            })

        return usb_devices

    except (subprocess.TimeoutExpired, subprocess.SubprocessError, Exception) as exc:
        logger.warning("pnputil USB query failed: %s", exc)
        return []


def get_removable_drives() -> List[Dict[str, Any]]:
    """Detect mounted removable USB storage media, flash drives, and external cards."""
    removable: List[Dict[str, Any]] = []
    kernel32 = getattr(ctypes.windll, "kernel32", None)

    for part in psutil.disk_partitions(all=False):
        is_removable = "removable" in part.opts.lower()
        if not is_removable and kernel32:
            try:
                drive_type = kernel32.GetDriveTypeW(part.mountpoint)
                if drive_type == DRIVE_REMOVABLE:
                    is_removable = True
            except Exception:
                pass

        if is_removable:
            try:
                usage = psutil.disk_usage(part.mountpoint)
                removable.append({
                    "mountpoint": part.mountpoint,
                    "device": part.device,
                    "filesystem": part.fstype,
                    "total_gb": round(usage.total / (1024**3), 2),
                    "used_gb": round(usage.used / (1024**3), 2),
                    "free_gb": round(usage.free / (1024**3), 2),
                    "percent_used": usage.percent,
                })
            except (PermissionError, OSError):
                removable.append({
                    "mountpoint": part.mountpoint,
                    "device": part.device,
                    "filesystem": part.fstype,
                    "status": "Inaccessible / Unmounted",
                })

    return removable


def get_usb_summary() -> Dict[str, Any]:
    """Compile comprehensive status of plugged-in USB hardware and removable storage."""
    devices = get_connected_usb_devices(include_internal_hubs=False)
    drives = get_removable_drives()

    # Filter peripherals (keyboards, mice, webcams, audio)
    peripherals = [d["device_description"] for d in devices if d["category"] in ("Input / Peripheral", "Camera / Imaging", "Audio / Media")]

    return {
        "status": "success",
        "connected_usb_devices_count": len(devices),
        "removable_drives_count": len(drives),
        "removable_drives": drives,
        "peripherals": peripherals,
        "all_connected_devices": devices,
    }


def usb_sentinel(parameters: dict, **_kwargs) -> str:
    """Dispatches USB device inspection, removable storage, and peripheral audits."""
    require_owner()
    action = str(parameters.get("action") or "summary").lower().strip()
    include_hubs = bool(parameters.get("include_hubs", False))

    if action in ("summary", "status", "health"):
        summary = get_usb_summary()
        drives_str = f", {summary['removable_drives_count']} removable storage drive(s)" if summary["removable_drives_count"] else ""
        summary_text = (
            f"USB Diagnostics: {summary['connected_usb_devices_count']} connected USB device(s){drives_str}. "
            f"Active peripherals: {', '.join(summary['peripherals'][:4]) if summary['peripherals'] else 'None detected'}."
        )
        return json.dumps({"status": "success", "summary": summary_text, "data": summary}, indent=2)

    if action in ("devices", "list", "peripherals"):
        devices = get_connected_usb_devices(include_internal_hubs=include_hubs)
        summary_text = f"Found {len(devices)} connected USB devices."
        return json.dumps({"status": "success", "summary": summary_text, "devices": devices}, indent=2)

    if action in ("drives", "storage", "removable", "flash"):
        drives = get_removable_drives()
        summary_text = f"Found {len(drives)} mounted removable storage drives."
        return json.dumps({"status": "success", "summary": summary_text, "drives": drives}, indent=2)

    return json.dumps({
        "status": "error",
        "message": f"Unknown action '{action}'. Choose from: summary, devices, drives."
    }, indent=2)


TOOL = {
    "name": "usb_sentinel",
    "description": "Inspect connected USB devices, external storage media (flash drives / SSDs), and input peripherals (mice, keyboards, cameras).",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["summary", "devices", "drives"],
                "description": "USB action to execute (default: 'summary').",
            },
            "include_hubs": {
                "type": "BOOLEAN",
                "description": "Whether to include internal USB host controllers and root hubs (default: false).",
            },
        },
    },
    "handler": usb_sentinel,
}
