"""Tests for Autonomous Long-Horizon Goal Runner and Self-Healing Loop.
Created and developed by Sajan Rai for Zaya.
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any
import pytest

from core.autonomous_agent import AutonomousGoalRunner, GoalStep
from core.execution_policy import TRUST_EXTERNAL_MESSAGE, TRUST_LOCAL_OWNER, with_trust
from core.task_runtime import TaskRuntime
from core.tool_result import ToolResult
from actions.autonomous_task import autonomous_task


@pytest.fixture
def mock_runtime():
    runtime = TaskRuntime(":memory:")
    yield runtime



def test_goal_runner_plan_resolution(mock_runtime):
    runner = AutonomousGoalRunner(runtime=mock_runtime)
    # Test heuristic resolution
    plan = runner._resolve_plan("Test and verify the system", None, "Zaya")
    assert len(plan) == 2
    assert plan[0].tool == "repo_sentinel"
    assert plan[1].tool == "port_sentinel"

    # Test explicit steps
    custom_steps = [
        {"description": "Step 1", "tool": "custom_tool", "parameters": {"a": 1}},
        {"description": "Step 2", "tool": "custom_tool_2", "parameters": {"b": 2}},
    ]
    resolved = runner._resolve_plan("Custom Goal", custom_steps, "Zaya")
    assert len(resolved) == 2
    assert resolved[0].tool == "custom_tool"
    assert resolved[0].parameters == {"a": 1}
    assert resolved[1].tool == "custom_tool_2"


def test_goal_runner_successful_execution(mock_runtime, monkeypatch):
    executed = []

    def dummy_executor(tool_name: str, parameters: dict[str, Any]) -> ToolResult:
        executed.append((tool_name, parameters))
        return ToolResult("success", f"Executed {tool_name}", {"ok": True})

    runner = AutonomousGoalRunner(runtime=mock_runtime, tool_executor=dummy_executor)
    steps = [
        {"description": "First step", "tool": "step_one", "parameters": {"key": "val1"}},
        {"description": "Second step", "tool": "step_two", "parameters": {"key": "val2"}},
    ]

    res = runner.run_goal("Test execution goal", steps=steps)
    assert res.status == "success"
    assert len(executed) == 2
    assert executed[0][0] == "step_one"
    assert executed[1][0] == "step_two"

    task_id = res.data["task_id"]
    task = mock_runtime.get(task_id)
    assert task.state == "completed"


def test_goal_runner_self_healing_retry(mock_runtime):
    attempts = []

    def flaky_executor(tool_name: str, parameters: dict[str, Any]) -> ToolResult:
        attempts.append(dict(parameters))
        if len(attempts) < 3:
            return ToolResult("failed", "Request timed out waiting for server response", {"error": "timeout"})
        return ToolResult("success", "Succeeded on retry", {"attempts": len(attempts)})

    runner = AutonomousGoalRunner(runtime=mock_runtime, tool_executor=flaky_executor)
    steps = [
        {"description": "Network call", "tool": "fetch_api", "parameters": {"timeout": 5}},
    ]

    res = runner.run_goal("Flaky API goal", steps=steps)
    assert res.status == "success"
    assert len(attempts) == 3
    # Verify parameter adaptation (timeout doubled on timeout error)
    assert attempts[0].get("timeout") == 5
    assert attempts[1].get("timeout") == 10
    assert attempts[2].get("timeout") == 20


def test_goal_runner_cancellation(mock_runtime):
    runner = AutonomousGoalRunner(runtime=mock_runtime)

    def slow_executor(tool_name: str, parameters: dict[str, Any]) -> ToolResult:
        # Trigger cancel during step 1
        active = [t for t in runner.runtime.list() if t.state not in {"completed", "failed", "cancelled"}]
        if active:
            runner.cancel(task_id=active[0].id)
        return ToolResult("success", "Done", {})

    runner.tool_executor = slow_executor
    steps = [
        {"description": "Step 1", "tool": "t1"},
        {"description": "Step 2", "tool": "t2"},
    ]

    res = runner.run_goal("Cancellable goal", steps=steps)
    assert res.status == "partial"
    assert "cancelled" in res.summary.lower()


def test_autonomous_task_action_handler(mock_runtime, monkeypatch):
    runner = AutonomousGoalRunner(
        runtime=mock_runtime,
        tool_executor=lambda t, p: ToolResult("success", f"Done {t}", {}),
    )
    monkeypatch.setattr("actions.autonomous_task.get_autonomous_goal_runner", lambda: runner)
    monkeypatch.setattr("actions.autonomous_task.get_runtime", lambda: mock_runtime)

    # Test run
    run_res = autonomous_task({
        "action": "run",
        "goal": "Verify system health",
        "steps": [{"description": "Check", "tool": "check_tool"}],
    })
    assert run_res.status == "success"
    task_id = run_res.data["task_id"]

    # Test status
    status_res = autonomous_task({"action": "status", "task_id": task_id})
    assert status_res.status == "success"
    assert status_res.data["state"] == "completed"

    # Test invalid action
    inv_res = autonomous_task({"action": "invalid_action"})
    assert inv_res.status == "failed"


def test_autonomous_task_untrusted_source_blocked(mock_runtime):
    runner = AutonomousGoalRunner(runtime=mock_runtime)
    with with_trust(TRUST_EXTERNAL_MESSAGE):
        with pytest.raises(PermissionError, match="Untrusted or external source"):
            runner.run_goal("Hacked goal")

        with pytest.raises(PermissionError, match="Untrusted or external source"):
            autonomous_task({"action": "run", "goal": "Hacked goal"})

