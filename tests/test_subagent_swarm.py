"""Tests for Parallel Sub-Worker Swarm & Multi-Agent Mesh (Cycle 72).
Created and developed by Sajan Rai for Zaya.
"""
from __future__ import annotations

import json
import time
from unittest.mock import patch
import pytest

from core.subagent_swarm import SubAgentSwarm, SwarmTask
from actions.subagent_swarm_action import handle_subagent_swarm


class TestSubAgentSwarm:
    def test_spawn_and_complete_task(self):
        swarm = SubAgentSwarm(max_workers=2)

        def simple_work(x: int, y: int) -> int:
            return x * y

        task = swarm.spawn("Multiplier", "MathWorker", simple_work, 6, 7)
        assert task.status in ("queued", "running", "completed")

        # Wait for completion
        res = swarm.join(task_ids=[task.task_id], timeout=2.0)
        assert res["completed"] == 1
        assert res["pending"] == 0

        t = swarm.get_task(task.task_id)
        assert t is not None
        assert t.status == "completed"
        assert t.result == 42
        assert t.duration_sec is not None

    def test_failed_task_captures_error(self):
        swarm = SubAgentSwarm(max_workers=2)

        def bad_work():
            raise ValueError("Something exploded!")

        task = swarm.spawn("BadWorker", "TestCrash", bad_work)
        swarm.join(task_ids=[task.task_id], timeout=2.0)

        t = swarm.get_task(task.task_id)
        assert t is not None
        assert t.status == "failed"
        assert "Something exploded!" in (t.error or "")

    def test_concurrent_execution(self):
        swarm = SubAgentSwarm(max_workers=4)

        def sleep_and_return(sec: float, val: str) -> str:
            time.sleep(sec)
            return val

        t0 = time.monotonic()
        task1 = swarm.spawn("W1", "R1", sleep_and_return, 0.1, "res1")
        task2 = swarm.spawn("W2", "R2", sleep_and_return, 0.1, "res2")
        task3 = swarm.spawn("W3", "R3", sleep_and_return, 0.1, "res3")

        swarm.join(task_ids=[task1.task_id, task2.task_id, task3.task_id], timeout=3.0)
        elapsed = time.monotonic() - t0

        # All 3 ran in parallel so total elapsed should be close to 0.1s, well under 0.3s
        assert elapsed < 0.25
        assert swarm.get_task(task1.task_id).result == "res1"
        assert swarm.get_task(task2.task_id).result == "res2"
        assert swarm.get_task(task3.task_id).result == "res3"


class TestSubAgentSwarmAction:
    def test_action_spawn_list_and_join(self):
        with patch("core.action_loader.execute_tool", return_value="Fake Tool Result"):
            spawn_res = handle_subagent_swarm(
                action="spawn",
                name="ActionWorker",
                role="Tester",
                tool_name="fake_tool",
            )
            spawn_data = json.loads(spawn_res)
            assert spawn_data["status"] == "success"
            task_id = spawn_data["task_id"]

            # Check list
            list_res = handle_subagent_swarm(action="list")
            list_data = json.loads(list_res)
            assert list_data["count"] >= 1

            # Join
            join_res = handle_subagent_swarm(action="join", task_id=task_id, timeout=2.0)
            join_data = json.loads(join_res)
            assert join_data["status"] == "success"
            assert join_data["summary"]["completed"] == 1
