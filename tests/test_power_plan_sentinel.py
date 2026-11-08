"""Tests for Windows Power Schemes & Performance Mode Sentinel."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch
import pytest

from actions.power_plan_sentinel import (
    get_active_power_scheme,
    list_power_schemes,
    power_plan_sentinel,
    switch_power_scheme,
    TOOL,
)
from core.execution_policy import set_trust, TRUST_LOCAL_OWNER, TRUST_UNKNOWN
from core.fast_reflex import FastReflexRouter


@pytest.fixture(autouse=True)
def _owner_trust():
    set_trust(TRUST_LOCAL_OWNER)
    yield
    set_trust(TRUST_LOCAL_OWNER)


def test_owner_security_gate():
    set_trust(TRUST_UNKNOWN)
    with pytest.raises(PermissionError):
        power_plan_sentinel({"action": "status"})


def test_list_and_get_active_power_schemes_live():
    schemes = list_power_schemes()
    assert isinstance(schemes, list)
    assert len(schemes) > 0
    assert any(s.get("active") for s in schemes)

    active = get_active_power_scheme()
    assert active["status"] == "success"
    assert "name" in active
    assert "guid" in active


def test_switch_power_scheme_mocked():
    mock_schemes = [
        {"guid": "381b4222-f694-41f0-9685-ff5bb260df2e", "name": "Balanced", "active": True},
        {"guid": "ec75dd6d-7bec-44db-8aae-93355063212a", "name": "ultimate", "active": False},
        {"guid": "a1841308-3541-4fab-bc81-f71556f20b4a", "name": "Power Saver", "active": False},
    ]

    with patch("actions.power_plan_sentinel.list_power_schemes", return_value=mock_schemes), \
         patch("subprocess.check_call") as mock_call:

        # Performance request should match 'ultimate'
        res_perf = switch_power_scheme("performance")
        assert res_perf["status"] == "success"
        assert res_perf["name"] == "ultimate"
        mock_call.assert_called_with(["powercfg", "/setactive", "ec75dd6d-7bec-44db-8aae-93355063212a"], stdout=-3, stderr=-3)

        # Balanced request
        res_bal = switch_power_scheme("balanced")
        assert res_bal["status"] == "success"
        assert res_bal["name"] == "Balanced"

        # Saver request
        res_sav = switch_power_scheme("power saver")
        assert res_sav["status"] == "success"
        assert res_sav["name"] == "Power Saver"


def test_switch_power_scheme_unknown():
    mock_schemes = [
        {"guid": "381b4222-f694-41f0-9685-ff5bb260df2e", "name": "Balanced", "active": True},
    ]

    with patch("actions.power_plan_sentinel.list_power_schemes", return_value=mock_schemes):
        res = switch_power_scheme("nonexistent_profile_xyz")
        assert res["status"] == "error"
        assert "Available plans: Balanced" in res["message"]


def test_power_plan_sentinel_actions():
    mock_active = {
        "status": "success",
        "name": "Balanced",
        "guid": "381b4222-f694-41f0-9685-ff5bb260df2e",
        "all_schemes": [
            {"guid": "381b4222-f694-41f0-9685-ff5bb260df2e", "name": "Balanced", "active": True},
            {"guid": "ec75dd6d-7bec-44db-8aae-93355063212a", "name": "ultimate", "active": False},
        ],
    }

    with patch("actions.power_plan_sentinel.get_active_power_scheme", return_value=mock_active), \
         patch("actions.power_plan_sentinel.switch_power_scheme", return_value={"status": "success", "name": "ultimate"}), \
         patch("actions.power_plan_sentinel.list_power_schemes", return_value=mock_active["all_schemes"]):

        out_stat = json.loads(power_plan_sentinel({"action": "status"}))
        assert out_stat["status"] == "success"
        assert "Active Power Scheme: 'Balanced'" in out_stat["summary"]

        out_sw = json.loads(power_plan_sentinel({"action": "switch", "plan": "performance"}))
        assert out_sw["status"] == "success"
        assert out_sw["name"] == "ultimate"

        out_sw_err = json.loads(power_plan_sentinel({"action": "switch"}))
        assert out_sw_err["status"] == "error"

        out_list = json.loads(power_plan_sentinel({"action": "list"}))
        assert out_list["status"] == "success"
        assert len(out_list["data"]["schemes"]) == 2

        out_err = json.loads(power_plan_sentinel({"action": "invalid"}))
        assert out_err["status"] == "error"


def test_tool_declaration():
    assert TOOL["name"] == "power_plan_sentinel"
    assert "parameters" in TOOL
    assert callable(TOOL["handler"])


def test_fast_reflex_power_plans():
    router = FastReflexRouter()

    # Query
    intent, score = router.match("what power plan am i on")
    assert intent == "POWER_PLAN_QUERY"
    assert score >= 0.88

    res = router.execute_intent(intent)
    assert res.matched is True
    assert "Active Windows power plan is" in res.ack
