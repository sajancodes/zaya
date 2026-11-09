"""Voice Anti-Spoof Action — Replay Attack & Synthetic Voice Defense.
Created and developed by Sajan Rai for Zaya.
"""
from __future__ import annotations

import json
from typing import Any, Dict

from core.voice_antispoof import get_voice_antispoof_engine


def handle_voice_antispoof(
    action: str = "status",
    threshold: float = 0.50,
) -> str:
    """Inspect voice liveness history or configure anti-spoofing threshold."""
    engine = get_voice_antispoof_engine()

    if action == "status":
        history = engine.get_recent_results()
        return json.dumps({
            "status": "success",
            "threshold": engine.liveness_threshold,
            "recent_checks": len(history),
            "history": history,
        })

    elif action == "set_threshold":
        new_th = engine.set_threshold(threshold)
        return json.dumps({
            "status": "success",
            "message": f"Anti-spoofing liveness threshold updated to {new_th:.2f}.",
            "threshold": new_th,
        })

    return f"Unknown anti-spoof action: '{action}'."


TOOL = {
    "name": "voice_antispoof",
    "description": (
        "Inspect acoustic anti-spoofing status and replay defense metrics. "
        "Guards biometric voice operations against synthetic vocoders or recorded speaker playback."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["status", "set_threshold"],
                "description": "Anti-spoof action.",
            },
            "threshold": {
                "type": "NUMBER",
                "description": "Liveness threshold (0.1 to 0.95). Audio below this threshold is flagged as replay.",
            },
        },
        "required": ["action"],
    },
    "handler": handle_voice_antispoof,
}
