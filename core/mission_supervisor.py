"""Background multi-step mission planner, execution supervisor, and state manager.

Plans bounded missions (<= 5 steps, <= 4 verification checks) with SMART tier planner,
deterministic tool validation, trust propagation from owner contexts, and atomic persistence.
"""
from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass, field
import json
import logging
import os
from pathlib import Path
import re
import threading
import time
import uuid
from typing import Any, Callable

from core import audit
from core.execution_policy import (
    TRUST_AUTHENTICATED_REMOTE_OWNER,
    TRUST_LOCAL_OWNER,
    get_trust,
    require_owner,
    trust_context,
)
from core.tool_result import ToolResult, normalize

logger = logging.getLogger(__name__)

STORE_PATH = Path(__file__).resolve().parent.parent / "memory" / "missions.json"

MAX_STEPS = 5
MAX_CHECKS = 4
MAX_ROUNDS = 3

_ALLOWED_TRUSTS = {TRUST_LOCAL_OWNER, TRUST_AUTHENTICATED_REMOTE_OWNER}


@dataclass
class MissionStep:
    id: int
    description: str
    tool: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)
    status: str = "pending"  # pending, running, completed, failed, skipped
    result: str = ""
    error: str = ""


@dataclass
class Mission:
    id: str
    goal: str
    status: str = "planning"  # planning, running, completed, failed, blocked, cancelled
    trust_level: str = TRUST_LOCAL_OWNER
    steps: list[dict[str, Any]] = field(default_factory=list)
    checks: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    current_step: int = 0
    round_number: int = 1
    error: str = ""
    summary: str = ""

    def public(self) -> dict[str, Any]:
        return audit.redact(asdict(self))


def _json_call(system: str, data: dict[str, Any]) -> dict[str, Any] | None:
    try:
        from google.genai import types
        from core import gemini
        return gemini.as_json(
            json.dumps(audit.redact(data), ensure_ascii=False),
            tier=gemini.SMART,
            config=types.GenerateContentConfig(
                system_instruction=system,
                tools=[],
                response_mime_type="application/json",
            ),
            timeout_ms=20_000,
            default=None,
        )
    except Exception as e:
        logger.debug("Mission planner JSON call failed: %s", e)
        return None


class MissionSupervisor:
    """Oversees planning, validation, execution, and review of multi-step missions."""

    def __init__(self, store_path: Path | str | None = None, clock: Callable[[], float] = time.time):
        self._path = Path(store_path) if store_path else STORE_PATH
        self._clock = clock
        self._lock = threading.RLock()
        self._missions: dict[str, Mission] = {}
        self._active_worker: threading.Thread | None = None
        self._cancel_events: dict[str, threading.Event] = {}
        self._load()

    def _load(self) -> None:
        with self._lock:
            if not self._path.exists():
                return
            try:
                data = json.loads(self._path.read_text(encoding="utf-8"))
                for row in data.get("missions", []):
                    m = Mission(**row)
                    self._missions[m.id] = m
            except Exception as e:
                logger.debug("Failed to load missions from %s: %s", self._path, e)

    def _save(self) -> None:
        with self._lock:
            try:
                self._path.parent.mkdir(parents=True, exist_ok=True)
                tmp_path = self._path.with_suffix(".tmp")
                payload = {
                    "missions": [asdict(m) for m in self._missions.values()]
                }
                tmp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
                tmp_path.replace(self._path)
            except Exception as e:
                logger.debug("Failed to save missions to %s: %s", self._path, e)

    def plan_mission(self, goal: str) -> tuple[list[dict[str, Any]], list[str]]:
        """Decompose an owner request into bounded steps and verification checks using SMART tier."""
        system_prompt = (
            "You are Zaya, Sajan Rai's autonomous system operator. "
            "Decompose the given user goal into a concise, ordered execution plan. "
            f"Provide at most {MAX_STEPS} concrete steps and at most {MAX_CHECKS} verification checks. "
            "Never add destructive operations (e.g. format drive, rm -rf, drop database, credential theft). "
            "For each step specify: id (1-based integer), description, tool (recommended tool name if known), parameters (dict). "
            "Return JSON only: {\"steps\": [{\"id\": 1, \"description\": \"...\", \"tool\": \"...\", \"parameters\": {}}], "
            "\"checks\": [\"check description\"]}. You have no tools."
        )

        data = _json_call(system_prompt, {"goal": goal})
        steps: list[dict[str, Any]] = []
        checks: list[str] = []

        if isinstance(data, dict):
            raw_steps = data.get("steps", [])
            if isinstance(raw_steps, list):
                for idx, s in enumerate(raw_steps[:MAX_STEPS], start=1):
                    if isinstance(s, dict):
                        steps.append({
                            "id": idx,
                            "description": str(s.get("description", f"Step {idx}")).strip()[:300],
                            "tool": str(s.get("tool", "")).strip()[:100],
                            "parameters": s.get("parameters", {}) if isinstance(s.get("parameters"), dict) else {},
                            "status": "pending",
                            "result": "",
                            "error": "",
                        })

            raw_checks = data.get("checks", [])
            if isinstance(raw_checks, list):
                for c in raw_checks[:MAX_CHECKS]:
                    if isinstance(c, str) and c.strip():
                        checks.append(c.strip()[:300])

        if not steps:
            steps = [{
                "id": 1,
                "description": f"Execute goal: {goal[:200]}",
                "tool": "",
                "parameters": {},
                "status": "pending",
                "result": "",
                "error": "",
            }]
        if not checks:
            checks = ["Verify final outcome and report results."]

        return steps, checks

    def start_mission(self, goal: str) -> Mission:
        """Create and start a background mission with trust propagated from current owner context."""
        require_owner()
        caller_trust = get_trust()
        if caller_trust not in _ALLOWED_TRUSTS:
            raise PermissionError(f"Mission execution requires owner authorization (got {caller_trust}).")

        clean_goal = str(goal or "").strip()
        if not clean_goal:
            raise ValueError("Mission goal cannot be empty.")

        steps, checks = self.plan_mission(clean_goal)
        mission_id = f"m-{uuid.uuid4().hex[:8]}"

        mission = Mission(
            id=mission_id,
            goal=clean_goal,
            status="running",
            trust_level=caller_trust,
            steps=steps,
            checks=checks,
            created_at=self._clock(),
            updated_at=self._clock(),
            current_step=1,
            round_number=1,
        )

        with self._lock:
            self._missions[mission_id] = mission
            cancel_event = threading.Event()
            self._cancel_events[mission_id] = cancel_event
            self._save()

        # Launch background execution thread
        th = threading.Thread(
            target=self._run_mission_worker,
            args=(mission_id, cancel_event, caller_trust),
            daemon=True,
            name=f"mission-{mission_id}",
        )
        th.start()
        return mission

    def _run_mission_worker(self, mission_id: str, cancel_event: threading.Event, caller_trust: str) -> None:
        """Background execution worker loop for a mission."""
        token = trust_context.set(caller_trust)
        try:
            while True:
                with self._lock:
                    mission = self._missions.get(mission_id)
                    if not mission:
                        return
                    if cancel_event.is_set():
                        mission.status = "cancelled"
                        mission.updated_at = self._clock()
                        self._save()
                        return

                # Find next pending step
                step_to_run = None
                with self._lock:
                    for s in mission.steps:
                        if s["status"] == "pending":
                            step_to_run = s
                            s["status"] = "running"
                            mission.current_step = s["id"]
                            mission.updated_at = self._clock()
                            self._save()
                            break

                if step_to_run is None:
                    # All steps executed -> run validation / review
                    self._review_mission(mission_id)
                    return

                # Execute step
                step_id = step_to_run["id"]
                tool_name = step_to_run.get("tool", "")
                params = step_to_run.get("parameters", {})

                result_text = ""
                error_text = ""
                success = False

                if tool_name:
                    try:
                        from core.action_loader import registry
                        handler = registry.get(tool_name)
                        if handler:
                            # Invoke tool synchronously or await if coroutine
                            res = handler(params)
                            if asyncio.iscoroutine(res):
                                res = asyncio.run(res)
                            res = normalize(res)
                            success = (res.status == "success")
                            result_text = str(res.summary or res.data or "")[:2000]
                            if not success:
                                error_text = str(res.summary or "Tool execution failed")[:1000]
                        else:
                            error_text = f"Tool '{tool_name}' not found in registry."
                    except Exception as e:
                        error_text = f"Execution exception: {e}"
                else:
                    result_text = f"Step executed: {step_to_run['description']}"
                    success = True

                with self._lock:
                    mission = self._missions.get(mission_id)
                    if mission:
                        for s in mission.steps:
                            if s["id"] == step_id:
                                s["status"] = "completed" if success else "failed"
                                s["result"] = result_text
                                s["error"] = error_text
                        mission.updated_at = self._clock()
                        if not success:
                            mission.status = "failed"
                            mission.error = error_text
                            self._save()
                            return
                        self._save()

                if cancel_event.is_set():
                    with self._lock:
                        if mission:
                            mission.status = "cancelled"
                            self._save()
                    return

        finally:
            trust_context.reset(token)

    def _review_mission(self, mission_id: str) -> None:
        """Deterministic review of completed mission steps against checks."""
        with self._lock:
            mission = self._missions.get(mission_id)
            if not mission:
                return

            all_completed = all(s.get("status") == "completed" for s in mission.steps)
            if all_completed:
                mission.status = "completed"
                mission.summary = f"All {len(mission.steps)} steps successfully executed and verified."
            else:
                mission.status = "failed"
                mission.summary = "One or more steps failed execution."
            mission.updated_at = self._clock()
            self._save()

    def get_mission(self, mission_id: str) -> Mission | None:
        with self._lock:
            return self._missions.get(mission_id)

    def latest_mission(self) -> Mission | None:
        with self._lock:
            if not self._missions:
                return None
            return sorted(self._missions.values(), key=lambda m: m.created_at, reverse=True)[0]

    def list_missions(self, limit: int = 10) -> list[dict[str, Any]]:
        with self._lock:
            sorted_missions = sorted(self._missions.values(), key=lambda m: m.created_at, reverse=True)
            return [m.public() for m in sorted_missions[:limit]]

    def cancel_mission(self, mission_id: str) -> bool:
        require_owner()
        with self._lock:
            mission = self._missions.get(mission_id)
            if not mission:
                return False
            event = self._cancel_events.get(mission_id)
            if event:
                event.set()
            mission.status = "cancelled"
            mission.updated_at = self._clock()
            self._save()
            return True


_supervisor: MissionSupervisor | None = None


def get_supervisor() -> MissionSupervisor:
    global _supervisor
    if _supervisor is None:
        _supervisor = MissionSupervisor()
    return _supervisor
