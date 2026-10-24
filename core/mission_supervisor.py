"""Background multi-step mission planner, execution supervisor, and state manager.

Plans bounded missions (<= 5 steps, <= 4 verification checks) with SMART tier planner,
deterministic tool validation, trust propagation from owner contexts, execution through
Operator and canonical confirmation policies, and atomic persistence.
"""
from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass, field
import json
import logging
import os
from pathlib import Path
from core.runtime_paths import mutable_path
import re
import threading
import time
import uuid
from typing import Any, Callable

from core import audit
from core.event_bus import bus
from core.execution_policy import (
    TRUST_AUTHENTICATED_REMOTE_OWNER,
    TRUST_LOCAL_OWNER,
    get_trust,
    require_owner,
    trust_context,
)
from core.tool_result import ToolResult, normalize

logger = logging.getLogger(__name__)

STORE_PATH = mutable_path(Path(__file__).resolve().parent.parent / "memory" / "missions.json")

MAX_STEPS = 5
MAX_CHECKS = 4
MAX_ROUNDS = 3
MAX_STEP_ATTEMPTS = 3
MAX_HISTORY_MISSIONS = 150

_ALLOWED_TRUSTS = {TRUST_LOCAL_OWNER, TRUST_AUTHENTICATED_REMOTE_OWNER}

# Explicit whitelist of tools permissible in background missions
MISSION_ALLOWED_TOOLS = {
    "system_diagnostics",
    "runtime_status",
    "runtime_logs",
    "computer_control",
    "computer_settings",
    "file_controller",
    "file_processor",
    "open_app",
    "terminate_app",
    "browser_control",
    "web_search",
    "git_control",
    "game_updater",
    "personal_profile",
    "reminder",
    "conversation_history",
    "session_activity",
    "terminal_exec",
}

# Operation classification mapping for tools
TOOL_OPERATION_CLASSES: dict[str, set[str]] = {
    "system_diagnostics": {"inspect_system", "read"},
    "runtime_status": {"inspect_system", "read"},
    "runtime_logs": {"inspect_system", "read"},
    "personal_profile": {"read"},
    "conversation_history": {"read"},
    "session_activity": {"read", "change_settings"},
    "web_search": {"search", "read"},
    "open_app": {"run_command", "computer_control"},
    "terminate_app": {"terminate_process"},
    "computer_control": {"computer_control"},
    "computer_settings": {"change_settings", "computer_control"},
    "file_controller": {"inspect_files", "read", "write_files", "delete"},
    "file_processor": {"inspect_files", "read", "write_files"},
    "browser_control": {"search", "read", "computer_control"},
    "git_control": {"git_commit", "git_push"},
    "game_updater": {"install", "run_command"},
    "reminder": {"write_files"},
    "terminal_exec": {"run_command"},
}


def classify_goal_scope(goal: str) -> set[str]:
    """Deterministically classify authorized operation classes from the owner's request."""
    g = str(goal or "").lower()
    allowed: set[str] = {"read", "search", "inspect_system", "inspect_files"}

    # Process termination
    if re.search(r"\b(kill|terminate|close|stop|end|abort)\b.*\b(process|app|program|task|chrome|brave|window)\b", g) or \
       re.search(r"\b(kill|terminate|close)\b", g):
        allowed.add("terminate_process")

    # File operations
    if re.search(r"\b(write|create|edit|modify|save|append|update|touch|make|generate|move|copy|rename)\b.*\b(file|script|code|folder|directory)\b", g):
        allowed.add("write_files")
    if re.search(r"\b(delete|remove|erase|clean|clear|purge|rm|unlink)\b", g):
        allowed.add("delete")

    # Computer control and settings
    if re.search(r"\b(click|press|type|hotkey|drag|scroll|mouse|cursor|grounding)\b", g):
        allowed.add("computer_control")
    if re.search(r"\b(volume|brightness|dark mode|wifi|bluetooth|setting|mute|unmute|shutdown|restart)\b", g):
        allowed.add("change_settings")

    # Commands / installation
    if re.search(r"\b(run|execute|open|launch|command|script|shell|terminal|powershell|pwsh|cmd)\b", g):
        allowed.add("run_command")
    if re.search(r"\b(install|setup|update game|upgrade|download)\b", g):
        allowed.add("install")
    if re.search(r'\b(remind|reminder)\b', g):
        allowed.add('write_files')

    # Git
    if re.search(r"\b(git|commit|stage)\b", g):
        allowed.add("git_commit")
    if re.search(r"\b(push|publish)\b", g):
        allowed.add("git_push")

    # Messages / external
    if re.search(r"\b(send|message|whatsapp|telegram|email|call)\b", g):
        allowed.add("send_message")

    return allowed


def validate_step(tool_name: str, parameters: dict[str, Any], allowed_scopes: set[str]) -> str | None:
    """Validate step tool, authorization scope, and parameters. Returns error string or None."""
    tool_name = str(tool_name or "").strip()
    if not tool_name:
        return "Empty tool name (empty tool steps are rejected)."

    if tool_name not in MISSION_ALLOWED_TOOLS:
        return f"Tool '{tool_name}' is not in the mission allowed tools set."

    if not isinstance(parameters, dict):
        return f"Parameters for tool '{tool_name}' must be a dictionary."
    tool_scopes = _step_scopes(tool_name, parameters)
    if not tool_scopes or not tool_scopes.issubset(allowed_scopes):
        return f"Tool '{tool_name}' requires operation classes {sorted(tool_scopes)}, but authorized scope is {sorted(allowed_scopes)}."

    if not isinstance(parameters, dict):
        return f"Parameters for tool '{tool_name}' must be a dictionary."

    # Parameter schema inspection
    try:
        from core.action_loader import get_action_registry
        reg = get_action_registry()
        rec = reg._actions.get(tool_name)
        if rec and rec.parameters:
            schema = rec.parameters
            required = schema.get("required", [])
            for req in required:
                if req not in parameters:
                    return f"Missing required parameter '{req}' for tool '{tool_name}'."
            props = schema.get("properties", {})
            for k, v in parameters.items():
                if isinstance(v, str) and len(v) > 5000:
                    return f"Parameter '{k}' exceeds length limits."
                if k in props and "enum" in props[k]:
                    if v not in props[k]["enum"]:
                        return f"Invalid value '{v}' for '{k}'. Expected {props[k]['enum']}."
    except Exception as e:
        logger.debug("Schema validation error: %s", e)

    return None


def _step_scopes(tool: str, params: dict) -> set[str]:
    """Classify the selected operation, never the union of a tool's abilities."""
    action = str(params.get('action', '')).strip().lower()
    if tool == 'file_controller':
        if action in {'list', 'read', 'find', 'largest', 'disk_usage', 'info'}:
            return {'inspect_files'}
        return {'delete'} if action == 'delete' else {'write_files'}
    if tool == 'file_processor':
        if action in {'info', 'stats', 'word_count', 'describe', 'ocr', 'analyze', 'read', 'extract_text', 'list', 'validate', 'summarize', 'transcribe'}:
            return {'read'}
        return {'run_command'} if action == 'run' else {'write_files'}
    if tool == 'git_control':
        if action in {'repo_info', 'status', 'diff', 'diff_staged', 'branches', 'log', 'remote', 'verify_push'}:
            return {'read'}
        return {'git_push'} if action == 'push' else {'git_commit'}
    if tool == 'personal_profile':
        return {'read'} if action in {'get', 'read', 'show', 'status', 'list', ''} else {'change_settings'}
    if tool == 'session_activity':
        return {'read'} if action in {'get', 'read', 'status', 'list', ''} else {'change_settings'}
    if tool == 'browser_control':
        return {'read'} if action in {'tabs', 'list_tabs', 'read', 'get_text', 'status', 'screenshot'} else {'computer_control'}
    if tool == 'runtime_logs':
        return {'read'} if action in {'read', 'status', ''} else {'computer_control'}
    if tool == 'computer_settings':
        if not action:
            return set()  # Require an explicit action rather than model inference.
        if action in {'press_key', 'type_text', 'write_on_screen', 'type', 'write'} or any(
                token in action for token in ('scroll', 'window', 'tab', 'click', 'refresh', 'reload', 'fullscreen', 'zoom')):
            return {'computer_control'}
        return {'change_settings'}
    if tool == 'game_updater':
        if action in {'list', 'download_status', 'schedule_status'}:
            return {'read'}
        if params.get('shutdown_when_done') not in (None, False, 'false', '0', 0):
            return {'install', 'change_settings'}
        # A mission must not inherit an unrelated global shutdown setting.
        params.setdefault('shutdown_when_done', False)
        return {'install'}
    if tool == 'reminder':
        return {'read'} if action in {'status', 'list'} else {'write_files'}
    if tool == 'open_app':
        return {'run_command'}
    if tool == 'web_search':
        return {'search'}
    # Single-purpose tools do not combine read and mutation scopes.
    return TOOL_OPERATION_CLASSES.get(tool, set())


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
    status: str = "planning"  # planning, running, completed, completed_unverified, failed, blocked, cancelled, waiting_confirmation, waiting_clarification, waiting_external, paused, interrupted
    trust_level: str = TRUST_LOCAL_OWNER
    steps: list[dict[str, Any]] = field(default_factory=list)
    checks: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    current_step: int = 0
    round_number: int = 1
    error: str = ""
    summary: str = ""
    pending_confirmation: dict[str, Any] | None = None

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
        self._cancel_events: dict[str, threading.Event] = {}
        self._load()

    @staticmethod
    def _emit_progress(mission: Mission, stage: str, detail: str = "") -> None:
        try:
            bus.publish(
                "mission.progress",
                mission_id=mission.id,
                goal=mission.goal,
                status=mission.status,
                stage=stage,
                detail=str(detail)[:500],
                step=mission.current_step,
            )
        except Exception:
            pass

    def _load(self) -> None:
        with self._lock:
            if not self._path.exists():
                return
            try:
                raw = json.loads(self._path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    rows = raw.get("missions", list(raw.values()) if not raw.get("missions") else [])
                elif isinstance(raw, list):
                    rows = raw
                else:
                    rows = []

                for row in rows:
                    if isinstance(row, dict) and "id" in row and "goal" in row:
                        m = Mission(**row)
                        # Crash/restart recovery: any previously running or waiting mission becomes paused/interrupted
                        if m.status in ("running", "planning"):
                            m.status = "interrupted"
                            m.error = "Mission interrupted by system restart. Resume explicitly via continue."
                        elif m.status in ("waiting_confirmation", "waiting_clarification", "waiting_external"):
                            m.status = "paused"
                            m.error = "Pending owner decision or external operation preserved on restart. Continue explicitly."
                        self._missions[m.id] = m
            except Exception as e:
                logger.error("Corrupt or invalid missions.json at %s: %s", self._path, e)
                # Keep existing in-memory state or fresh store if unreadable

    def _save(self) -> None:
        with self._lock:
            try:
                self._prune_history()
                self._path.parent.mkdir(parents=True, exist_ok=True)
                tmp_path = self._path.with_suffix(".tmp")
                payload = {
                    "missions": [asdict(m) for m in self._missions.values()]
                }
                tmp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
                tmp_path.replace(self._path)
            except Exception as e:
                logger.debug("Failed to save missions to %s: %s", self._path, e)

    def _prune_history(self, keep: int = MAX_HISTORY_MISSIONS) -> None:
        """Keep 100-200 missions, preserving unfinished/interrupted missions."""
        if len(self._missions) <= keep:
            return

        unfinished_states = ("running", "planning", "interrupted", "paused", "waiting_confirmation",
                             "waiting_clarification", "waiting_external")
        unfinished = {mid: m for mid, m in self._missions.items() if m.status in unfinished_states}
        terminal = [m for m in self._missions.values() if m.status not in unfinished_states]
        terminal.sort(key=lambda m: m.created_at, reverse=True)

        keep_count = max(0, keep - len(unfinished))
        kept_terminal = {m.id: m for m in terminal[:keep_count]}

        self._missions = {**unfinished, **kept_terminal}

    def plan_mission(self, goal: str) -> tuple[list[dict[str, Any]], list[str]]:
        """Decompose an owner request into bounded steps and verification checks."""
        allowed_scopes = classify_goal_scope(goal)
        allowed_tool_list = sorted([t for t in MISSION_ALLOWED_TOOLS if TOOL_OPERATION_CLASSES.get(t, set()) & allowed_scopes])

        system_prompt = (
            "You are Zaya, Sajan Rai's autonomous system operator. "
            "Decompose the given user goal into a concise, ordered execution plan. "
            f"You may ONLY choose tools from this exact allowed list: {allowed_tool_list}. "
            f"Provide at most {MAX_STEPS} concrete steps and at most {MAX_CHECKS} verification checks. "
            "Never invent tools outside the allowed list. Every step must have a non-empty tool. "
            "For each step specify: id (1-based integer), description, tool (must be from allowed list), parameters (dict). "
            "Return JSON only: {\"steps\": [{\"id\": 1, \"description\": \"...\", \"tool\": \"...\", \"parameters\": {}}], "
            "\"checks\": [\"concrete check description\"]}. You have no tools."
        )

        data = _json_call(system_prompt, {"goal": goal, "allowed_tools": allowed_tool_list})
        steps: list[dict[str, Any]] = []
        checks: list[str] = []

        if isinstance(data, dict):
            raw_steps = data.get("steps", [])
            if isinstance(raw_steps, list):
                for idx, s in enumerate(raw_steps[:MAX_STEPS], start=1):
                    if isinstance(s, dict):
                        tool_candidate = str(s.get("tool", "")).strip().lower()
                        steps.append({
                            "id": idx,
                            "description": str(s.get("description", f"Step {idx}")).strip()[:300],
                            "tool": tool_candidate,
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

        if not checks:
            checks = ["Verify primary goal execution outcome."]

        return steps, checks

    def validate_step(self, step: dict[str, Any], goal: str) -> tuple[bool, str]:
        """Validate step tool, authorization scope, and parameters."""
        tool_name = step.get("tool", "")
        params = step.get("parameters", {})
        err = validate_step(tool_name, params, classify_goal_scope(goal))
        if err:
            return False, err
        return True, ""

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
        if not steps:
            raise ValueError("Planner failed to produce valid executable steps.")

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

        self._emit_progress(mission, "started", f"{len(mission.steps)} planned steps")
        self._spawn_worker(mission_id, cancel_event, caller_trust)
        return mission

    def execute_step_sync(self, mission_id: str) -> None:
        """Execute one pending step synchronously (used in tests and stepping)."""
        cancel_event = self._cancel_events.get(mission_id, threading.Event())
        caller_trust = self._missions[mission_id].trust_level if mission_id in self._missions else TRUST_LOCAL_OWNER
        # Run one iteration of worker logic
        with self._lock:
            mission = self._missions.get(mission_id)
            if not mission or mission.status in ("paused", "waiting_confirmation", "waiting_clarification",
                                                 "waiting_external", "interrupted", "failed", "cancelled",
                                                 "completed", "completed_unverified"):
                return
            step_to_run = None
            for s in mission.steps:
                if s["status"] == "pending":
                    if int(s.get('attempts', 0)) >= MAX_STEP_ATTEMPTS:
                        mission.status, mission.error = 'failed', 'Step retry budget exhausted.'
                        self._save()
                        return
                    s['attempts'] = int(s.get('attempts', 0)) + 1
                    step_to_run = s
                    s["status"] = "running"
                    mission.current_step = s["id"]
                    mission.updated_at = self._clock()
                    self._save()
                    break

        if step_to_run is None:
            self._review_and_verify_mission(mission_id)
            return

        valid, reason = self.validate_step(step_to_run, mission.goal)
        if not valid:
            with self._lock:
                mission = self._missions.get(mission_id)
                if mission:
                    step_to_run["status"] = "failed"
                    step_to_run["error"] = reason
                    mission.status = "failed"
                    mission.error = f"Step validation failed: {reason}"
                    mission.updated_at = self._clock()
                    self._save()
            return

        step_id = step_to_run["id"]
        tool_name = step_to_run["tool"]
        params = step_to_run.get("parameters", {})

        result, needs_confirm = self._execute_step_via_operator(tool_name, params, mission.goal, caller_trust)

        if needs_confirm:
            with self._lock:
                mission = self._missions.get(mission_id)
                if mission:
                    step_to_run["status"] = "pending"
                    mission.status = "waiting_confirmation"
                    mission.pending_confirmation = {
                        "step_id": step_id,
                        "tool": tool_name,
                        "parameters": params,
                        "runtime_task_id": result.data.get('runtime_task_id'),
                        "kind": "confirmation",
                    }
                    mission.updated_at = self._clock()
                    self._save()
                    self._emit_progress(mission, "waiting_confirmation", result.summary)
            return

        status = str(result.status or "failed")
        result_text = str(result.summary or result.data or "")[:2000]
        error_text = str(result.summary or "Tool execution failed")[:1000] if status == "failed" else ""

        if status == "ambiguous":
            with self._lock:
                mission = self._missions.get(mission_id)
                if mission:
                    step_to_run["status"] = "pending"
                    mission.status = "waiting_clarification"
                    mission.pending_confirmation = {
                        "step_id": step_id, "tool": tool_name,
                        "parameters": params, "kind": "clarification",
                    }
                    mission.error = result.summary
                    mission.updated_at = self._clock()
                    self._save()
                    self._emit_progress(mission, "waiting_clarification", result.summary)
            return

        if status == "started":
            with self._lock:
                mission = self._missions.get(mission_id)
                if mission:
                    for s in mission.steps:
                        if s["id"] == step_id:
                            s["status"] = "started"
                            s["result"] = result_text
                            s["error"] = ""
                    mission.status = "waiting_external"
                    mission.summary = f"Started: {result.summary}"
                    mission.pending_confirmation = {
                        "step_id": step_id, "tool": tool_name,
                        "parameters": params, "kind": "external",
                    }
                    mission.updated_at = self._clock()
                    self._save()
                    self._emit_progress(mission, "started_external", result.summary)
            return

        with self._lock:
            mission = self._missions.get(mission_id)
            if mission:
                success = status == "success"
                unverified = status == "partial"
                for s in mission.steps:
                    if s["id"] == step_id:
                        s["status"] = "completed" if success else ("unverified" if unverified else "failed")
                        s["result"] = result_text
                        s["error"] = error_text
                mission.updated_at = self._clock()
                if not success and not unverified:
                    if result.retryable and not result.side_effect and step_to_run.get('attempts', 0) < MAX_STEP_ATTEMPTS:
                        step_to_run["status"] = "pending"
                        step_to_run["error"] = f"Retryable error: {error_text}"
                    else:
                        mission.status = "failed"
                        mission.error = error_text
                self._save()
                self._emit_progress(mission, "step_complete" if success else "step_unverified",
                                    f"{step_id}: {result.summary}")

    def _spawn_worker(self, mission_id: str, cancel_event: threading.Event, caller_trust: str) -> None:
        th = threading.Thread(
            target=self._run_mission_worker,
            args=(mission_id, cancel_event, caller_trust),
            daemon=True,
            name=f"mission-{mission_id}",
        )
        th.start()

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
                    if mission.status in ("paused", "waiting_confirmation", "waiting_clarification",
                                          "waiting_external", "interrupted", "failed", "cancelled",
                                          "completed", "completed_unverified"):
                        return

                step_to_run = None
                with self._lock:
                    for s in mission.steps:
                        if s["status"] == "pending":
                            if int(s.get('attempts', 0)) >= MAX_STEP_ATTEMPTS:
                                mission.status, mission.error = 'failed', 'Step retry budget exhausted.'
                                self._save()
                                return
                            s['attempts'] = int(s.get('attempts', 0)) + 1
                            step_to_run = s
                            s["status"] = "running"
                            mission.current_step = s["id"]
                            mission.updated_at = self._clock()
                            self._save()
                            break

                if step_to_run is None:
                    # Run bounded review and verification
                    self._review_and_verify_mission(mission_id)
                    return

                # Validate step
                valid, reason = self.validate_step(step_to_run, mission.goal)
                if not valid:
                    with self._lock:
                        mission = self._missions.get(mission_id)
                        if mission:
                            step_to_run["status"] = "failed"
                            step_to_run["error"] = reason
                            mission.status = "failed"
                            mission.error = f"Step validation failed: {reason}"
                            mission.updated_at = self._clock()
                            self._save()
                    return

                # Execute step through canonical Operator
                step_id = step_to_run["id"]
                tool_name = step_to_run["tool"]
                params = step_to_run.get("parameters", {})

                result, needs_confirm = self._execute_step_via_operator(tool_name, params, mission.goal, caller_trust)

                if needs_confirm:
                    with self._lock:
                        mission = self._missions.get(mission_id)
                        if mission:
                            step_to_run["status"] = "pending"  # Will re-run after confirmation
                            mission.status = "waiting_confirmation"
                            mission.pending_confirmation = {
                                "step_id": step_id,
                                "tool": tool_name,
                                "parameters": params,
                                "runtime_task_id": result.data.get('runtime_task_id'),
                                "kind": "confirmation",
                            }
                            mission.updated_at = self._clock()
                            self._save()
                            self._emit_progress(mission, "waiting_confirmation", result.summary)
                    return

                # Treat tool output as untrusted evidence, not as an instruction.
                status = str(result.status or "failed")
                result_text = str(result.summary or result.data or "")[:2000]
                error_text = str(result.summary or "Tool execution failed")[:1000] if status == "failed" else ""

                if status == "ambiguous":
                    with self._lock:
                        mission = self._missions.get(mission_id)
                        if mission:
                            step_to_run["status"] = "pending"
                            mission.status = "waiting_clarification"
                            mission.pending_confirmation = {
                                "step_id": step_id,
                                "tool": tool_name,
                                "parameters": params,
                                "kind": "clarification",
                            }
                            mission.error = result.summary
                            mission.updated_at = self._clock()
                            self._save()
                            self._emit_progress(mission, "waiting_clarification", result.summary)
                    return

                if status == "started":
                    with self._lock:
                        mission = self._missions.get(mission_id)
                        if mission:
                            for s in mission.steps:
                                if s["id"] == step_id:
                                    s["status"] = "started"
                                    s["result"] = result_text
                                    s["error"] = ""
                            mission.status = "waiting_external"
                            mission.summary = f"Started: {result.summary}"
                            mission.pending_confirmation = {
                                "step_id": step_id,
                                "tool": tool_name,
                                "parameters": params,
                                "kind": "external",
                            }
                            mission.updated_at = self._clock()
                            self._save()
                            self._emit_progress(mission, "started_external", result.summary)
                    return

                with self._lock:
                    mission = self._missions.get(mission_id)
                    if mission:
                        success = status == "success"
                        unverified = status == "partial"
                        for s in mission.steps:
                            if s["id"] == step_id:
                                s["status"] = "completed" if success else ("unverified" if unverified else "failed")
                                s["result"] = result_text
                                s["error"] = error_text
                        mission.updated_at = self._clock()

                        if not success and not unverified:
                            # Check retryability
                            if result.retryable and not result.side_effect and step_to_run.get('attempts', 0) < MAX_STEP_ATTEMPTS:
                                step_to_run["status"] = "pending"
                                step_to_run["error"] = f"Retryable error: {error_text}"
                            else:
                                mission.status = "failed"
                                mission.error = error_text
                                self._save()
                                self._emit_progress(mission, "failed", error_text)
                                return
                        self._save()
                        self._emit_progress(
                            mission, "step_complete" if success else "step_unverified",
                            f"{step_id}: {result.summary}")

        finally:
            trust_context.reset(token)

    def _execute_step_via_operator(self, tool_name: str, params: dict[str, Any], goal: str, trust_level: str) -> tuple[ToolResult, bool]:
        """Execute action through Operator, respecting confirmations and audit trails."""
        from core.action_loader import get_action_registry
        from core.operator import Operator
        from core.task_runtime import get_runtime
        from memory.config_manager import get_auto_execute_enabled

        reg = get_action_registry()
        rec = reg._actions.get(tool_name)
        if not rec or not rec.handler:
            return ToolResult("failed", f"Tool '{tool_name}' not available in registry."), False

        handler = rec.handler

        async def _invoke():
            if tool_name == 'terminate_app' and not get_auto_execute_enabled():
                from core import confirm
                from core.operator import current_task
                from core.execution_policy import with_trust
                task_id = current_task.get()
                runtime = get_runtime()
                def approved():
                    with with_trust(trust_level):
                        try:
                            result = normalize(handler(params))
                        except Exception as error:
                            result = ToolResult('failed', f'Confirmed step failed: {type(error).__name__}')
                        runtime.finish(task_id, result)
                        return str(result)
                def cancelled(reason):
                    runtime.transition(task_id, 'cancelled', error=reason)
                return normalize(confirm.request('mission-terminate-' + task_id,
                    'Terminate application for mission', str(params), approved, on_cancel=cancelled))
            res = handler(params)
            if asyncio.iscoroutine(res):
                res = await res
            return normalize(res)

        operator = Operator(get_runtime())
        try:
            loop = asyncio.new_event_loop()
            res = loop.run_until_complete(
                operator.execute(
                    name=tool_name,
                    invoke=_invoke,
                    request_id=f"mission-{uuid.uuid4().hex[:10]}",
                    goal=goal,
                    arguments=dict(params or {}),
                    trust_level=trust_level,
                )
            )
            return res, res.status == 'waiting_confirmation'
        except Exception as e:
            return ToolResult("failed", f"Operator execution exception: {e}"), False
        finally:
            if 'loop' in locals():
                loop.close()

    def _review_and_verify_mission(self, mission_id: str) -> None:
        """Bounded review loop and real verification of checks."""
        with self._lock:
            mission = self._missions.get(mission_id)
            if not mission:
                return

        # 1. Deterministic verification of outcomes
        verification_passed, verif_detail = self._verify_checks(mission)

        # 2. Review loop if incomplete and rounds remain
        if not verification_passed and mission.round_number < MAX_ROUNDS:
            followup_steps = self._review_followup(mission, verif_detail)
            if followup_steps:
                with self._lock:
                    mission.round_number += 1
                    mission.steps.extend(followup_steps)
                    mission.updated_at = self._clock()
                    self._save()
                # Continue execution
                cancel_event = self._cancel_events.get(mission_id, threading.Event())
                self._spawn_worker(mission_id, cancel_event, mission.trust_level)
                return

        with self._lock:
            mission = self._missions.get(mission_id)
            if not mission:
                return

            step_statuses = [str(s.get("status") or "") for s in mission.steps]
            all_steps_ok = all(value in {"completed", "unverified"} for value in step_statuses)
            has_unverified = any(value == "unverified" for value in step_statuses)
            if all_steps_ok:
                if verification_passed and not has_unverified:
                    mission.status = "completed"
                    mission.summary = f"Execution succeeded and verified: {verif_detail}"
                else:
                    mission.status = "completed_unverified"
                    reason = "one or more steps only reported dispatch" if has_unverified else verif_detail
                    mission.summary = f"Execution finished without full proof: {reason}"
            else:
                mission.status = "failed"
                mission.summary = "One or more steps failed execution."

            mission.updated_at = self._clock()
            self._save()
            self._emit_progress(mission, "finished", mission.summary)

    def _verify_checks(self, mission: Mission) -> tuple[bool, str]:
        """Verify real deterministic outcomes from checks."""
        checks = mission.checks
        if not checks:
            return False, "No verification checks specified."

        verifications: list[str] = []
        all_passed = True

        for check in checks:
            c_lower = check.lower()
            # File existence check
            m = re.fullmatch(r"\s*file\s+exists\s*:\s*(.+?)\s*", check, re.IGNORECASE)
            if m:
                target_path = Path(m.group(1).strip().strip('\"\''))
                if target_path.is_file():
                    verifications.append(f"Verified: {target_path} exists")
                else:
                    all_passed = False
                    verifications.append(f"Failed check: {target_path} does not exist")
                continue

            # Process / window running check
            m_proc = re.fullmatch(r"\s*process\s+['\"]?([\w\-\\.]+)['\"]?\s+running\s*", c_lower)
            if m_proc:
                pname = m_proc.group(1).lower()
                try:
                    import psutil
                    running = any(pname == (p.info["name"] or "").lower() for p in psutil.process_iter(["name"]))
                    if running:
                        verifications.append(f"Verified: {pname} is running")
                    else:
                        all_passed = False
                        verifications.append(f"Failed check: {pname} is not running")
                except Exception:
                    all_passed = False
                continue

            all_passed = False
            verifications.append(f"Unverifiable check: '{check}'")

        return all_passed, "; ".join(verifications)

    def _review_followup(self, mission: Mission, verif_detail: str) -> list[dict[str, Any]]:
        """Bounded reviewer asking if further allowed steps are needed from original brief."""
        allowed_scopes = classify_goal_scope(mission.goal)
        allowed_tools = sorted([t for t in MISSION_ALLOWED_TOOLS if TOOL_OPERATION_CLASSES.get(t, set()) & allowed_scopes])

        review_prompt = (
            "You are Zaya reviewing mission progress against the original owner goal. "
            f"Original goal: '{mission.goal}'. "
            f"Verification findings: '{verif_detail}'. "
            f"Executed steps: {[{'desc': s['description'], 'tool': s['tool'], 'status': s['status']} for s in mission.steps]}. "
            f"Allowed tools: {allowed_tools}. "
            "You may return decision 'complete', 'blocked', or 'continue'. "
            "For 'continue', provide up to 2 follow-up steps using ONLY allowed tools. "
            "Never escalate scope or invent new tools. Return JSON only: "
            "{\"decision\": \"complete|continue|blocked\", \"steps\": [{\"id\": 1, \"description\": \"...\", \"tool\": \"...\", \"parameters\": {}}]}"
        )

        resp = _json_call(review_prompt, {"goal": mission.goal})
        if isinstance(resp, dict) and resp.get("decision") == "continue":
            raw_steps = resp.get("steps", [])
            valid_steps = []
            curr_id = len(mission.steps) + 1
            for s in raw_steps[:2]:
                if isinstance(s, dict):
                    tool = str(s.get("tool", "")).strip().lower()
                    if tool in allowed_tools:
                        valid_steps.append({
                            "id": curr_id,
                            "description": str(s.get("description", "Follow-up step"))[:300],
                            "tool": tool,
                            "parameters": s.get("parameters", {}) if isinstance(s.get("parameters"), dict) else {},
                            "status": "pending",
                            "result": "",
                            "error": "",
                        })
                        curr_id += 1
            return valid_steps

        return []

    def continue_mission(self, mission_id: str, approved: bool = True) -> ToolResult:
        """Resume a paused, interrupted, or waiting_confirmation mission."""
        require_owner()
        caller_trust = get_trust()
        if caller_trust not in _ALLOWED_TRUSTS:
            raise PermissionError(f"Owner authorization required to continue missions (got {caller_trust}).")

        with self._lock:
            mission = self._missions.get(mission_id)
            if not mission:
                return ToolResult("failed", f"Mission {mission_id} not found.")

            if mission.status == "waiting_confirmation":
                task_id = (mission.pending_confirmation or {}).get('runtime_task_id')
                if not approved:
                    if task_id:
                        from core import confirm
                        confirm.cancel_task(task_id)
                    mission.status = "cancelled"
                    mission.error = "Confirmation denied by owner."
                    mission.updated_at = self._clock()
                    self._save()
                    return ToolResult("success", f"Mission {mission_id} denied and cancelled.", {"mission": mission.public()}, side_effect=True)

                # A model-provided boolean cannot resolve the real UI gate.
                # Continue only after its originating task records completion.
                if not task_id:
                    return ToolResult('waiting_confirmation', 'Use the actual confirmation interface; this mission has no verified approval result.')
                from core.task_runtime import get_runtime
                task = get_runtime().get(task_id)
                if task.state != 'completed':
                    if task.state in {'cancelled', 'failed'}:
                        mission.status, mission.error = task.state, task.error or 'The confirmed step did not complete.'
                        self._save()
                        return ToolResult('failed', mission.error)
                    return ToolResult('waiting_confirmation', 'The actual confirmation is still pending. Confirm on the interface, then continue.')
                for step in mission.steps:
                    if step['id'] == mission.pending_confirmation['step_id']:
                        step['status'], step['result'] = 'completed', 'Completion recorded by the confirmed operator task.'
                mission.status = "running"
                mission.pending_confirmation = None
                mission.updated_at = self._clock()
                self._save()

            elif mission.status == "waiting_clarification":
                if not approved:
                    mission.status = "cancelled"
                    mission.error = "Clarification was not provided; mission cancelled."
                    mission.updated_at = self._clock()
                    self._save()
                    return ToolResult("success", f"Mission {mission_id} cancelled.",
                                      {"mission": mission.public()}, side_effect=True)
                pending = mission.pending_confirmation or {}
                for step in mission.steps:
                    if step["id"] == pending.get("step_id") and step.get("status") == "pending":
                        step["error"] = "Owner continued after clarification."
                mission.pending_confirmation = None
                mission.status = "running"
                mission.updated_at = self._clock()
                self._save()

            elif mission.status == "waiting_external":
                if not approved:
                    mission.status = "paused"
                    mission.updated_at = self._clock()
                    self._save()
                    return ToolResult("success", f"Mission {mission_id} paused while the external operation continues.",
                                      {"mission": mission.public()}, side_effect=True)
                pending = mission.pending_confirmation or {}
                for step in mission.steps:
                    if step["id"] == pending.get("step_id") and step.get("status") == "started":
                        step["status"] = "completed"
                        step["result"] = (step.get("result") or "") + " Owner confirmed continuation after external start."
                mission.pending_confirmation = None
                mission.status = "running"
                mission.updated_at = self._clock()
                self._save()

            elif mission.status in ("interrupted", "paused"):
                pending = mission.pending_confirmation or {}
                kind = str(pending.get("kind") or "")
                if kind == "confirmation":
                    if not approved:
                        return ToolResult("success", f"Mission {mission_id} remains paused.",
                                          {"mission": mission.public()}, side_effect=True)
                    # A restart pauses the mission, but it must not bypass the
                    # real confirmation gate. Only the originating runtime task
                    # can prove that the owner approved the action.
                    task_id = pending.get("runtime_task_id")
                    if not task_id:
                        return ToolResult(
                            "waiting_confirmation",
                            "Use the actual confirmation interface; this paused mission has no verified approval result.",
                        )
                    from core.task_runtime import get_runtime
                    try:
                        task = get_runtime().get(task_id)
                    except KeyError:
                        task = None
                    if task is not None and task.state in {"cancelled", "failed"}:
                        mission.status = task.state
                        mission.error = task.error or "The confirmed operation did not complete."
                        self._save()
                        return ToolResult("failed", mission.error)
                    if task is not None and task.state == "waiting_confirmation":
                        return ToolResult(
                            "waiting_confirmation",
                            "The actual confirmation is still pending. Confirm on the interface, then continue.",
                        )
                    if task is None or task.state == "paused":
                        # The interface gate lives in memory, so a restart loses
                        # the pending banner. Re-issue the step instead of
                        # marking it complete; the tool will go through the real
                        # confirmation gate again.
                        for step in mission.steps:
                            if step.get("id") == pending.get("step_id"):
                                step["status"] = "pending"
                                step["result"] = ""
                                step["error"] = "Restarted before approval; the confirmation will be requested again."
                        mission.pending_confirmation = None
                        mission.status = "running"
                        mission.updated_at = self._clock()
                        self._save()
                    elif task.state == "completed":
                        for step in mission.steps:
                            if step.get("id") == pending.get("step_id"):
                                step["status"] = "completed"
                                step["result"] = "Completion recorded by the confirmed operator task."
                        mission.pending_confirmation = None
                        mission.status = "running"
                        mission.updated_at = self._clock()
                        self._save()
                    else:
                        return ToolResult(
                            "waiting_confirmation",
                            "The actual confirmation is still pending. Confirm on the interface, then continue.",
                        )
                else:
                    if not approved:
                        return ToolResult("success", f"Mission {mission_id} remains paused.",
                                          {"mission": mission.public()}, side_effect=True)
                    if kind == "external":
                        # A restart pauses the mission. An explicit owner
                        # continue is the acknowledgement that the externally
                        # started step may be recorded as finished; otherwise
                        # the worker would later treat the untouched "started"
                        # step as a failure.
                        for step in mission.steps:
                            if step.get("id") == pending.get("step_id") and step.get("status") == "started":
                                step["status"] = "completed"
                                step["result"] = (step.get("result") or "") + (
                                    " Owner confirmed continuation after external start.")
                    mission.pending_confirmation = None
                    mission.status = "running"
                    mission.updated_at = self._clock()
                    self._save()

            else:
                return ToolResult("failed", f"Mission {mission_id} is in status '{mission.status}' and cannot be continued.")

            cancel_event = threading.Event()
            self._cancel_events[mission_id] = cancel_event

        self._spawn_worker(mission_id, cancel_event, caller_trust)
        return ToolResult("success", f"Mission {mission_id} resumed.", {"mission": mission.public()}, side_effect=True)

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
            task_id = (mission.pending_confirmation or {}).get('runtime_task_id')
            if task_id:
                from core import confirm
                confirm.cancel_task(task_id)
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
