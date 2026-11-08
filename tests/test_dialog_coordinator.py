"""Tests for Dialog Coordinator and Dialog Action.
Created and developed by Sajan Rai for Zaya.
"""
from __future__ import annotations

import pytest

from core.dialog_coordinator import (
    DialogCoordinator,
    DialogState,
)
from core.execution_policy import TRUST_EXTERNAL_MESSAGE, with_trust
from actions.dialog_action import dialog_action


def test_contextual_pronoun_resolution():
    coord = DialogCoordinator()

    # First turn: mentions a specific file
    turn1 = coord.process_turn("Can you inspect web/server.py for errors?")
    assert turn1.active_entity == "server.py"
    assert "server.py" in turn1.resolved_text

    # Second turn: uses pronoun "it"
    turn2 = coord.process_turn("Restart it now")
    assert turn2.active_entity == "server.py"
    assert "Restart server.py now" in turn2.resolved_text

    # Third turn: uses pronoun "that"
    turn3 = coord.process_turn("What port is that using?")
    assert "What port is server.py using?" in turn3.resolved_text


def test_confirmation_state_machine():
    coord = DialogCoordinator()
    coord.request_confirmation(
        action_name="process_terminate",
        parameters={"pid": 1234},
        prompt="Are you sure you want to kill PID 1234?",
    )
    assert coord.get_context().state == DialogState.AWAITING_CONFIRMATION.value

    # Affirmative response
    res = coord.process_turn("Yes, proceed")
    assert res.state == DialogState.IDLE.value
    assert res.ready_to_execute is True
    assert res.action_payload["parameters"]["pid"] == 1234

    # Negative response in new confirmation
    coord.request_confirmation("delete_file", {"path": "tmp.txt"}, "Delete?")
    res_no = coord.process_turn("No, cancel that")
    assert res_no.state == DialogState.IDLE.value
    assert res_no.ready_to_execute is False
    assert res_no.intent == "cancelled"


def test_slot_filling_flow():
    coord = DialogCoordinator()
    coord.request_slot_fill(
        intent="run_tests",
        entity="Zaya",
        required_slot="test_suite",
        prompt="Which test suite would you like to execute? (unit, android, all)",
    )
    assert coord.get_context().state == DialogState.AWAITING_SLOT_FILL.value

    res = coord.process_turn("unit")
    assert res.state == DialogState.IDLE.value
    assert res.ready_to_execute is True
    assert res.action_payload["slots"]["test_suite"] == "unit"


def test_side_query_suspension_and_resumption():
    coord = DialogCoordinator()
    coord.set_active_entity("android/app/build.gradle")

    # User interrupts with side query
    res_side = coord.process_turn("Wait, what time is it?")
    assert res_side.state == DialogState.SUSPENDED_SIDE_QUERY.value

    # User continues previous thought
    res_resume = coord.process_turn("Check it for dependency updates")
    assert "Check android/app/build.gradle for dependency updates" in res_resume.resolved_text


def test_dialog_action_handler():
    # Process turn
    p_res = dialog_action({"action": "process", "text": "Inspect main.py"})
    assert p_res.status == "success"
    assert p_res.data["active_entity"] == "main.py"

    # Status
    st_res = dialog_action({"action": "status"})
    assert st_res.status == "success"
    assert st_res.data["active_entity"] == "main.py"

    # Reset
    rst_res = dialog_action({"action": "reset"})
    assert rst_res.status == "success"
    assert rst_res.data["active_entity"] is None

    # Unauthorized access check
    with with_trust(TRUST_EXTERNAL_MESSAGE):
        with pytest.raises(PermissionError):
            dialog_action({"action": "status"})
