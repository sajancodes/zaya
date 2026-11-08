"""Windows Scheduled Tasks & Task Scheduler Sentinel.
Created and developed by Sajan Rai for Zaya.

Inspects, audits, and monitors Windows Task Scheduler tasks, execution states,
next run times, and currently running background jobs via native schtasks telemetry.
"""
from __future__ import annotations

import csv
import io
import json
import logging
import subprocess
from typing import Any, Dict, List, Optional

from core.execution_policy import require_owner

logger = logging.getLogger(__name__)


def _query_all_tasks() -> List[Dict[str, str]]:
    """Execute schtasks to query all registered tasks as CSV."""
    cmd = ["schtasks", "/query", "/fo", "csv", "/nh"]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
        if proc.returncode != 0 or not proc.stdout.strip():
            return []

        tasks: List[Dict[str, str]] = []
        reader = csv.reader(io.StringIO(proc.stdout))
        for row in reader:
            if not row or len(row) < 3:
                continue
            task_name = row[0].strip()
            next_run = row[1].strip()
            status = row[2].strip()

            is_microsoft = task_name.startswith("\\Microsoft\\Windows\\") or task_name.startswith("\\Microsoft\\Xbl")
            folder = "Root"
            if task_name.startswith("\\"):
                parts = [p for p in task_name.split("\\") if p]
                if len(parts) > 1:
                    folder = parts[0]

            tasks.append({
                "task_name": task_name,
                "folder": folder,
                "next_run_time": next_run,
                "status": status,
                "is_microsoft": is_microsoft,
            })

        return tasks

    except (subprocess.TimeoutExpired, subprocess.SubprocessError, Exception) as exc:
        logger.warning("schtasks query failed: %s", exc)
        return []


def get_user_tasks(include_microsoft: bool = False) -> List[Dict[str, Any]]:
    """Retrieve scheduled tasks, by default filtering out internal OS telemetry noise."""
    all_tasks = _query_all_tasks()
    if include_microsoft:
        return all_tasks
    return [t for t in all_tasks if not t["is_microsoft"]]


def get_running_scheduled_tasks() -> List[Dict[str, Any]]:
    """Retrieve tasks that are currently actively executing."""
    all_tasks = _query_all_tasks()
    return [t for t in all_tasks if t["status"].lower() == "running"]


def search_tasks(query: str) -> List[Dict[str, Any]]:
    """Search for scheduled tasks matching keyword across all folders."""
    q = query.lower().strip()
    if not q:
        return []
    all_tasks = _query_all_tasks()
    return [t for t in all_tasks if q in t["task_name"].lower()]


def get_task_details(task_name: str) -> Dict[str, Any]:
    """Retrieve detailed verbose information for a specific scheduled task."""
    cmd = ["schtasks", "/query", "/tn", task_name, "/fo", "list", "/v"]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if proc.returncode != 0:
            return {"task_name": task_name, "error": proc.stderr.strip() or "Task not found."}

        details: Dict[str, str] = {"task_name": task_name}
        for line in proc.stdout.splitlines():
            line_str = line.strip()
            if not line_str or ":" not in line_str:
                continue
            key, sep, val = line_str.partition(":")
            clean_key = key.strip().lower().replace(" ", "_")
            details[clean_key] = val.strip()

        return details

    except (subprocess.TimeoutExpired, subprocess.SubprocessError, Exception) as exc:
        logger.warning("schtasks verbose query failed for %s: %s", task_name, exc)
        return {"task_name": task_name, "error": str(exc)}


def get_scheduler_summary() -> Dict[str, Any]:
    """Summarize overall Task Scheduler health and active background workloads."""
    all_tasks = _query_all_tasks()
    user_tasks = [t for t in all_tasks if not t["is_microsoft"]]
    running_tasks = [t for t in all_tasks if t["status"].lower() == "running"]

    # Deduplicate and sort upcoming tasks
    upcoming = [
        t for t in user_tasks
        if t["next_run_time"] and t["next_run_time"] != "N/A" and t["status"] == "Ready"
    ]

    return {
        "status": "success",
        "total_tasks_registered": len(all_tasks),
        "user_and_app_tasks_count": len(user_tasks),
        "running_tasks_count": len(running_tasks),
        "running_tasks": running_tasks,
        "upcoming_tasks": upcoming[:5],
        "sample_user_tasks": user_tasks[:10],
    }


def task_scheduler_sentinel(parameters: dict, **_kwargs) -> str:
    """Dispatches Windows Task Scheduler inspection and search actions."""
    require_owner()
    action = str(parameters.get("action") or "summary").lower().strip()
    include_ms = bool(parameters.get("include_microsoft", False))
    query = str(parameters.get("query") or "").strip()
    task_name = str(parameters.get("task_name") or "").strip()

    if action in ("summary", "health", "status"):
        summary = get_scheduler_summary()
        running_names = ", ".join(t["task_name"] for t in summary["running_tasks"]) if summary["running_tasks"] else "None"
        summary_text = (
            f"Windows Task Scheduler: {summary['total_tasks_registered']} total tasks "
            f"({summary['user_and_app_tasks_count']} application/user tasks). "
            f"Currently running: {summary['running_tasks_count']} ({running_names}). "
            f"Upcoming scheduled triggers: {len(summary['upcoming_tasks'])}."
        )
        return json.dumps({"status": "success", "summary": summary_text, "data": summary}, indent=2)

    if action in ("list", "list_tasks", "tasks"):
        tasks = get_user_tasks(include_microsoft=include_ms)
        scope = "all registered" if include_ms else "user/application"
        summary_text = f"Found {len(tasks)} {scope} scheduled tasks."
        return json.dumps({"status": "success", "summary": summary_text, "tasks": tasks}, indent=2)

    if action in ("running", "active"):
        running = get_running_scheduled_tasks()
        summary_text = f"Found {len(running)} actively executing scheduled tasks."
        return json.dumps({"status": "success", "summary": summary_text, "running_tasks": running}, indent=2)

    if action in ("search", "find"):
        if not query:
            return json.dumps({"status": "error", "message": "Search parameter 'query' is required."}, indent=2)
        results = search_tasks(query)
        summary_text = f"Found {len(results)} scheduled tasks matching '{query}'."
        return json.dumps({"status": "success", "summary": summary_text, "matches": results}, indent=2)

    if action in ("details", "inspect", "info"):
        if not task_name:
            return json.dumps({"status": "error", "message": "Task parameter 'task_name' is required."}, indent=2)
        details = get_task_details(task_name)
        summary_text = f"Details for task '{task_name}'."
        return json.dumps({"status": "success", "summary": summary_text, "details": details}, indent=2)

    return json.dumps({
        "status": "error",
        "message": f"Unknown action '{action}'. Choose from: summary, list_tasks, running, search, details."
    }, indent=2)


TOOL = {
    "name": "task_scheduler_sentinel",
    "description": "Inspect and audit Windows Task Scheduler: list scheduled jobs, check actively running tasks, view next run times, search task names, and view task details.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["summary", "list_tasks", "running", "search", "details"],
                "description": "Task scheduler action to execute (default: 'summary').",
            },
            "include_microsoft": {
                "type": "BOOLEAN",
                "description": "Include internal Microsoft Windows system tasks in list (default: false).",
            },
            "query": {
                "type": "STRING",
                "description": "Search keyword for finding tasks by name.",
            },
            "task_name": {
                "type": "STRING",
                "description": "Exact task name or path for inspect/details action.",
            },
        },
    },
    "handler": task_scheduler_sentinel,
}
