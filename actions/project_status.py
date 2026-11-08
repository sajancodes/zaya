"""Authoritative Project Awareness & Observation Provenance Action.
Created and developed by Sajan Rai for Zaya.

Reads reconciled project state across active workspace windows, registered projects,
in-flight tasks, background sentinel alerts, and persistent project state.
"""
from __future__ import annotations

from typing import Any

from core.project_awareness import get_project_awareness
from core.tool_result import ToolResult


def project_status(parameters: dict[str, Any], **_kwargs) -> ToolResult:
    """Read authoritative active project, workspace, and observation provenance."""
    awareness = get_project_awareness()
    snapshot = awareness.snapshot()

    active = snapshot.get("active_project", "")
    last_known = snapshot.get("last_known_project", "")
    sources = snapshot.get("sources", [])
    active_task = snapshot.get("active_task")

    summary_parts = []
    if active:
        summary_parts.append(f"Active project: '{active}'.")
    elif last_known:
        summary_parts.append(f"Last known project: '{last_known}' (no active window/task).")
    else:
        summary_parts.append("No active or registered project identified.")

    if active_task:
        summary_parts.append(f"Active task: {active_task.get('goal', '')} [{active_task.get('state', '')}].")
    else:
        summary_parts.append("No active runtime task.")

    summary = " ".join(summary_parts)

    evidence = [
        {
            "source": s.get("source", "project_awareness"),
            "kind": s.get("kind", "project"),
            "timestamp": s.get("timestamp"),
            "confidence": s.get("confidence"),
        }
        for s in sources
    ]

    return ToolResult(
        status="success",
        summary=summary,
        data=snapshot,
        evidence=evidence,
    )


TOOL = {
    "name": "project_status",
    "description": (
        "Read authoritative active project, workspace context, and observation provenance. "
        "Use when asked about the current project, task, what you are working on, or how you knew about a file."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "detail": {
                "type": "STRING",
                "enum": ["summary", "full"],
                "description": "Level of detail requested (default: 'summary').",
            }
        },
    },
    "handler": project_status,
}
