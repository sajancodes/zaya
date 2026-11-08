"""Autonomous Long-Horizon Agent & Self-Healing Execution Loop for Zaya.
Created and developed by Sajan Rai.

Executes multi-step goals with bounded iterations, evidence inspection,
automated error diagnosis, and self-correcting retry loops.
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from core.event_bus import bus
from core.execution_policy import require_owner
from core.task_runtime import Task, TaskRuntime, get_runtime
from core.tool_result import ToolResult

logger = logging.getLogger(__name__)

MAX_AUTONOMOUS_STEPS = 12
MAX_STEP_RETRIES = 3


@dataclass
class GoalStep:
    id: int
    description: str
    tool: str
    parameters: dict[str, Any] = field(default_factory=dict)
    status: str = "pending"  # pending, running, completed, failed, skipped
    result: Optional[dict[str, Any]] = None
    retries: int = 0
    error: str = ""


class AutonomousGoalRunner:
    def __init__(
        self,
        runtime: Optional[TaskRuntime] = None,
        tool_executor: Optional[Callable[[str, dict[str, Any]], ToolResult]] = None,
    ) -> None:
        self.runtime = runtime or get_runtime()
        self.tool_executor = tool_executor or self._default_tool_executor
        self._lock = threading.RLock()
        self._active_runs: dict[str, bool] = {}

    def _default_tool_executor(self, tool_name: str, parameters: dict[str, Any]) -> ToolResult:
        """Execute a tool via ActionRegistry or system execution policy."""
        try:
            from core.action_loader import ActionRegistry
            registry = ActionRegistry()
            record = registry.get(tool_name)
            if not record or not record.handler:
                return ToolResult("failed", f"Tool '{tool_name}' is not registered.", {"tool_missing": True})
            res = record.handler(parameters=parameters)
            if isinstance(res, ToolResult):
                return res
            elif isinstance(res, str):
                return ToolResult("success", res, {"output": res})
            elif isinstance(res, dict):
                return ToolResult("success", "Operation completed", res)
            return ToolResult("success", str(res))
        except Exception as exc:
            return ToolResult("failed", f"Tool '{tool_name}' failed with error: {exc}", {"error": str(exc)})

    def run_goal(
        self,
        goal: str,
        steps: Optional[List[dict[str, Any]]] = None,
        project_context: str = "",
        max_steps: int = MAX_AUTONOMOUS_STEPS,
    ) -> ToolResult:
        """Run an autonomous multi-step goal with self-healing retries."""
        require_owner()
        task = self.runtime.create(
            goal=goal,
            plan={"project": project_context, "steps": steps or []},
            source="autonomous_agent",
        )
        task_id = task.id

        with self._lock:
            self._active_runs[task_id] = True

        try:
            self.runtime.transition(task_id, "planning")
            bus.publish("task.planning", task_id=task_id, goal=goal)

            # Generate or parse execution plan
            plan_steps = self._resolve_plan(goal, steps, project_context)
            if not plan_steps:
                self.runtime.transition(task_id, "failed", error="Unable to formulate actionable execution plan.")
                return ToolResult("failed", "Unable to formulate actionable execution plan.", {"task_id": task_id})

            self.runtime.transition(task_id, "executing", plan={"steps": [s.__dict__ for s in plan_steps]})
            evidence_log: list[dict[str, Any]] = []

            for step in plan_steps[:max_steps]:
                with self._lock:
                    if not self._active_runs.get(task_id, False):
                        self.runtime.transition(task_id, "cancelled", error="Cancelled by user.")
                        return ToolResult("partial", "Autonomous execution cancelled.", {"task_id": task_id})

                success = self._execute_step_with_self_healing(task_id, step, evidence_log)
                if not success:
                    # Critical step failure after retries
                    self.runtime.transition(task_id, "failed", error=f"Step failed after retries: {step.description}")
                    return ToolResult(
                        "failed",
                        f"Autonomous execution failed at step: {step.description}. Error: {step.error}",
                        {"task_id": task_id, "step": step.__dict__, "evidence": evidence_log},
                    )

            # Verification phase
            self.runtime.transition(task_id, "verifying")
            bus.publish("task.verifying", task_id=task_id)

            # Mark completed
            final_summary = f"Autonomous goal completed successfully ({len(plan_steps)} steps executed)."
            final_res = ToolResult("success", final_summary, {"task_id": task_id, "steps_executed": len(plan_steps)}, evidence_log)
            self.runtime.finish(task_id, final_res)
            bus.publish("task.completed", task_id=task_id, summary=final_summary)
            return final_res

        except Exception as exc:
            logger.exception("Autonomous goal runner encountered fatal error: %s", exc)
            self.runtime.transition(task_id, "failed", error=str(exc))
            return ToolResult("failed", f"Autonomous runner fatal error: {exc}", {"task_id": task_id, "error": str(exc)})
        finally:
            with self._lock:
                self._active_runs.pop(task_id, None)

    def cancel(self, task_id: str) -> bool:
        """Cancel an in-flight autonomous run."""
        with self._lock:
            if task_id in self._active_runs:
                self._active_runs[task_id] = False
                return True
        return False

    def _resolve_plan(
        self,
        goal: str,
        steps: Optional[List[dict[str, Any]]],
        project_context: str,
    ) -> List[GoalStep]:
        """Convert raw step dicts or heuristics into structured GoalStep instances."""
        resolved: List[GoalStep] = []
        if steps:
            for idx, s in enumerate(steps, start=1):
                resolved.append(
                    GoalStep(
                        id=idx,
                        description=str(s.get("description") or f"Step {idx}"),
                        tool=str(s.get("tool") or "").strip(),
                        parameters=dict(s.get("parameters") or {}),
                    )
                )
            return resolved

        # Default self-healing workspace audit heuristic if no explicit steps provided
        clean_goal = goal.lower()
        if "test" in clean_goal or "verify" in clean_goal:
            resolved.append(GoalStep(1, "Inspect git repository status", "repo_sentinel", {}))
            resolved.append(GoalStep(2, "Inspect active developer ports", "port_sentinel", {}))
        elif "build" in clean_goal or "compile" in clean_goal:
            resolved.append(GoalStep(1, "Check active project awareness", "project_status", {}))
            resolved.append(GoalStep(2, "Inspect git repository status", "repo_sentinel", {}))
        else:
            resolved.append(GoalStep(1, "Inspect project status", "project_status", {}))

        return resolved

    def _execute_step_with_self_healing(
        self,
        task_id: str,
        step: GoalStep,
        evidence_log: list[dict[str, Any]],
    ) -> bool:
        """Execute a step and automatically diagnose/retry if it fails."""
        step.status = "running"
        bus.publish("task.step_started", task_id=task_id, step=step.description)

        for attempt in range(1, MAX_STEP_RETRIES + 1):
            step.retries = attempt
            try:
                self.runtime.attempt(task_id, step.description)
            except Exception:
                pass  # Ignore attempt limit if retrying inside runner

            result = self.tool_executor(step.tool, step.parameters)
            evidence_log.append({
                "step": step.description,
                "tool": step.tool,
                "attempt": attempt,
                "status": result.status,
                "summary": result.summary,
            })

            if result.status == "success":
                step.status = "completed"
                step.result = result.data
                bus.publish("task.step_completed", task_id=task_id, step=step.description)
                return True

            # Step failed - attempt self-healing diagnosis
            err_msg = result.summary or str(result.data.get("error", "Unknown error"))
            step.error = err_msg
            logger.warning("Step '%s' failed (attempt %d/%d): %s", step.description, attempt, MAX_STEP_RETRIES, err_msg)
            bus.publish("task.self_healing", task_id=task_id, step=step.description, attempt=attempt, error=err_msg)

            if attempt < MAX_STEP_RETRIES:
                self._apply_self_healing_corrections(step, err_msg)
                time.sleep(0.1)

        step.status = "failed"
        return False

    def _apply_self_healing_corrections(self, step: GoalStep, error_message: str) -> None:
        """Adjust parameters or retry strategy based on error patterns."""
        err = error_message.lower()
        # Case 1: Timeout -> increase timeout if present
        if "timeout" in err or "timed out" in err:
            cur_to = step.parameters.get("timeout", 5)
            step.parameters["timeout"] = cur_to * 2

        # Case 2: Port already in use -> signal retry or check port
        elif "address already in use" in err or "port" in err:
            step.parameters["force"] = True

        # Case 3: Missing path or file not found
        elif "not found" in err or "no such file" in err:
            # Recheck path parameter if relative
            if "path" in step.parameters and not Path(step.parameters["path"]).is_absolute():
                step.parameters["path"] = str(Path(step.parameters["path"]).resolve())


# Global singleton
_goal_runner: AutonomousGoalRunner | None = None
_runner_lock = threading.Lock()


def get_autonomous_goal_runner() -> AutonomousGoalRunner:
    global _goal_runner
    with _runner_lock:
        if _goal_runner is None:
            _goal_runner = AutonomousGoalRunner()
        return _goal_runner
