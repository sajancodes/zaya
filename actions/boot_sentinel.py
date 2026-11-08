"""System Uptime, Boot Diagnostics & Power State Sentinel.
Created and developed by Sajan Rai for Zaya.

Tracks system uptime, exact boot timestamps, historical shutdown triggers (Event 1074),
devices armed to wake the machine from sleep, and supported ACPI sleep states.
"""
from __future__ import annotations

import datetime
import json
import logging
import subprocess
import time
from typing import Any, Dict, List, Optional
import xml.etree.ElementTree as ET

import psutil

from core.execution_policy import require_owner

logger = logging.getLogger(__name__)

_NS = {"e": "http://schemas.microsoft.com/win/2004/08/events/event"}


def get_system_uptime() -> Dict[str, Any]:
    """Calculate exact system uptime and boot timestamp."""
    boot_ts = psutil.boot_time()
    now_ts = time.time()
    uptime_sec = max(0, int(now_ts - boot_ts))

    days, rem = divmod(uptime_sec, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, seconds = divmod(rem, 60)

    parts: List[str] = []
    if days > 0:
        parts.append(f"{days} day{'s' if days != 1 else ''}")
    if hours > 0 or days > 0:
        parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")

    formatted = ", ".join(parts) if parts else f"{seconds} seconds"
    boot_dt = datetime.datetime.fromtimestamp(boot_ts).astimezone()

    return {
        "uptime_formatted": formatted,
        "uptime_seconds": uptime_sec,
        "days": days,
        "hours": hours,
        "minutes": minutes,
        "seconds": seconds,
        "boot_timestamp": boot_ts,
        "boot_iso": boot_dt.isoformat(),
    }


def get_last_shutdown_info() -> Optional[Dict[str, Any]]:
    """Retrieve the last recorded shutdown or reboot event (Event ID 1074) from Windows Event Log."""
    cmd = [
        "wevtutil",
        "qe",
        "System",
        "/q:*[System[Provider[@Name='User32'] and (EventID=1074)]]",
        "/c:1",
        "/rd:true",
        "/f:xml",
    ]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if proc.returncode != 0 or not proc.stdout.strip():
            return None

        xml_data = f"<Events>{proc.stdout}</Events>"
        root = ET.fromstring(xml_data)
        ev = root.find("e:Event", _NS)
        if ev is None:
            return None

        sys_elem = ev.find("e:System", _NS)
        time_elem = sys_elem.find("e:TimeCreated", _NS) if sys_elem is not None else None
        timestamp = time_elem.attrib.get("SystemTime", "Unknown") if time_elem is not None else "Unknown"

        data_dict: Dict[str, str] = {}
        event_data = ev.find("e:EventData", _NS)
        if event_data is not None:
            for d in event_data.findall("e:Data", _NS):
                name = d.attrib.get("Name")
                val = (d.text or "").strip()
                if name:
                    data_dict[name] = val

        return {
            "timestamp": timestamp,
            "initiating_process": data_dict.get("param1", "Unknown"),
            "computer": data_dict.get("param2", "Unknown"),
            "reason": data_dict.get("param3", "Unknown"),
            "shutdown_action": data_dict.get("param5", "power off"),
            "initiator_user": data_dict.get("param7", "Unknown"),
        }

    except (subprocess.TimeoutExpired, subprocess.SubprocessError, ET.ParseError, Exception) as exc:
        logger.warning("Failed to query shutdown Event 1074: %s", exc)
        return None


def get_wake_armed_devices() -> List[str]:
    """Query hardware devices authorized to wake the PC from sleep via powercfg."""
    cmd = ["powercfg", "/devicequery", "wake_armed"]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if proc.returncode != 0 or not proc.stdout.strip():
            return []

        devices = [line.strip() for line in proc.stdout.splitlines() if line.strip() and line.strip() != "NONE"]
        return devices

    except (subprocess.TimeoutExpired, subprocess.SubprocessError, Exception) as exc:
        logger.warning("Failed to query wake_armed devices: %s", exc)
        return []


def get_available_sleep_states() -> List[str]:
    """Query available ACPI sleep states on the system via powercfg /a."""
    cmd = ["powercfg", "/a"]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if proc.returncode != 0 or not proc.stdout.strip():
            return []

        available: List[str] = []
        is_avail_section = False
        for line in proc.stdout.splitlines():
            s = line.strip()
            if "The following sleep states are available" in s:
                is_avail_section = True
                continue
            if "The following sleep states are not available" in s:
                is_avail_section = False
                break
            if is_avail_section and s:
                available.append(s)

        return available

    except (subprocess.TimeoutExpired, subprocess.SubprocessError, Exception) as exc:
        logger.warning("Failed to query available sleep states: %s", exc)
        return []


def get_boot_summary() -> Dict[str, Any]:
    """Compile comprehensive boot and uptime status."""
    uptime = get_system_uptime()
    last_shutdown = get_last_shutdown_info()
    wake_devices = get_wake_armed_devices()
    sleep_states = get_available_sleep_states()

    return {
        "status": "success",
        "uptime": uptime,
        "last_shutdown": last_shutdown,
        "wake_armed_devices": wake_devices,
        "available_sleep_states": sleep_states,
    }


def boot_sentinel(parameters: dict, **_kwargs) -> str:
    """Dispatches uptime, boot diagnostics, and wake device inspection."""
    require_owner()
    action = str(parameters.get("action") or "summary").lower().strip()

    if action in ("summary", "status", "health"):
        summary = get_boot_summary()
        uptime_str = summary["uptime"]["uptime_formatted"]
        shut = summary.get("last_shutdown")
        shut_str = f" Last shutdown initiated by {shut['initiator_user']} ({shut['shutdown_action']})." if shut else ""
        wake_str = f" Wake devices: {', '.join(summary['wake_armed_devices'])}." if summary['wake_armed_devices'] else ""
        summary_text = f"System Uptime: {uptime_str}.{shut_str}{wake_str}"
        return json.dumps({"status": "success", "summary": summary_text, "data": summary}, indent=2)

    if action in ("uptime", "boot_time"):
        uptime = get_system_uptime()
        summary_text = f"System has been running for {uptime['uptime_formatted']} (Booted: {uptime['boot_iso']})."
        return json.dumps({"status": "success", "summary": summary_text, "uptime": uptime}, indent=2)

    if action in ("last_shutdown", "reboot_reason", "shutdown_history"):
        shut = get_last_shutdown_info()
        if not shut:
            return json.dumps({"status": "success", "summary": "No shutdown event 1074 found in system event log."}, indent=2)
        summary_text = f"Last shutdown on {shut['timestamp']} by {shut['initiator_user']} ({shut['initiating_process']}): {shut['shutdown_action']} ({shut['reason']})."
        return json.dumps({"status": "success", "summary": summary_text, "shutdown": shut}, indent=2)

    if action in ("wake_devices", "wake_armed"):
        devices = get_wake_armed_devices()
        summary_text = f"Found {len(devices)} device(s) armed to wake the system from sleep."
        return json.dumps({"status": "success", "summary": summary_text, "devices": devices}, indent=2)

    if action in ("sleep_states", "sleep_modes"):
        states = get_available_sleep_states()
        summary_text = f"Supported sleep states: {', '.join(states) if states else 'Standard standby'}."
        return json.dumps({"status": "success", "summary": summary_text, "sleep_states": states}, indent=2)

    return json.dumps({
        "status": "error",
        "message": f"Unknown action '{action}'. Choose from: summary, uptime, last_shutdown, wake_devices, sleep_states."
    }, indent=2)


TOOL = {
    "name": "boot_sentinel",
    "description": "Inspect system uptime, boot timestamp, last shutdown/reboot cause (Event 1074), wake-armed devices, and supported ACPI sleep states.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["summary", "uptime", "last_shutdown", "wake_devices", "sleep_states"],
                "description": "Boot diagnostic action to execute (default: 'summary').",
            },
        },
    },
    "handler": boot_sentinel,
}
