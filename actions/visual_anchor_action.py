"""Visual UI Anchor Action — Actionable Screen Click Anchors.
Created and developed by Sajan Rai for Zaya.
"""
from __future__ import annotations

import json
from typing import Any, Dict

from core.visual_ui_graph import get_visual_ui_graph
from core.action_loader import ActionRecord


def handle_visual_anchors(action: str = "list", target: str = "", elements_json: str = "") -> str:
    """Manage and interact with visual screen UI anchors."""
    graph = get_visual_ui_graph()

    if action == "build":
        try:
            elements = json.loads(elements_json) if elements_json else []
            if not isinstance(elements, list):
                return "Error: elements_json must be a JSON array of objects."
            anchors = graph.build_from_elements(elements)
            return json.dumps({
                "status": "success",
                "count": len(anchors),
                "anchors": [a.to_dict() for a in anchors[:30]],
            })
        except Exception as e:
            return f"Error building UI graph: {e}"

    elif action == "list":
        anchors = graph.get_anchors_summary()
        return json.dumps({
            "status": "success",
            "count": len(anchors),
            "anchors": anchors,
        })

    elif action == "resolve":
        if not target:
            return "Error: target (anchor ID or label) is required for resolve."
        ok, coords, msg = graph.resolve_click_target(target)
        if not ok:
            return json.dumps({"status": "failed", "error": msg})
        return json.dumps({
            "status": "success",
            "target": target,
            "center": list(coords) if coords else [],
            "message": msg,
        })

    elif action == "click":
        if not target:
            return "Error: target (anchor ID or label) is required for click."
        ok, coords, msg = graph.resolve_click_target(target)
        if not ok:
            return json.dumps({"status": "failed", "error": msg})

        # Safe click dispatch via platform adapter or pyautogui if available
        try:
            import pyautogui
            pyautogui.click(coords[0], coords[1])
            return json.dumps({"status": "success", "clicked": coords, "message": msg})
        except Exception as e:
            return json.dumps({"status": "partial", "coordinates": coords, "note": f"Resolved target, click execution: {e}"})

    return f"Unknown visual anchor action: '{action}'."


TOOL = {
    "name": "visual_anchors",
    "description": (
        "Interact with screen UI elements via numbered, spatial visual anchors. "
        "Allows finding and clicking buttons, textboxes, and links without coordinate guessing."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["build", "list", "resolve", "click"],
                "description": "Action to perform on the visual UI graph.",
            },
            "target": {
                "type": "STRING",
                "description": "Anchor numeric ID (e.g. '1', '2') or label name (e.g. 'Submit', 'Search').",
            },
            "elements_json": {
                "type": "STRING",
                "description": "Optional raw JSON list of detected UI elements when building graph.",
            },
        },
        "required": ["action"],
    },
    "handler": handle_visual_anchors,
}
