"""Autonomous Goal & Multi-Step Task Action for Zaya.
Created and developed by Sajan Rai for Zaya.

Runs autonomous multi-step goals with bounded execution, self-healing parameter retries,
and step status tracking.
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Any

from core.autonomous_agent import get_autonomous_goal_runner
from core.execution_policy import require_owner
from core.task_runtime import TERMINAL, get_runtime
from core.tool_result import ToolResult


def autonomous_task(parameters: dict[str, Any], **_kwargs) -> ToolResult:
    """Execute or manage an autonomous long-horizon multi-step task."""
    require_owner()
    action = str(parameters.get("action", "run")).lower().strip()
    runner = get_autonomous_goal_runner()
    runtime = get_runtime()

    if action == "run":
        goal = str(parameters.get("goal", "")).strip()
        if not goal:
            return ToolResult("failed", "Parameter 'goal' is required to run an autonomous task.", {})

        steps = parameters.get("steps")
        project_context = str(parameters.get("project_context", "")).strip()
        max_steps = int(parameters.get("max_steps", 12))

        return runner.run_goal(
            goal=goal,
            steps=steps,
            project_context=project_context,
            max_steps=max_steps,
        )

    elif action == "cancel":
        task_id = str(parameters.get("task_id", "")).strip()
        if not task_id:
            return ToolResult("failed", "Parameter 'task_id' is required to cancel a task.", {})
        cancelled = runner.cancel(task_id)
        if cancelled:
            return ToolResult("success", f"Autonomous task '{task_id}' cancellation requested.", {"task_id": task_id})
        return ToolResult("failed", f"Task '{task_id}' was not found in active runs.", {"task_id": task_id})

    elif action == "status":
        task_id = str(parameters.get("task_id", "")).strip()
        if task_id:
            try:
                t = runtime.get(task_id)
                return ToolResult("success", f"Task '{task_id}' state: {t.state}", asdict(t))
            except KeyError:
                return ToolResult("failed", f"Task '{task_id}' not found.", {"task_id": task_id})
        else:
            all_tasks = runtime.list(limit=50)
            active = [t for t in all_tasks if t.state not in TERMINAL]
            return ToolResult(
                "success",
                f"{len(active)} active task(s).",
                {"active_tasks": [asdict(t) for t in active]},
            )

    return ToolResult("failed", f"Unknown action '{action}'. Valid actions are 'run', 'status', 'cancel'.", {})


TOOL = {
    "name": "autonomous_task",
    "description": (
        "Execute autonomous multi-step goals with bounded iterations, self-healing parameter retries, "
        "and runtime evidence collection. Allows running, inspecting status, or cancelling goals."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["run", "status", "cancel"],
                "description": "Action to perform: run a goal, inspect status, or cancel an active task.",
            },
            "goal": {
                "type": "STRING",
                "description": "Clear high-level objective to accomplish autonomously (required for 'run').",
            },
            "steps": {
                "type": "ARRAY",
                "description": "Optional list of pre-planned steps, each with description, tool name, and parameters.",
                "items": {"type": "OBJECT"},
            },
            "project_context": {
                "type": "STRING",
                "description": "Optional active project name to bind with project awareness.",
            },
            "task_id": {
                "type": "STRING",
                "description": "Task identifier for checking status or cancelling.",
            },
            "max_steps": {
                "type": "INTEGER",
                "description": "Maximum number of steps to execute (default: 12).",
            },
        },
        "required": ["action"],
    },
    "handler": autonomous_task,
}
