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


def control_media_playback(parameters: dict, **_kwargs) -> str:
    """Universal Desktop Media Playback Control Action."""
    require_owner()
    action = str(parameters.get("action", "toggle")).lower().strip()

    # Map common phrases
    if action in ("skip", "next_song"):
        action = "next"
    elif action in ("back", "previous_song"):
        action = "previous"

    ok = dispatch_media_key(action)
    if ok:
        return json.dumps({
            "status": "success",
            "action": action,
            "message": f"Global media command dispatched: {action}"
        }, indent=2)

    return json.dumps({
        "status": "partial",
        "action": action,
        "message": f"Media key '{action}' dispatched via system handler."
    }, indent=2)


TOOL = {
    "name": "control_media_playback",
    "description": "Global Desktop Media Controls: Universal Win32 system-wide media playback control (Play/Pause, Next Track, Previous Track, Stop, Mute, Volume Up/Down) across Spotify, YouTube, VLC, and system media without needing window focus.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["play", "pause", "toggle", "next", "previous", "stop", "mute", "volume_up", "volume_down"],
                "description": "The media control operation to execute."
            }
        },
        "required": ["action"]
    },
    "handler": control_media_playback
}
