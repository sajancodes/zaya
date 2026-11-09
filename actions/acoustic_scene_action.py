"""Acoustic Scene Action — Environmental Audio & Sound Event Classifier.
Created and developed by Sajan Rai for Zaya.
"""
from __future__ import annotations

import json
from typing import Any, Dict

from core.acoustic_scene import get_acoustic_classifier


def handle_acoustic_scene(
    action: str = "status",
    category: str = "",
    enabled: bool = True,
) -> str:
    """Inspect or configure environmental sound event detection."""
    classifier = get_acoustic_classifier()

    if action == "status":
        events = classifier.get_recent_events()
        return json.dumps({
            "status": "success",
            "enabled_categories": list(classifier.enabled_categories),
            "recent_events_count": len(events),
            "recent_events": events,
        })

    elif action == "toggle":
        if not category:
            return "Error: category is required to toggle."
        is_on = classifier.set_category_enabled(category, enabled)
        return json.dumps({
            "status": "success",
            "category": category,
            "enabled": is_on,
        })

    elif action == "recent":
        events = classifier.get_recent_events(limit=10)
        return json.dumps({"status": "success", "events": events})

    return f"Unknown acoustic scene action: '{action}'."


TOOL = {
    "name": "acoustic_scene",
    "description": (
        "Monitor and query environmental sound events (door knocks, alarm chirps, doorbells, glass break). "
        "Allows inspecting recent audio scene detections or configuring surveillance categories."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["status", "recent", "toggle"],
                "description": "Acoustic scene action.",
            },
            "category": {
                "type": "STRING",
                "description": "Sound category name (e.g. 'door_knock', 'alarm_chirp', 'doorbell', 'glass_break').",
            },
            "enabled": {
                "type": "BOOLEAN",
                "description": "Whether the category should be enabled or disabled.",
            },
        },
        "required": ["action"],
    },
    "handler": handle_acoustic_scene,
}
