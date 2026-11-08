"""Windows Microphone & Audio Capture Sentinel.
Created and developed by Sajan Rai for Zaya.

Audits active recording endpoints, inspects input capture levels,
and controls hardware microphone mute and volume states via Windows Core Audio.
"""
from __future__ import annotations

import json
import warnings
from typing import Any, Dict, List, Optional

from core.execution_policy import require_owner


def _init_com() -> None:
    """Ensure COM library is initialized for current thread."""
    try:
        import comtypes
        comtypes.CoInitialize()
    except Exception:
        pass


def _get_default_mic_device():
    """Retrieve wrapped AudioDevice for default capture endpoint."""
    _init_com()
    try:
        from pycaw.pycaw import AudioUtilities
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            raw_mic = AudioUtilities.GetMicrophone()
            if raw_mic is None:
                return None
            return AudioUtilities.CreateDevice(raw_mic)
    except Exception:
        return None


def get_microphone_status() -> Dict[str, Any]:
    """Retrieve primary microphone status, volume level, and mute state."""
    mic = _get_default_mic_device()
    if not mic:
        return {
            "device": "None detected",
            "muted": False,
            "volume_percent": 0,
            "device_id": "",
            "status": "unavailable",
        }

    device_name = str(getattr(mic, "FriendlyName", "Default Microphone") or "Default Microphone")
    device_id = str(getattr(mic, "id", "") or "")
    muted = False
    volume_percent = 0

    try:
        vol = mic.EndpointVolume
        if vol:
            muted = bool(vol.GetMute())
            volume_percent = round(vol.GetMasterVolumeLevelScalar() * 100)
    except Exception:
        pass

    return {
        "device": device_name,
        "muted": muted,
        "volume_percent": volume_percent,
        "device_id": device_id,
        "status": "active",
    }


def list_recording_devices() -> List[Dict[str, Any]]:
    """Enumerate all connected or configured capture / microphone devices."""
    _init_com()
    devices = []
    try:
        from pycaw.pycaw import AudioUtilities
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            all_devs = AudioUtilities.GetAllDevices()

        for d in all_devs:
            dev_id = getattr(d, "id", "")
            # Windows Core Audio endpoint ID format: {0.0.1.00000000} indicates capture/recording
            is_capture = "{0.0.1." in dev_id or (
                "{0.0.0." not in dev_id
                and any(kw in getattr(d, "FriendlyName", "").lower() for kw in ("mic", "microphone", "input", "line in"))
            )
            if is_capture:
                state_str = str(getattr(d, "state", "Unknown"))
                if "." in state_str:
                    state_str = state_str.split(".")[-1]
                devices.append({
                    "name": getattr(d, "FriendlyName", "Unknown Device"),
                    "id": dev_id,
                    "state": state_str,
                })
    except Exception:
        pass
    return devices


def set_microphone_mute(muted: bool) -> Dict[str, Any]:
    """Set hardware microphone mute state on the default capture device."""
    mic = _get_default_mic_device()
    if not mic:
        return {"status": "error", "message": "No default microphone device detected."}

    try:
        vol = mic.EndpointVolume
        vol.SetMute(1 if muted else 0, None)
        new_state = bool(vol.GetMute())
        action_word = "muted" if new_state else "unmuted"
        return {
            "status": "success",
            "device": getattr(mic, "FriendlyName", "Default Microphone"),
            "muted": new_state,
            "message": f"Microphone is now {action_word}.",
        }
    except Exception as e:
        return {"status": "error", "message": f"Failed to set microphone mute state: {e}"}


def toggle_microphone_mute() -> Dict[str, Any]:
    """Toggle hardware microphone mute state."""
    status = get_microphone_status()
    if status.get("status") == "unavailable":
        return {"status": "error", "message": "No default microphone device detected."}
    return set_microphone_mute(not status["muted"])


def set_microphone_volume(volume_percent: int) -> Dict[str, Any]:
    """Set master microphone volume level percentage (0 to 100)."""
    mic = _get_default_mic_device()
    if not mic:
        return {"status": "error", "message": "No default microphone device detected."}

    clamped = max(0, min(100, int(volume_percent)))
    scalar = clamped / 100.0

    try:
        vol = mic.EndpointVolume
        vol.SetMasterVolumeLevelScalar(scalar, None)
        actual = round(vol.GetMasterVolumeLevelScalar() * 100)
        return {
            "status": "success",
            "device": getattr(mic, "FriendlyName", "Default Microphone"),
            "volume_percent": actual,
            "message": f"Microphone input volume set to {actual}%.",
        }
    except Exception as e:
        return {"status": "error", "message": f"Failed to set microphone volume: {e}"}


def mic_sentinel(parameters: Optional[Dict[str, Any]] = None, **_kwargs) -> str:
    """Action entry point for inspecting and controlling system microphone."""
    require_owner()
    params = parameters or {}
    action = params.get("action", "status").lower().strip()

    if action in ("status", "summary"):
        status = get_microphone_status()
        mute_txt = "MUTED" if status["muted"] else "UNMUTED"
        summary = (
            f"Microphone: {status['device']} ({mute_txt}, {status['volume_percent']}% input level)."
        )
        return json.dumps({
            "status": "success",
            "summary": summary,
            "data": status,
        }, indent=2)

    if action == "mute":
        res = set_microphone_mute(True)
        return json.dumps(res, indent=2)

    if action == "unmute":
        res = set_microphone_mute(False)
        return json.dumps(res, indent=2)

    if action == "toggle_mute":
        res = toggle_microphone_mute()
        return json.dumps(res, indent=2)

    if action == "set_volume":
        vol = params.get("volume")
        if vol is None:
            return json.dumps({"status": "error", "message": "Must provide 'volume' percentage (0-100)."}, indent=2)
        res = set_microphone_volume(vol)
        return json.dumps(res, indent=2)

    if action == "devices":
        devs = list_recording_devices()
        return json.dumps({
            "status": "success",
            "summary": f"Detected {len(devs)} recording / capture endpoints.",
            "data": {"recording_devices": devs},
        }, indent=2)

    return json.dumps({
        "status": "error",
        "message": f"Unknown action '{action}'. Choose from: status, mute, unmute, toggle_mute, set_volume, devices."
    }, indent=2)


TOOL = {
    "name": "mic_sentinel",
    "description": "Inspect and control system microphone: query mute status and input volume level, mute/unmute or toggle microphone, and list connected recording devices.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["status", "mute", "unmute", "toggle_mute", "set_volume", "devices"],
                "description": "Microphone action to perform (default: 'status').",
            },
            "volume": {
                "type": "INTEGER",
                "description": "Input volume percentage (0 to 100) when action is 'set_volume'.",
            },
        },
    },
    "handler": mic_sentinel,
}
