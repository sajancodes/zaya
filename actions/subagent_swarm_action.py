"""Parallel Sub-Worker Swarm Action.
Created and developed by Sajan Rai for Zaya.
"""
from __future__ import annotations

import json
from typing import Any, Dict

from core.subagent_swarm import get_subagent_swarm


def handle_subagent_swarm(
    action: str = "list",
    task_id: str = "",
    name: str = "",
    role: str = "",
    tool_name: str = "",
    parameters_json: str = "",
    timeout: float = 30.0,
) -> str:
    """Manage parallel sub-agent workers for concurrent multi-tasking."""
    swarm = get_subagent_swarm()

    if action == "list":
        tasks = swarm.list_tasks()
        return json.dumps({"status": "success", "count": len(tasks), "tasks": tasks})

    elif action == "status":
        if not task_id:
            return "Error: task_id is required for status."
        task = swarm.get_task(task_id)
        if not task:
            return f"Error: task_id '{task_id}' not found."
        return json.dumps({"status": "success", "task": task.to_dict()})

    elif action == "spawn":
        if not name or not role:
            return "Error: name and role are required to spawn a worker."
        if not tool_name:
            return "Error: tool_name is required to execute."

        params = json.loads(parameters_json) if parameters_json else {}

        def _exec():
            from core.action_loader import execute_tool
            return execute_tool(tool_name, params)

        task = swarm.spawn(name, role, _exec, metadata={"tool": tool_name})
        return json.dumps({
            "status": "success",
            "task_id": task.task_id,
            "name": name,
            "role": role,
            "message": f"Worker '{name}' spawned in background.",
        })

    elif action == "join":
        tids = [task_id] if task_id else None
        res = swarm.join(task_ids=tids, timeout=timeout)
        return json.dumps({"status": "success", "summary": res})

    elif action == "cancel":
        if not task_id:
            return "Error: task_id is required to cancel."
        ok = swarm.cancel(task_id)
        return json.dumps({"status": "success" if ok else "failed", "cancelled": ok})

    return f"Unknown swarm action: '{action}'."


TOOL = {
    "name": "subagent_swarm",
    "description": (
        "Decompose large goals into concurrent, non-blocking sub-worker agents. "
        "Spawn parallel research, diagnostics, compilation, or validation tasks."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["spawn", "list", "status", "join", "cancel"],
                "description": "Swarm coordination action.",
            },
            "task_id": {
                "type": "STRING",
                "description": "Specific subagent worker task ID (for status, join, or cancel).",
            },
            "name": {
                "type": "STRING",
                "description": "Human-readable worker name (e.g. 'PriceFetcher', 'CodeChecker').",
            },
            "role": {
                "type": "STRING",
                "description": "Worker role or description (e.g. 'Search web for flights').",
            },
            "tool_name": {
                "type": "STRING",
                "description": "Action/tool to execute in the worker thread.",
            },
            "parameters_json": {
                "type": "STRING",
                "description": "JSON arguments to pass to the tool.",
            },
            "timeout": {
                "type": "NUMBER",
                "description": "Timeout in seconds when joining workers.",
            },
        },
        "required": ["action"],
    },
    "handler": handle_subagent_swarm,
}
