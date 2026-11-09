"""Monitor Mode Action — start/stop/status for periodic screen surveillance.
Created and developed by Sajan Rai for Zaya.
"""
from __future__ import annotations

from core.monitor_mode import get_monitor_engine
from core.tool_result import ToolResult


def monitor_mode(parameters: dict, **_kwargs) -> ToolResult:
    """Handle monitor_mode tool calls."""
    action = (parameters.get("action") or "status").lower().strip()
    engine = get_monitor_engine()

    if action == "start":
        task = parameters.get("task", "").strip()
        if not task:
            return ToolResult("failed", "Describe what you want me to monitor.")
        interval = int(parameters.get("interval_minutes", 5)) * 60
        max_dur = int(parameters.get("max_duration_hours", 4)) * 3600
        try:
            session = engine.start(task, interval_sec=interval, max_duration_sec=max_dur)
            return ToolResult(
                "success",
                f"Monitor started: '{session.task}' — capturing every "
                f"{session.interval_sec // 60} min for up to "
                f"{session.max_duration_sec // 3600} hours.",
                data=session.summary(),
                side_effect=True,
            )
        except (RuntimeError, ValueError) as e:
            return ToolResult("failed", str(e))

    elif action == "stop":
        try:
            session = engine.stop()
            if session:
                return ToolResult(
                    "success",
                    f"Monitor stopped: '{session.task}' — "
                    f"{len(session.observations)} observations captured.",
                    data=session.summary(),
                    side_effect=True,
                )
            return ToolResult("success", "No active monitoring session.")
        except Exception as e:
            return ToolResult("failed", str(e))

    elif action == "status":
        status = engine.status()
        if status.get("active"):
            return ToolResult(
                "success",
                f"Monitoring '{status.get('task', '')}': "
                f"{status.get('observation_count', 0)} observations, "
                f"{status.get('elapsed_sec', 0) // 60} min elapsed.",
                data=status,
            )
        return ToolResult("success", status.get("message", "No active session."), data=status)

    elif action == "adjust":
        interval = int(parameters.get("interval_minutes", 5)) * 60
        try:
            result = engine.adjust_interval(interval)
            return ToolResult(
                "success",
                f"Interval adjusted to {result['interval_sec'] // 60} min.",
                data=result,
                side_effect=True,
            )
        except RuntimeError as e:
            return ToolResult("failed", str(e))

    elif action == "observations":
        limit = int(parameters.get("limit", 10))
        obs = engine.recent_observations(limit)
        return ToolResult(
            "success",
            f"{len(obs)} recent observations." if obs else "No observations yet.",
            data={"observations": obs},
        )

    elif action == "history":
        hist = engine.history()
        return ToolResult(
            "success",
            f"{len(hist)} past sessions." if hist else "No monitoring history.",
            data={"sessions": hist},
        )

    else:
        return ToolResult("failed", f"Unknown action '{action}'. Use: start, stop, status, adjust, observations, history.")


TOOL = {
    "name": "monitor_mode",
    "description": "Screen surveillance monitor: periodically captures the screen, analyses it, and alerts when something needs attention. Actions: start, stop, status, adjust, observations, history.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["start", "stop", "status", "adjust", "observations", "history"],
                "description": "start | stop | status | adjust | observations | history",
            },
            "task": {
                "type": "STRING",
                "description": "What to monitor (for 'start'): e.g. 'build progress', 'download completion'.",
            },
            "interval_minutes": {
                "type": "INTEGER",
                "description": "Minutes between captures (default 5, min 1, max 60).",
            },
            "max_duration_hours": {
                "type": "INTEGER",
                "description": "Max monitoring hours (default 4).",
            },
            "limit": {
                "type": "INTEGER",
                "description": "Number of recent observations to return (for 'observations').",
            },
        },
        "required": ["action"],
    },
    "handler": monitor_mode,
}
