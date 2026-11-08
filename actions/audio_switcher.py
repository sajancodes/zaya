"""Windows Audio Endpoint & Per-Application Volume Manager.
Created and developed by Sajan Rai for Zaya.

Inspects active hardware audio devices, monitors per-application audio sessions,
and controls individual app volumes (e.g. Spotify, Chrome, Edge, Brave) without
affecting the master system volume.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional
import warnings

from core.execution_policy import require_owner


def _get_default_speakers() -> Dict[str, Any]:
    """Retrieve the primary default playback device name and volume."""
    try:
        from pycaw.pycaw import AudioUtilities
        spk = AudioUtilities.GetSpeakers()
        name = getattr(spk, "FriendlyName", "Default Speakers")
        vol_scalar = 100
        try:
            vol_scalar = round(spk.EndpointVolume.GetMasterVolumeLevelScalar() * 100)
        except Exception:
            pass
        return {"device": name, "volume_percent": vol_scalar}
    except Exception as e:
        return {"device": "Unknown", "volume_percent": 0, "error": str(e)}


def _list_active_devices() -> List[Dict[str, Any]]:
    """List all connected and active playback and capture audio devices."""
    devices = []
    try:
        from pycaw.pycaw import AudioUtilities, AudioDeviceState
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            all_devs = AudioUtilities.GetAllDevices()

        for d in all_devs:
            if hasattr(d, "FriendlyName") and getattr(d, "state", None) == AudioDeviceState.Active:
                name = d.FriendlyName
                is_mic = any(kw in name.lower() for kw in ("mic", "microphone", "input", "line in"))
                devices.append({
                    "name": name,
                    "id": getattr(d, "id", ""),
                    "type": "recording" if is_mic else "playback",
                })
    except Exception:
        pass
    return devices


def _list_app_sessions() -> List[Dict[str, Any]]:
    """List applications currently holding active audio sessions."""
    sessions_list = []
    try:
        from pycaw.pycaw import AudioUtilities
        for s in AudioUtilities.GetAllSessions():
            proc = getattr(s, "Process", None)
            if proc:
                try:
                    name = proc.name()
                    vol = s.SimpleAudioVolume
                    sessions_list.append({
                        "process": name,
                        "pid": proc.pid,
                        "volume_percent": round(vol.GetMasterVolume() * 100),
                        "muted": bool(vol.GetMute()),
                    })
                except Exception:
                    continue
    except Exception:
        pass
    return sessions_list


def _control_app_audio(app_name: str, volume: Optional[int] = None, mute: Optional[bool] = None) -> Dict[str, Any]:
    """Adjust volume or mute state for a specific application."""
    clean_target = app_name.lower().strip()
    if clean_target.endswith(".exe"):
        clean_target = clean_target[:-4]

    matched = []
    try:
        from pycaw.pycaw import AudioUtilities
        for s in AudioUtilities.GetAllSessions():
            proc = getattr(s, "Process", None)
            if proc:
                p_name = proc.name().lower()
                if clean_target in p_name:
                    vol = s.SimpleAudioVolume
                    if mute is not None:
                        vol.SetMute(1 if mute else 0, None)
                    if volume is not None:
                        clamped = max(0.0, min(float(volume) / 100.0, 1.0))
                        vol.SetMasterVolume(clamped, None)
                    matched.append({
                        "process": proc.name(),
                        "pid": proc.pid,
                        "volume_percent": round(vol.GetMasterVolume() * 100),
                        "muted": bool(vol.GetMute()),
                    })
    except Exception as e:
        return {"status": "error", "message": f"Failed to control app audio: {e}"}

    if not matched:
        return {
            "status": "error",
            "message": f"No active audio session found matching application '{app_name}'. Make sure the app is currently running and producing audio."
        }

    return {
        "status": "success",
        "app_name": app_name,
        "matched": matched,
    }


def audio_switcher(parameters: dict, **_kwargs) -> str:
    """Dispatches audio device discovery and per-app volume adjustments."""
    require_owner()
    action = str(parameters.get("action") or "summary").lower().strip()
    app_name = parameters.get("app") or parameters.get("app_name")
    volume = parameters.get("volume")
    if volume is not None:
        volume = int(volume)

    # 1. List Hardware Devices
    if action in ("devices", "list_devices", "hardware"):
        devs = _list_active_devices()
        playback = [d["name"] for d in devs if d["type"] == "playback"]
        recording = [d["name"] for d in devs if d["type"] == "recording"]
        summary = f"Active Audio Endpoints: {len(playback)} playback device(s) ({', '.join(playback)}), {len(recording)} microphone(s)."
        return json.dumps({"status": "success", "summary": summary, "data": devs}, indent=2)

    # 2. List Application Audio Sessions
    if action in ("app_sessions", "sessions", "apps"):
        sessions = _list_app_sessions()
        if sessions:
            summary = f"Active app audio sessions: " + ", ".join(f"{s['process']} ({s['volume_percent']}%, {'muted' if s['muted'] else 'unmuted'})" for s in sessions)
        else:
            summary = "No applications are currently holding active audio output sessions."
        return json.dumps({"status": "success", "summary": summary, "data": sessions}, indent=2)

    # 3. Set Specific App Volume
    if action in ("set_app_volume", "app_volume"):
        if not app_name:
            return json.dumps({"status": "error", "message": "Must provide 'app' name to set volume."}, indent=2)
        if volume is None:
            return json.dumps({"status": "error", "message": "Must provide 'volume' percentage (0-100)."}, indent=2)
        res = _control_app_audio(app_name, volume=volume)
        if res.get("status") == "success":
            res["summary"] = f"Set {app_name} volume to {volume}%."
        return json.dumps(res, indent=2)

    # 4. Mute Specific App
    if action in ("mute_app", "mute"):
        if not app_name:
            return json.dumps({"status": "error", "message": "Must provide 'app' name to mute."}, indent=2)
        res = _control_app_audio(app_name, mute=True)
        if res.get("status") == "success":
            res["summary"] = f"Muted {app_name}."
        return json.dumps(res, indent=2)

    # 5. Unmute Specific App
    if action in ("unmute_app", "unmute"):
        if not app_name:
            return json.dumps({"status": "error", "message": "Must provide 'app' name to unmute."}, indent=2)
        res = _control_app_audio(app_name, mute=False)
        if res.get("status") == "success":
            res["summary"] = f"Unmuted {app_name}."
        return json.dumps(res, indent=2)

    # 6. Audio Ecosystem Summary
    if action == "summary":
        spk = _get_default_speakers()
        devs = _list_active_devices()
        sessions = _list_app_sessions()
        summary = (
            f"Audio Summary: Output through '{spk.get('device')}' at {spk.get('volume_percent')}%. "
            f"{len(devs)} active device(s), {len(sessions)} app session(s) active."
        )
        return json.dumps({
            "status": "success",
            "summary": summary,
            "data": {
                "default_speakers": spk,
                "devices": devs,
                "app_sessions": sessions,
            }
        }, indent=2)

    return json.dumps({
        "status": "error",
        "message": f"Unknown action '{action}'. Choose from: summary, devices, app_sessions, set_app_volume, mute_app, unmute_app."
    }, indent=2)


TOOL = {
    "name": "audio_switcher",
    "description": "Inspect active hardware audio playback and recording endpoints, list applications playing audio, and control individual application volumes or mute states.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["summary", "devices", "app_sessions", "set_app_volume", "mute_app", "unmute_app"],
                "description": "Audio management action (default: 'summary').",
            },
            "app": {
                "type": "STRING",
                "description": "Name of the target application (e.g. 'Spotify', 'Chrome', 'Edge', 'Brave').",
            },
            "volume": {
                "type": "INTEGER",
                "description": "Target volume percentage (0 to 100) for the application.",
            },
        },
    },
    "handler": audio_switcher,
}
