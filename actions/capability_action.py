"""Capability Registry Action for Zaya runtime self-knowledge.
Created and developed by Sajan Rai for Zaya.
"""
from __future__ import annotations

from dataclasses import asdict
from core.capability_registry import get_capability_registry
from core.tool_result import ToolResult


def capability_action(parameters: dict, **_kwargs) -> ToolResult:
    """Inspect what Zaya can and cannot execute at runtime."""
    action = (parameters.get("action") or "status").lower().strip()
    registry = get_capability_registry()

    if action == "status":
        snap = registry.snapshot(force_refresh=bool(parameters.get("refresh", False)))
        return ToolResult(
            "success",
            snap.readiness_summary,
            data=asdict(snap),
        )

    elif action == "check":
        capability = str(parameters.get("capability") or "").strip()
        if not capability:
            return ToolResult("failed", "Specify a capability to check (e.g., 'camera', 'screen_capture', 'ollama').")

        can_run, reason = registry.can_execute(capability)
        return ToolResult(
            "success" if can_run else "partial",
            registry.explain_limitation(capability),
            data={"capability": capability, "can_execute": can_run, "reason": reason},
        )

    return ToolResult("failed", f"Unknown action: '{action}'. Use status or check.")


TOOL = {
    "name": "capability_registry",
    "description": "Zaya Runtime Self-Knowledge: Check hardware availability, active AI providers, missing dependencies, and verify whether a capability can execute before running it.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["status", "check"],
                "description": "status | check",
            },
            "capability": {
                "type": "STRING",
                "description": "For 'check': camera | screen_capture | gui_automation | local_llm | browser_automation | tool_name",
            },
            "refresh": {"type": "BOOLEAN", "description": "True to force an immediate hardware/OS re-probe."},
        },
        "required": ["action"],
    },
    "handler": capability_action,
}
