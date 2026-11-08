"""Windows Night Light & Blue Light Reduction Sentinel.
Created and developed by Sajan Rai for Zaya.

Inspects Windows Night Light (Blue Light filter) activation status,
scheduled active hours (sunset to sunrise), and toggles eye-strain reduction modes.
"""
from __future__ import annotations

import json
from typing import Any, Dict, Optional
try:
    import winreg
except ImportError:
    winreg = None  # type: ignore

from core.execution_policy import require_owner


_CLOUDSTORE_PARENT = (
    r"Software\Microsoft\Windows\CurrentVersion\CloudStore\Store\DefaultAccount\Current"
)
_STATE_KEY_NAME = "default" + chr(36) + "windows.data.bluelightreduction.bluelightreductionstate"
_SETTINGS_KEY_NAME = "default" + chr(36) + "windows.data.bluelightreduction.settings"


def get_night_light_status() -> Dict[str, Any]:
    """Inspect Windows Night Light enablement, state, and schedule."""
    enabled = False
    status = "active"
    schedule_start: Optional[str] = None
    schedule_end: Optional[str] = None

    if winreg is None:
        return {
            "status": "unavailable",
            "enabled": False,
            "state_label": "OFF (Disabled)",
            "schedule": {
                "has_schedule": False,
                "start_time": "Not set",
                "end_time": "Not set",
            },
        }

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _CLOUDSTORE_PARENT) as parent:
            # 1. Inspect state
            try:
                with winreg.OpenKey(parent, rf"{_STATE_KEY_NAME}\windows.data.bluelightreduction.bluelightreductionstate") as sk:
                    data, _ = winreg.QueryValueEx(sk, "Data")
                    if len(data) > 18:
                        # Byte 18: 0x15 (21) = ON, 0x13 (19) = OFF
                        enabled = (data[18] == 21)
            except FileNotFoundError:
                status = "unavailable"

            # 2. Inspect settings & schedule
            try:
                with winreg.OpenKey(parent, rf"{_SETTINGS_KEY_NAME}\windows.data.bluelightreduction.settings") as sk:
                    data, _ = winreg.QueryValueEx(sk, "Data")
                    seq_start = bytes([202, 20, 14])
                    seq_end = bytes([202, 30, 14])
                    idx1 = data.find(seq_start)
                    idx2 = data.find(seq_end)
                    if idx1 != -1 and idx1 + 5 <= len(data):
                        schedule_start = f"{data[idx1+3]:02d}:{data[idx1+4]:02d}"
                    if idx2 != -1 and idx2 + 5 <= len(data):
                        schedule_end = f"{data[idx2+3]:02d}:{data[idx2+4]:02d}"
            except Exception:
                pass

    except Exception:
        status = "unavailable"

    return {
        "status": status,
        "enabled": enabled,
        "state_label": "ON (Active)" if enabled else "OFF (Disabled)",
        "schedule": {
            "has_schedule": bool(schedule_start and schedule_end),
            "start_time": schedule_start or "Not set",
            "end_time": schedule_end or "Not set",
        },
    }


def set_night_light(enabled: bool) -> Dict[str, Any]:
    """Turn Windows Night Light on or off by updating CloudStore state."""
    if winreg is None:
        return {"status": "error", "message": "Windows Night Light is only available on Windows."}

    target_byte = 21 if enabled else 19

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _CLOUDSTORE_PARENT, 0, winreg.KEY_READ | winreg.KEY_WRITE) as parent:
            subpath = rf"{_STATE_KEY_NAME}\windows.data.bluelightreduction.bluelightreductionstate"
            with winreg.OpenKey(parent, subpath, 0, winreg.KEY_READ | winreg.KEY_WRITE) as sk:
                data, typ = winreg.QueryValueEx(sk, "Data")
                if len(data) <= 18:
                    return {"status": "error", "message": "Corrupted or unexpected Night Light state data size."}

                modified = bytearray(data)
                modified[18] = target_byte
                winreg.SetValueEx(sk, "Data", 0, typ, bytes(modified))

        state_txt = "enabled" if enabled else "disabled"
        return {
            "status": "success",
            "enabled": enabled,
            "message": f"Windows Night Light has been {state_txt}.",
        }
    except Exception as e:
        return {"status": "error", "message": f"Failed to set Night Light state: {e}"}


def toggle_night_light() -> Dict[str, Any]:
    """Toggle current Windows Night Light state."""
    cur = get_night_light_status()
    if cur["status"] == "unavailable":
        return {"status": "error", "message": "Night Light is not available or supported on this system."}
    return set_night_light(not cur["enabled"])


def night_light_sentinel(parameters: Optional[Dict[str, Any]] = None, **_kwargs) -> str:
    """Action entry point for inspecting and toggling Windows Night Light."""
    require_owner()
    params = parameters or {}
    action = str(params.get("action") or "status").lower().strip()

    if action in ("status", "summary"):
        info = get_night_light_status()
        sched = info["schedule"]
        sched_txt = f" (Scheduled: {sched['start_time']} - {sched['end_time']})" if sched["has_schedule"] else ""
        summary = f"Night Light: {info['state_label']}{sched_txt}."
        return json.dumps({
            "status": "success",
            "summary": summary,
            "data": info,
        }, indent=2)

    if action in ("enable", "on", "activate"):
        res = set_night_light(True)
        return json.dumps(res, indent=2)

    if action in ("disable", "off", "deactivate"):
        res = set_night_light(False)
        return json.dumps(res, indent=2)

    if action in ("toggle", "switch"):
        res = toggle_night_light()
        return json.dumps(res, indent=2)

    return json.dumps({
        "status": "error",
        "message": f"Unknown action '{action}'. Choose from: status, enable, disable, toggle.",
    }, indent=2)


TOOL = {
    "name": "night_light_sentinel",
    "description": "Inspect and toggle Windows Night Light (Blue Light filter): check whether eye-strain reduction is active, view sunset/sunrise schedule, and enable/disable/toggle warm display color mode.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["status", "enable", "disable", "toggle"],
                "description": "Night Light action to perform (default: 'status').",
            },
        },
    },
    "handler": night_light_sentinel,
}
