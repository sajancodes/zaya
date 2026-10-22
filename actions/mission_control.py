"""Owner tool for managing multi-step autonomous background missions."""
from __future__ import annotations

from core.execution_policy import require_owner
from core.mission_supervisor import get_supervisor
from core.tool_result import ToolResult


def mission_control(parameters: dict, *, owner_request: str | None = None, **_kwargs) -> ToolResult:
    try:
        require_owner()
    except PermissionError:
        return ToolResult("failed", "Only the owner can execute background missions.", {"denied": True})

    supervisor = get_supervisor()
    action = str(parameters.get("action") or "status").lower().strip()
    goal = str(owner_request or parameters.get("goal") or "").strip()
    mission_id = str(parameters.get("mission_id") or "").strip()

    try:
        if action == "start":
            if not goal:
                return ToolResult("failed", "Missing required 'goal' parameter to start a mission.")
            mission = supervisor.start_mission(goal)
            return ToolResult(
                "started",
                f"Mission {mission.id} planned and started in background ({len(mission.steps)} steps).",
                {"mission": mission.public(), "progress_message": "I've started the background mission and will report each meaningful milestone."},
                side_effect=True,
            )

        elif action == "status":
            if mission_id:
                m = supervisor.get_mission(mission_id)
            else:
                m = supervisor.latest_mission()

            if m is None:
                return ToolResult("success", "No active or recent missions found.", {"mission": None})

            summary = f"Mission {m.id} ({m.goal[:60]}): {m.status} (step {m.current_step}/{len(m.steps)})."
            if m.error:
                summary += f" Error: {m.error}"
            elif m.summary:
                summary += f" {m.summary}"

            return ToolResult("success", summary, {"mission": m.public()})

        elif action == "cancel":
            if not mission_id:
                m = supervisor.latest_mission()
                mission_id = m.id if m else ""

            if not mission_id:
                return ToolResult("failed", "No mission specified or found to cancel.")

            ok = supervisor.cancel_mission(mission_id)
            if ok:
                return ToolResult("success", f"Mission {mission_id} cancelled.", {"cancelled": True}, side_effect=True)
            return ToolResult("failed", f"Mission {mission_id} not found.", {"cancelled": False})

        elif action == "list":
            limit = int(parameters.get("limit", 10))
            missions = supervisor.list_missions(limit=limit)
            return ToolResult(
                "success",
                f"Retrieved {len(missions)} missions.",
                {"missions": missions},
            )

        elif action == "continue":
            if not mission_id:
                m = supervisor.latest_mission()
                mission_id = m.id if m else ""

            if not mission_id:
                return ToolResult("failed", "No mission specified or found to continue.")

            approved = bool(parameters.get("approved", True))
            return supervisor.continue_mission(mission_id, approved=approved)

        else:
            return ToolResult("failed", f"Unknown mission action: '{action}'. Use start, status, cancel, list, or continue.")

    except Exception as e:
        return ToolResult("failed", f"Mission control error: {e}")


TOOL = {
    "name": "mission_control",
    "description": "Plan, supervise, inspect, continue, and cancel bounded multi-step autonomous background missions with verification checks.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "enum": ["start", "status", "cancel", "list", "continue"]},
            "goal": {"type": "STRING", "description": "The objective to plan and execute when action='start'."},
            "mission_id": {"type": "STRING", "description": "Optional specific mission ID for status, cancellation, or continue."},
            "approved": {"type": "BOOLEAN", "description": "Whether to approve pending confirmation when action='continue' (default True)."},
            "limit": {"type": "INTEGER", "description": "Maximum missions to return when action='list'."},
        },
        "required": ["action"],
    },
    "handler": mission_control,
}
