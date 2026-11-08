"""Self-Reflective Metacognition Action for Zaya.
Created and developed by Sajan Rai.

Inspects tool reliability metrics, latency averages, failure patterns, and manages
circuit-breaker degradation to maintain autonomous execution stability.
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Any

from core.execution_policy import require_owner
from core.metacognition import get_metacognitive_engine
from core.tool_result import ToolResult


def metacognition(parameters: dict[str, Any], **_kwargs) -> ToolResult:
    """Inspect or manage self-reflective tool reliability metrics."""
    require_owner()
    action = str(parameters.get("action", "diagnose")).lower().strip()
    engine = get_metacognitive_engine()

    if action == "diagnose":
        report = engine.generate_diagnostic_report()
        evidence = [
            {"source": "metacognition", "healthy": report["healthy_count"], "tripped": report["tripped_count"]}
        ]
        return ToolResult("success", report["summary"], report, evidence=evidence)

    elif action == "health":
        tool_name = str(parameters.get("tool", "")).strip()
        if tool_name:
            h = engine.check_tool_health(tool_name)
            summary = f"Tool '{tool_name}' status: {h['status'].upper()} (can_execute: {h['can_execute']}, avg_latency: {h['avg_latency_ms']}ms)."
            return ToolResult("success", summary, h)
        else:
            report = engine.generate_diagnostic_report()
            return ToolResult("success", report["summary"], {"tools": report["tools"]})

    elif action == "record":
        tool_name = str(parameters.get("tool", "")).strip()
        if not tool_name:
            return ToolResult("failed", "Parameter 'tool' is required to record execution metrics.", {})

        duration_ms = float(parameters.get("duration_ms", 0.0))
        success = bool(parameters.get("success", True))
        err_msg = str(parameters.get("error", ""))

        m = engine.record_execution(tool_name, duration_ms, success, err_msg)
        return ToolResult(
            "success",
            f"Recorded telemetry for '{tool_name}': status={m.status}, success_rate={m.success_rate * 100:.1f}%.",
            asdict(m),
        )

    elif action == "reset":
        tool_name = str(parameters.get("tool", "")).strip()
        if not tool_name:
            return ToolResult("failed", "Parameter 'tool' is required to reset circuit breaker.", {})

        ok = engine.reset_tool(tool_name)
        if ok:
            return ToolResult("success", f"Circuit breaker for tool '{tool_name}' has been reset to HEALTHY.", {"tool": tool_name})
        return ToolResult("failed", f"Tool '{tool_name}' was not found in metrics registry.", {"tool": tool_name})

    return ToolResult("failed", f"Unknown action '{action}'. Valid actions are 'diagnose', 'health', 'record', 'reset'.", {})


TOOL = {
    "name": "metacognition",
    "description": (
        "Inspect self-reflective tool reliability metrics, latency averages, failure patterns, "
        "and circuit-breaker health status across Zaya's autonomous action suite."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["diagnose", "health", "record", "reset"],
                "description": "Action to perform: 'diagnose' (default), 'health', 'record', 'reset'.",
            },
            "tool": {
                "type": "STRING",
                "description": "Target tool name to inspect, record telemetry for, or reset.",
            },
            "duration_ms": {
                "type": "NUMBER",
                "description": "Execution duration in milliseconds (for 'record').",
            },
            "success": {
                "type": "BOOLEAN",
                "description": "Whether tool invocation succeeded (for 'record').",
            },
            "error": {
                "type": "STRING",
                "description": "Error message if invocation failed (for 'record').",
            },
        },
        "required": [],
    },
    "handler": metacognition,
}
