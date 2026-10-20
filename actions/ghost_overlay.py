"""Ghost Overlay Action for quick-access interactions at cursor position.
Created and developed by Sajan Rai for Zaya.
"""
from __future__ import annotations

from core.execution_policy import require_owner
from core.ghost_overlay import toggle_ghost_overlay_window
from core.tool_result import ToolResult


def ghost_overlay(parameters: dict, **_kwargs) -> ToolResult:
    """Summons or dismisses the mini ghost overlay at the cursor position."""
    require_owner()
    action = str(parameters.get("action") or "toggle").lower().strip()
    force_state = True if action in ("open", "show") else (False if action in ("close", "hide") else None)

    state = toggle_ghost_overlay_window(force_state=force_state)
    vis = state.get("visible", False)
    pos = state.get("position", [0, 0])
    msg = f"Ghost Mini Overlay dock is now {'visible at cursor coordinate ' + str(pos) if vis else 'hidden'}."

    return ToolResult("success", msg, data=state)


TOOL = {
    "name": "ghost_overlay",
    "description": "Ghost Overlay: launches or toggles a floating quick-access mini overlay at cursor position for immediate interactions.",
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
