"""Continuous Screen Monitor Action powered by Gemini Robotics ER-2 Streaming Model.
Created and developed by Sajan Rai for Zaya.
"""
from __future__ import annotations

import json
from typing import Any, Dict, Optional

from core.robotics_monitor import get_robotics_screen_monitor


def handle_robotics_screen_monitor(
    action: str = "status",
    task: str = "",
    interval_sec: float = 3.0,
    max_duration_sec: int = 14400,
) -> str:
    """Continuous screen surveillance and spatial affordance analysis via Gemini Robotics ER-2."""
    monitor = get_robotics_screen_monitor()

    if action == "status":
        st = monitor.status()
        return json.dumps({"status": "success", "monitor_status": st})

    elif action == "start":
        res = monitor.start(
            task_objective=task,
            interval_sec=interval_sec,
            max_duration_sec=max_duration_sec,
        )
        return json.dumps({"status": "success", "result": res})

    elif action == "stop":
        res = monitor.stop()
        return json.dumps({"status": "success", "result": res})

    elif action == "observe_now":
        obs = monitor.observe_now(task=task)
        return json.dumps({
            "status": "success",
            "observation": obs.to_dict(),
        })

    elif action == "recent":
        history = monitor.get_recent_observations(limit=10)
        return json.dumps({
            "status": "success",
            "count": len(history),
            "observations": history,
        })

    elif action == "set_interval":
        new_int = monitor.set_interval(interval_sec)
        return json.dumps({
            "status": "success",
            "interval_sec": new_int,
        })

    return f"Unknown robotics_screen_monitor action: '{action}'."


TOOL = {
    "name": "robotics_screen_monitor",
    "description": (
        "Continuous high-temporal screen monitoring using models/gemini-robotics-er-2-streaming-preview. "
        "Perceives continuous UI state transitions, terminal compilation errors, stuck progress bars, "
        "dialog prompts, and spatial affordances with automated fallback."
    ),
    "handler": handle_robotics_screen_monitor,
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["start", "stop", "status", "observe_now", "recent", "set_interval"],
                "description": "Action to perform on the robotics screen monitor.",
            },
            "task": {
                "type": "STRING",
                "description": "Task objective or surveillance instruction (e.g. 'Watch terminal build, alert if error occurs').",
            },
            "interval_sec": {
                "type": "NUMBER",
                "description": "Continuous screen sampling interval in seconds (default 3.0s).",
            },
            "max_duration_sec": {
                "type": "INTEGER",
                "description": "Maximum monitoring session duration in seconds (default 14400 = 4 hours).",
            },
        },
        "required": ["action"],
    },
}
