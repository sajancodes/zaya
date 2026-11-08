"""Ghost Operator Action for Zaya.
Created and developed by Sajan Rai for Zaya.

Exposes autonomous UI automation, mouse control, window management,
and multi-step desktop workflows.
"""
from __future__ import annotations

from core.execution_policy import require_owner
from core.ghost_operator import get_ghost_operator
from core.tool_result import ToolResult


def ghost_operator(parameters: dict, **_kwargs) -> ToolResult:
    """Executes mouse, window, or multi-step UI automation workflows."""
    require_owner()
    action = str(parameters.get("action") or "inspect").lower().strip()
    engine = get_ghost_operator()

    if action == "metrics":
        metrics = engine.get_display_metrics()
        return ToolResult(
            "success",
            f"Display metrics: {metrics['width']}x{metrics['height']} (DPI {metrics['dpi']}, Scale {int(metrics['scale_factor']*100)}%)",
            data=metrics,
        )

    if action == "inspect":
        win = engine.get_active_window()
        pos = engine.get_cursor_pos()
        metrics = engine.get_display_metrics()
        return ToolResult(
            "success",
            f"Active window: '{win.get('title')}' at cursor pos {pos} (Scale {int(metrics['scale_factor']*100)}%)",
            data={"window": win, "cursor": pos, "metrics": metrics},
        )

    # Coordinate normalization resolution if 0-1000 scale is given
    norm_x = parameters.get("normalized_x", parameters.get("norm_x"))
    norm_y = parameters.get("normalized_y", parameters.get("norm_y"))

    if action == "move":
        if norm_x is not None and norm_y is not None:
            x, y = engine.map_vision_coordinate(norm_x, norm_y)
        else:
            x = int(parameters.get("x", 0))
            y = int(parameters.get("y", 0))
        smooth = bool(parameters.get("smooth", True))
        bezier = bool(parameters.get("bezier", True))
        ok = engine.move_cursor(x, y, smooth=smooth, bezier=bezier)
        if ok:
            return ToolResult("success", f"Cursor moved to ({x}, {y})", data={"x": x, "y": y}, side_effect=True)
        return ToolResult("failed", f"Failed to move cursor to ({x}, {y})")

    if action in ("click", "double_click", "right_click"):
        if norm_x is not None and norm_y is not None:
            x, y = engine.map_vision_coordinate(norm_x, norm_y)
        else:
            x = parameters.get("x")
            y = parameters.get("y")
        btn = "right" if action == "right_click" else str(parameters.get("button", "left"))
        double = action == "double_click"
        ok = engine.click(button=btn, double=double, x=x, y=y)
        desc = f"{'Double-clicked' if double else 'Clicked'} {btn} button" + (f" at ({x}, {y})" if x is not None else "")
        if ok:
            return ToolResult("success", desc, data={"button": btn, "x": x, "y": y}, side_effect=True)
        return ToolResult("failed", f"Failed to perform {action}")

    if action == "drag":
        from_x = int(parameters.get("from_x", 0))
        from_y = int(parameters.get("from_y", 0))
        to_x = int(parameters.get("to_x", 0))
        to_y = int(parameters.get("to_y", 0))
        ok = engine.drag(from_x, from_y, to_x, to_y)
        if ok:
            return ToolResult("success", f"Dragged from ({from_x}, {from_y}) to ({to_x}, {to_y})", side_effect=True)
        return ToolResult("failed", "Drag operation failed.")

    if action == "scroll":
        clicks = int(parameters.get("clicks", -3))
        x = parameters.get("x")
        y = parameters.get("y")
        ok = engine.scroll(clicks, x=x, y=y)
        if ok:
            return ToolResult("success", f"Scrolled {clicks} clicks", data={"clicks": clicks}, side_effect=True)
        return ToolResult("failed", "Scroll operation failed.")

    if action == "focus_window":
        title = str(parameters.get("title") or "").strip()
        if not title:
            return ToolResult("failed", "Parameter 'title' is required to focus a window.")
        ok = engine.focus_window_by_title(title)
        if ok:
            return ToolResult("success", f"Window matching '{title}' brought to focus.", side_effect=True)
        return ToolResult("failed", f"Could not find or focus window matching '{title}'.")

    if action == "workflow":
        steps = parameters.get("steps")
        if not isinstance(steps, list) or not steps:
            return ToolResult("failed", "Parameter 'steps' must be a non-empty list of action dicts.")
        res = engine.execute_workflow(steps)
        status = res.get("status", "failed")
        msg = f"Workflow completed {res.get('steps_executed', 0)} steps." if status == "success" else f"Workflow failed: {res.get('error')}"
        return ToolResult(status, msg, data=res, side_effect=True)

    return ToolResult("failed", f"Unknown action '{action}'")


TOOL = {
    "name": "ghost_operator",
    "description": "Ghost Operator: Autonomous OS and UI automation operator. Performs mouse clicks, double clicks, right clicks, drag-and-drop, scrolling, window focus, typing, hotkeys, and multi-step automated UI workflows.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["inspect", "metrics", "move", "click", "double_click", "right_click", "drag", "scroll", "focus_window", "workflow"],
                "description": "The UI automation operation to perform."
            },
            "x": {
                "type": "INTEGER",
                "description": "X coordinate for mouse move/click/scroll."
            },
            "y": {
                "type": "INTEGER",
                "description": "Y coordinate for mouse move/click/scroll."
            },
            "from_x": {
                "type": "INTEGER",
                "description": "Starting X coordinate for drag."
            },
            "from_y": {
                "type": "INTEGER",
                "description": "Starting Y coordinate for drag."
            },
            "to_x": {
                "type": "INTEGER",
                "description": "Ending X coordinate for drag."
            },
            "to_y": {
                "type": "INTEGER",
                "description": "Ending Y coordinate for drag."
            },
            "clicks": {
                "type": "INTEGER",
                "description": "Scroll wheel clicks (positive for up, negative for down, default: -3)."
            },
            "title": {
                "type": "STRING",
                "description": "Substring of the window title to find and activate."
            },
            "steps": {
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT"
                },
                "description": "Sequence of workflow step objects (each with 'action', coordinates, etc.) for automated execution."
            }
        }
    },
    "handler": ghost_operator
}
