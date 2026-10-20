"""Double-clap activation toggle action.
Created and developed by Sajan Rai for Zaya.
"""
from __future__ import annotations

import json
from core.execution_policy import require_owner
from core.double_clap import is_double_clap_enabled, set_double_clap_enabled


def double_clap_toggle(parameters: dict, **_kwargs) -> str:
    """Toggles or checks double-clap activation."""
    require_owner()
    action = str(parameters.get("action", "toggle")).lower().strip()

    current = is_double_clap_enabled()
    if action in ("on", "enable"):
        new_state = True
    elif action in ("off", "disable"):
        new_state = False
    elif action == "status":
        state_str = "enabled" if current else "disabled"
        return json.dumps({
            "status": "success",
            "double_clap_enabled": current,
            "message": f"Double-clap detection is currently {state_str}."
        })
    else:  # toggle
        new_state = not current

    set_double_clap_enabled(new_state)
    state_str = "enabled" if new_state else "disabled"
    return json.dumps({
        "status": "success",
        "double_clap_enabled": new_state,
        "message": f"Double-clap activation is now {state_str}."
    })


TOOL = {
    "name": "double_clap_toggle",
    "description": "Enable, disable, toggle, or check double-clap hands-free wake word activation.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["on", "off", "toggle", "status"],
                "description": "Whether to turn double-clap detection on, off, toggle it, or query status."
            }
        }
    },
    "handler": double_clap_toggle
}
