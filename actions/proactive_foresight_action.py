"""Proactive Foresight Action for Zaya.
Created and developed by Sajan Rai.

Generates proactive contextual briefings, battery runway projections, and cognitive
workplace suggestions based on active project awareness and system telemetry.
"""
from __future__ import annotations

from typing import Any

from core.execution_policy import require_owner
from core.proactive_foresight import get_foresight_engine
from core.tool_result import ToolResult


def proactive_foresight(parameters: dict[str, Any], **_kwargs) -> ToolResult:
    """Execute proactive situational forecasting and executive briefing."""
    require_owner()
    action = str(parameters.get("action", "briefing")).lower().strip()
    engine = get_foresight_engine()

    if action == "briefing":
        briefing = engine.generate_executive_briefing()
        evidence = [
            {"source": "proactive_foresight", "category": f.get("category"), "priority": f.get("priority")}
            for f in briefing.get("foresight_items", [])
        ]
        return ToolResult(
            "success",
            briefing["summary"],
            briefing,
            evidence=evidence,
        )

    elif action == "anticipate":
        items = []
        # Check battery if provided
        bat_pct = parameters.get("battery_pct")
        charging = parameters.get("is_charging", False)
        if bat_pct is not None:
            bat_item = engine.predict_battery_runway(float(bat_pct), is_charging=bool(charging))
            if bat_item:
                items.append(bat_item)

        # Check session duration if provided
        focus_mins = parameters.get("focus_minutes")
        if focus_mins is not None:
            flow_item = engine.check_flow_duration(float(focus_mins))
            if flow_item:
                items.append(flow_item)

        summary = f"Generated {len(items)} anticipatory foresight item(s)." if items else "No immediate risks or routine suggestions detected."
        return ToolResult(
            "success",
            summary,
            {"items": [item.__dict__ for item in items]},
        )

    return ToolResult("failed", f"Unknown action '{action}'. Valid actions are 'briefing', 'anticipate'.", {})


TOOL = {
    "name": "proactive_foresight",
    "description": (
        "Generate Jarvis-grade executive briefings and proactive developer foresight. "
        "Anticipates battery depletion, uncommitted code drift, and deep focus rhythms."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["briefing", "anticipate"],
                "description": "Action to perform: 'briefing' (default) or 'anticipate'.",
            },
            "battery_pct": {
                "type": "NUMBER",
                "description": "Optional current battery percentage to forecast runway.",
            },
            "is_charging": {
                "type": "BOOLEAN",
                "description": "Whether battery is currently charging.",
            },
            "focus_minutes": {
                "type": "NUMBER",
                "description": "Minutes of continuous focus to evaluate rhythm breaks.",
            },
        },
        "required": [],
    },
    "handler": proactive_foresight,
}
