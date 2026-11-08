"""Global Windows Desktop Media Controls.
Created and developed by Sajan Rai for Zaya.
Universal Media Tool executing Win32 keybd_event system-wide for:
Play/Pause, Next Track, Previous Track, Stop, Mute, and Volume adjustments
across YouTube, Spotify, VLC, Apple Music, and Windows Media Player without needing window focus.
"""
from __future__ import annotations

import ctypes
import json
import sys
import time
from typing import Dict

from core.execution_policy import require_owner

KEYEVENTF_KEYUP = 0x0002

VK_MEDIA: Dict[str, int] = {
    "play_pause":  0xB3,
    "toggle":      0xB3,
    "play":        0xB3,
    "pause":       0xB3,
    "next":        0xB0,
    "next_track":  0xB0,
    "prev":        0xB1,
    "previous":    0xB1,
    "prev_track":  0xB1,
    "stop":        0xB2,
    "mute":        0xAD,
    "volume_down": 0xAE,
    "volume_up":   0xAF,
}


def dispatch_media_key(action: str) -> bool:
    """Dispatches Win32 keybd_event virtual media key."""
    action_key = action.lower().strip()
    vk = VK_MEDIA.get(action_key)
    if not vk:
        return False

    if sys.platform == "win32":
        try:
            user32 = ctypes.windll.user32
            # Key down
            user32.keybd_event(vk, 0, 0, 0)
            time.sleep(0.02)
            # Key up
            user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
            return True
        except Exception:
            return False
    return False


_DUCK_PREVIOUS_VOLUME: int | None = None


def fade_volume(target_percent: int, duration_seconds: float = 1.5, steps: int = 15) -> bool:
    """Smoothly fades system master volume to target_percent over duration_seconds."""
    from actions.computer_settings import volume_get, volume_set
    cur = volume_get()
    if cur is None:
        cur = 50
    target = max(0, min(100, int(target_percent)))
    if cur == target:
        return True

    delay = max(0.01, duration_seconds / float(steps))
    diff = target - cur
    for i in range(1, steps + 1):
        step_val = int(round(cur + diff * (i / float(steps))))
        volume_set(step_val)
        time.sleep(delay)
    volume_set(target)
    return True


def duck_volume(target_percent: int = 25) -> bool:
    """Ducks audio down to target_percent, preserving prior volume level."""
    global _DUCK_PREVIOUS_VOLUME
    from actions.computer_settings import volume_get
    cur = volume_get()
    if cur is not None and _DUCK_PREVIOUS_VOLUME is None:
        _DUCK_PREVIOUS_VOLUME = cur
    return fade_volume(target_percent, duration_seconds=0.6, steps=8)


def unduck_volume() -> bool:
    """Restores pre-duck volume level."""
    global _DUCK_PREVIOUS_VOLUME
    target = _DUCK_PREVIOUS_VOLUME if _DUCK_PREVIOUS_VOLUME is not None else 60
    _DUCK_PREVIOUS_VOLUME = None
    return fade_volume(target, duration_seconds=0.8, steps=8)

def control_media_playback(parameters: dict, **_kwargs) -> str:
    """Universal Desktop Media Playback Control Action."""
    require_owner()
    action = str(parameters.get("action", "toggle")).lower().strip()

    # Map common phrases
    if action in ("skip", "next_song"):
        action = "next"
    elif action in ("back", "previous_song"):
        action = "previous"

    if action in ("fade_out", "fade_down"):
        target = int(parameters.get("target", 0))
        dur = float(parameters.get("duration", 1.5))
        fade_volume(target, duration_seconds=dur)
        return json.dumps({
            "status": "success",
            "action": action,
            "message": f"Volume smoothly faded down to {target}%."
        }, indent=2)

    if action in ("fade_in", "fade_up"):
        target = int(parameters.get("target", 50))
        dur = float(parameters.get("duration", 1.5))
        fade_volume(target, duration_seconds=dur)
        return json.dumps({
            "status": "success",
            "action": action,
            "message": f"Volume smoothly faded in to {target}%."
        }, indent=2)

    if action == "duck":
        duck_volume(int(parameters.get("target", 25)))
        return json.dumps({
            "status": "success",
            "action": "duck",
            "message": "Audio ducked for clear hearing."
        }, indent=2)

    if action == "unduck":
        unduck_volume()
        return json.dumps({
            "status": "success",
            "action": "unduck",
            "message": "Audio volume restored."
        }, indent=2)

    if action not in VK_MEDIA:
        # An unknown action was never dispatched. Saying otherwise told the
        # owner the command had been sent when nothing happened at all.
        return json.dumps({
            "status": "error",
            "action": action,
            "message": f"Unknown media action '{action}'. Supported: {', '.join(sorted(set(VK_MEDIA)))}."
        }, indent=2)

    ok = dispatch_media_key(action)
    if ok:
        return json.dumps({
            "status": "success",
            "action": action,
            "message": f"Global media command dispatched: {action}"
        }, indent=2)

    return json.dumps({
        "status": "error",
        "action": action,
        "message": (
            f"Media key '{action}' could not be dispatched. Global media keys are a "
            "Windows feature — on other systems use the app's own volume and "
            "playback controls instead."
        )
    }, indent=2)


TOOL = {
    "name": "control_media_playback",
    "description": "Global Desktop Media Controls: Universal Win32 system-wide media playback control (Play/Pause, Next Track, Previous Track, Stop, Mute, Volume Up/Down) across Spotify, YouTube, VLC, and system media without needing window focus.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["play", "pause", "toggle", "next", "previous", "stop", "mute", "volume_up", "volume_down", "fade_out", "fade_in", "duck", "unduck"],
                "description": "The media control operation to execute."
            }
        },
        "required": ["action"]
    },
    "handler": control_media_playback
}
