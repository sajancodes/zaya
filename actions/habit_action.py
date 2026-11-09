"""Habit Action for Zaya workflow routine management.
Created and developed by Sajan Rai for Zaya.
"""
from __future__ import annotations

from dataclasses import asdict
from core.execution_policy import require_owner
from core.habit_engine import get_habit_engine
from core.tool_result import ToolResult


def habit_action(parameters: dict, **_kwargs) -> ToolResult:
    """Inspect learned routines, trigger custom workflows, or manage habits."""
    action = (parameters.get("action") or "list").lower().strip()
    engine = get_habit_engine()

    if action == "list":
        routines = engine.list_routines()
        return ToolResult(
            "success",
            f"Habit Engine: {len(routines)} routine(s) synthesized/stored.",
            data={"routines": routines},
        )

    elif action == "create":
        require_owner()
        name = parameters.get("name", "").strip()
        steps = parameters.get("steps", [])
        if not name or not steps:
            return ToolResult("failed", "Provide both 'name' and a list of 'steps' for the routine.")
        trigger = parameters.get("trigger_context", "manual")
        desc = parameters.get("description", "")
        routine = engine.create_custom_routine(name=name, steps=steps, trigger_context=trigger, description=desc)
        return ToolResult(
            "success",
            f"Created custom routine '{routine.name}' with {len(routine.steps)} step(s).",
            data=asdict(routine),
            side_effect=True,
        )

    elif action == "execute":
        require_owner()
        routine_id = parameters.get("routine_id", "").strip()
        routine = engine.get_routine(routine_id)
        if not routine:
            return ToolResult("failed", f"Routine '{routine_id}' not found.")

        # Dispatch steps via action loader
        from core.action_loader import execute_tool
        executed = []
        for s in routine.steps:
            try:
                res = execute_tool(s.tool_name, s.parameters)
                executed.append({"tool": s.tool_name, "status": getattr(res, "status", "success")})
            except Exception as e:
                executed.append({"tool": s.tool_name, "status": "failed", "error": str(e)})

        engine.mark_executed(routine.id)
        return ToolResult(
            "success",
            f"Executed routine '{routine.name}': {len(executed)} step(s) run.",
            data={"routine_id": routine.id, "steps_executed": executed},
            side_effect=True,
        )

    elif action == "delete":
        require_owner()
        routine_id = parameters.get("routine_id", "").strip()
        ok = engine.delete_routine(routine_id)
        return ToolResult(
            "success" if ok else "failed",
            f"Routine '{routine_id}' deleted." if ok else f"Routine '{routine_id}' not found.",
            side_effect=ok,
        )

    return ToolResult("failed", f"Unknown action: '{action}'. Use list, create, execute, delete.")


TOOL = {
    "name": "habit_action",
    "description": "Habit & Routine Engine: Inspect learned behavioral patterns, execute synthesized multi-step workflows, or define custom routines.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["list", "create", "execute", "delete"],
                "description": "list | create | execute | delete",
            },
            "name": {"type": "STRING", "description": "Name for custom routine."},
            "steps": {
                "type": "ARRAY",
                "items": {"type": "OBJECT"},
                "description": "Steps [{'tool_name': '...', 'parameters': {...}}].",
            },
            "routine_id": {"type": "STRING", "description": "Routine ID to execute or delete."},
            "trigger_context": {"type": "STRING", "description": "e.g. 'project:Zaya' or 'manual'."},
        },
        "required": ["action"],
    },
    "handler": habit_action,
}
