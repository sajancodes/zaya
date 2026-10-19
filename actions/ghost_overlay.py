"""
Ghost Overlay Action (Chapter 06 / PC Specs)
Summons a floating, context-aware command overlay at cursor position for rapid voice/keyboard interactions.
"""
from __future__ import annotations

import json
from core.execution_policy import require_owner
from core.ghost_overlay import toggle_ghost_overlay_window


def ghost_overlay(parameters: dict, **_kwargs) -> str:
    """Summons or dismisses the mini ghost overlay at the cursor position."""
    require_owner()
    action = str(parameters.get("action", "toggle")).lower().strip()
    force_state = True if action in ("open", "show") else (False if action in ("close", "hide") else None)

    state = toggle_ghost_overlay_window(force_state=force_state)
    vis = state.get("visible", False)
    pos = state.get("position", [0, 0])
    msg = f"Ghost Mini Overlay dock is now {'visible at cursor coordinate ' + str(pos) if vis else 'hidden'}."

    return json.dumps({
        "status": "success",
        "visible": vis,
        "position": pos,
        "message": msg
    })


TOOL = {
    "name": "ghost_overlay",
    "description": "Small Ghost Overlay: launches or toggles a sleek, floating quick-access mini overlay at cursor position (Ctrl+Shift+I) for immediate voice or keyboard commands.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["toggle", "open", "close"],
                "description": "Whether to toggle, open, or close the mini floating overlay dock."
            }
        }
    },
    "handler": ghost_overlay
}
