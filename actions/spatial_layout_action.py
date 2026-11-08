"""Spatial Window Layout Action for Zaya.
Created and developed by Sajan Rai.

Organizes desktop windows into presets (developer_split, dual_split, quad_grid, focus_center)
and saves/restores custom multi-window arrangements.
"""
from __future__ import annotations

from typing import Any

from core.execution_policy import require_owner
from core.spatial_layout import get_spatial_layout_engine
from core.tool_result import ToolResult


def spatial_layout(parameters: dict[str, Any], **_kwargs) -> ToolResult:
    """Execute spatial multi-window layout operations."""
    require_owner()
    action = str(parameters.get("action", "apply_preset")).lower().strip()
    engine = get_spatial_layout_engine()

    if action == "apply_preset":
        preset = str(parameters.get("preset", "developer_split")).strip().lower()
        try:
            res = engine.apply_preset(preset)
            evidence = [{"source": "spatial_layout", "preset": preset, "arranged": res["arranged_count"]}]
            return ToolResult("success", res["summary"], res, evidence=evidence, side_effect=True)
        except ValueError as err:
            return ToolResult("failed", str(err), {})

    elif action == "save":
        name = str(parameters.get("name", "")).strip().lower()
        if not name:
            return ToolResult("failed", "Parameter 'name' is required to save a layout.", {})
        res = engine.save_current_layout(name)
        return ToolResult("success", res["summary"], res, side_effect=True)

    elif action == "restore":
        name = str(parameters.get("name", "")).strip().lower()
        if not name:
            return ToolResult("failed", "Parameter 'name' is required to restore a layout.", {})
        try:
            res = engine.restore_layout(name)
            evidence = [{"source": "spatial_layout", "restored": res["restored_count"]}]
            return ToolResult("success", res["summary"], res, evidence=evidence, side_effect=True)
        except KeyError as err:
            return ToolResult("failed", str(err), {})

    elif action == "list":
        layouts = engine.list_layouts()
        summary = (
            f"Available presets: {', '.join(layouts['presets'])}. "
            f"Custom layouts: {', '.join(layouts['custom_layouts']) if layouts['custom_layouts'] else 'None'}."
        )
        return ToolResult("success", summary, layouts)

    return ToolResult("failed", f"Unknown action '{action}'. Valid actions are 'apply_preset', 'save', 'restore', 'list'.", {})


TOOL = {
    "name": "spatial_layout",
    "description": (
        "Arrange visible windows into multi-window spatial layout presets "
        "('developer_split', 'dual_split', 'quad_grid', 'focus_center') or save/restore custom desktop layouts."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["apply_preset", "save", "restore", "list"],
                "description": "Action to perform: 'apply_preset' (default), 'save', 'restore', 'list'.",
            },
            "preset": {
                "type": "STRING",
                "enum": ["developer_split", "dual_split", "quad_grid", "focus_center"],
                "description": "Preset name to apply (for 'apply_preset').",
            },
            "name": {
                "type": "STRING",
                "description": "Name of custom layout to save or restore.",
            },
        },
        "required": [],
    },
    "handler": spatial_layout,
}
