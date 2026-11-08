"""System Audio Volume Limiter & Ear-Safety Sentinel.
Created and developed by Sajan Rai for Zaya.

Prevents sudden ear-splitting audio blasts by enforcing maximum volume safety
ceilings, auto-clamping loud volume spikes, and providing one-command Whisper/Night
modes that balance media levels and suppress jarring desktop interruptions.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from core.execution_policy import require_owner

_CONFIG_PATH = Path("memory") / "ear_safety.json"
_DEFAULT_CEILING = 75  # 75% max safety ceiling by default


def _load_safety_config() -> Dict[str, Any]:
    if not _CONFIG_PATH.exists():
        return {
            "enabled": True,
            "max_volume_percent": _DEFAULT_CEILING,
            "whisper_mode": False,
        }
    try:
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return {
                    "enabled": bool(data.get("enabled", True)),
                    "max_volume_percent": int(data.get("max_volume_percent", _DEFAULT_CEILING)),
                    "whisper_mode": bool(data.get("whisper_mode", False)),
                }
    except Exception:
        pass
    return {"enabled": True, "max_volume_percent": _DEFAULT_CEILING, "whisper_mode": False}


def _save_safety_config(config: Dict[str, Any]) -> None:
    _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)


def _get_master_volume() -> Optional[int]:
    """Retrieve current Windows master volume percentage via pycaw."""
    if os.name != "nt":
        return 50
    try:
        from pycaw.pycaw import AudioUtilities
        dev = AudioUtilities.GetSpeakers()
        if dev and hasattr(dev, "EndpointVolume"):
            scalar = dev.EndpointVolume.GetMasterVolumeLevelScalar()
            return round(scalar * 100.0)
    except Exception:
        pass
    return None


def _set_master_volume(percent: int) -> bool:
    """Set Windows master volume percentage via pycaw."""
    if os.name != "nt":
        return False
    try:
        from pycaw.pycaw import AudioUtilities
        dev = AudioUtilities.GetSpeakers()
        if dev and hasattr(dev, "EndpointVolume"):
            scalar = max(0.0, min(1.0, percent / 100.0))
            dev.EndpointVolume.SetMasterVolumeLevelScalar(scalar, None)
            return True
    except Exception:
        pass
    return False


def ear_safety(parameters: dict, **_kwargs) -> str:
    """Dispatches Ear Safety, Volume Ceiling and Whisper Mode actions."""
    require_owner()
    action = str(parameters.get("action") or "status").lower().strip()
    cfg = _load_safety_config()
    current_vol = _get_master_volume()

    # 1. Status Query
    if action in ("status", "check", "summary"):
        cur_str = f"{current_vol}%" if current_vol is not None else "Unknown"
        mode_str = "Whisper Mode (15% limit)" if cfg.get("whisper_mode") else f"Ceiling at {cfg['max_volume_percent']}%"
        guard_str = "ACTIVE" if cfg.get("enabled") else "DISABLED"

        summary = (
            f"Ear Safety Guard: {guard_str} ({mode_str}). "
            f"Current Master Volume: {cur_str}."
        )
        return json.dumps({
            "status": "success",
            "summary": summary,
            "current_volume_percent": current_vol,
            "config": cfg,
        }, indent=2)

    # 2. Set Safety Ceiling
    if action in ("set_ceiling", "limit", "max"):
        new_max = int(parameters.get("percent") or parameters.get("ceiling") or parameters.get("max") or _DEFAULT_CEILING)
        new_max = max(10, min(100, new_max))
        cfg["max_volume_percent"] = new_max
        cfg["enabled"] = True
        cfg["whisper_mode"] = False
        _save_safety_config(cfg)

        clamped = False
        if current_vol is not None and current_vol > new_max:
            _set_master_volume(new_max)
            clamped = True

        clamp_str = f" Volume automatically clamped down from {current_vol}% to {new_max}%." if clamped else ""
        summary = f"Ear safety ceiling set to {new_max}%.{clamp_str}"
        return json.dumps({
            "status": "success",
            "summary": summary,
            "max_volume_percent": new_max,
            "clamped": clamped,
        }, indent=2)

    # 3. Whisper / Night Mode
    if action in ("whisper", "whisper_mode", "night", "night_mode"):
        cfg["whisper_mode"] = True
        cfg["max_volume_percent"] = 25
        cfg["enabled"] = True
        _save_safety_config(cfg)

        _set_master_volume(15)
        # Also engage DND if focus_mode module is available
        try:
            from actions.focus_mode import _set_windows_quiet_hours_state
            _set_windows_quiet_hours_state(2)  # Alarms Only
        except Exception:
            pass

        summary = "Whisper Mode activated: Master volume set to 15%, safety ceiling locked at 25%, and Do Not Disturb engaged for quiet listening, sir."
        return json.dumps({"status": "success", "summary": summary, "volume_percent": 15, "ceiling": 25}, indent=2)

    # 4. Normal / Daytime Audio Mode
    if action in ("normal", "normal_mode", "daytime"):
        cfg["whisper_mode"] = False
        cfg["max_volume_percent"] = _DEFAULT_CEILING
        cfg["enabled"] = True
        _save_safety_config(cfg)

        _set_master_volume(50)
        try:
            from actions.focus_mode import _set_windows_quiet_hours_state
            _set_windows_quiet_hours_state(0)  # Normal
        except Exception:
            pass

        summary = f"Normal audio mode restored: Master volume set to 50% with a {cfg['max_volume_percent']}% ear safety ceiling, sir."
        return json.dumps({"status": "success", "summary": summary, "volume_percent": 50, "ceiling": _DEFAULT_CEILING}, indent=2)

    # 5. Enable / Disable Guard
    if action in ("enable", "on"):
        cfg["enabled"] = True
        _save_safety_config(cfg)
        return json.dumps({"status": "success", "summary": "Ear safety guard enabled.", "enabled": True}, indent=2)

    if action in ("disable", "off"):
        cfg["enabled"] = False
        _save_safety_config(cfg)
        return json.dumps({"status": "success", "summary": "Ear safety guard disabled.", "enabled": False}, indent=2)

    return json.dumps({
        "status": "error",
        "message": f"Unknown action '{action}'. Choose from: status, set_ceiling, whisper, normal, enable, disable."
    }, indent=2)


TOOL = {
    "name": "ear_safety",
    "description": "Enforce maximum volume safety ceilings, prevent ear-splitting audio blasts, auto-clamp loud volume spikes, and activate Whisper / Night audio modes.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["status", "set_ceiling", "whisper", "normal", "enable", "disable"],
                "description": "Ear safety operation to execute (default: 'status').",
            },
            "percent": {
                "type": "INTEGER",
                "description": "Maximum allowed master volume ceiling percentage when action='set_ceiling' (10-100).",
            },
        },
    },
    "handler": ear_safety,
}
