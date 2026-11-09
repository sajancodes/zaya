"""Tests for Habit Learning and Automated Routine Synthesis Engine.
Created and developed by Sajan Rai for Zaya.
"""
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

os.environ.setdefault("TRUST_LOCAL_OWNER", "1")

from core.habit_engine import HabitEngine
from actions.habit_action import habit_action


@pytest.fixture
def temp_engine(tmp_path):
    store = tmp_path / "habits.json"
    return HabitEngine(store_path=store)


class TestHabitEngine:
    def test_record_actions_and_synthesize_routine(self, temp_engine):
        # Repeat the sequence (tool_A -> tool_B) 3 times
        routine = None
        for _ in range(3):
            temp_engine.record_action("spatial_layout", {"preset": "split_code"}, project="Zaya")
            routine = temp_engine.record_action("system_status", {}, project="Zaya")

        assert routine is not None
        assert "Auto: spatial_layout + system_status" in routine.name
        assert len(routine.steps) == 2
        assert routine.steps[0].tool_name == "spatial_layout"
        assert routine.steps[1].tool_name == "system_status"

    def test_custom_routine_lifecycle(self, temp_engine):
        steps = [
            {"tool_name": "spatial_layout", "parameters": {"preset": "focus"}, "description": "Focus mode"},
            {"tool_name": "system_status", "parameters": {}, "description": "Check status"},
        ]
        r = temp_engine.create_custom_routine("Dev Focus", steps, trigger_context="project:Zaya")
        assert r.name == "Dev Focus"
        assert len(r.steps) == 2

        # Check triggers
        matches = temp_engine.check_context_triggers(current_project="Zaya")
        assert len(matches) >= 1
        assert matches[0].name == "Dev Focus"

        # Delete
        assert temp_engine.delete_routine(r.id) is True
        assert temp_engine.get_routine(r.id) is None


class TestHabitAction:
    def test_action_list(self):
        res = habit_action({"action": "list"})
        assert res.status == "success"
        assert "Habit Engine:" in res.summary

    def test_action_create_and_delete(self, tmp_path):
        steps = [{"tool_name": "system_status", "parameters": {}}]
        with patch("actions.habit_action.get_habit_engine") as mock_get:
            engine = HabitEngine(store_path=tmp_path / "h.json")
            mock_get.return_value = engine

            res = habit_action({"action": "create", "name": "Quick Health", "steps": steps})
            assert res.status == "success"
            r_id = res.data["id"]

            res_del = habit_action({"action": "delete", "routine_id": r_id})
            assert res_del.status == "success"
